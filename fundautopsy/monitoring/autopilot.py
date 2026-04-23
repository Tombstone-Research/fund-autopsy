"""Weekly autopilot report generator for Fund Autopsy.

Runs every Monday. Aggregates state across the venture:
  - Schema monitor last-run status
  - Content draft queue (pending / approved / killed / published)
  - Deploy health (fund-autopsy.onrender.com)
  - Tweet log state (posted this week)
  - Networking log state (follows this week, escalations)
  - GitHub activity on Tombstone-Research org

Writes: Ventures/FundAutopsy/Intelligence/autopilot-YYYY-MM-DD.md

Operator review target: 5 minutes on phone. Everything else is details the
report already condensed.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

import httpx


VENTURE_ROOT = pathlib.Path(__file__).resolve().parents[2]
INTELLIGENCE_DIR = VENTURE_ROOT / "Intelligence"
CONTENT_DIR = VENTURE_ROOT / "content"
SCHEMA_REPORTS_DIR = VENTURE_ROOT / "fundautopsy" / "monitoring" / "reports"
DEPLOY_URL = "https://fund-autopsy.onrender.com"
DEPLOY_HEALTH_PATH = "/api/health"


@dataclass
class SectionResult:
    title: str
    status: str  # "GREEN", "YELLOW", "RED", "INFO"
    summary: str
    detail_lines: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        status_marker = {
            "GREEN": "PASS",
            "YELLOW": "WATCH",
            "RED": "ACTION",
            "INFO": "INFO",
        }[self.status]
        lines = [f"### {self.title} — {status_marker}", "", self.summary, ""]
        if self.detail_lines:
            lines.extend(self.detail_lines)
            lines.append("")
        return "\n".join(lines)


def check_schema_monitor() -> SectionResult:
    """Report status of the most recent schema monitor run."""
    if not SCHEMA_REPORTS_DIR.exists():
        return SectionResult(
            title="SEC schema monitor",
            status="RED",
            summary="No monitoring reports directory. Schema monitor has not been scheduled.",
        )

    reports = sorted(
        [p for p in SCHEMA_REPORTS_DIR.glob("*_schema_monitor_run.md")],
        reverse=True,
    )
    if not reports:
        return SectionResult(
            title="SEC schema monitor",
            status="RED",
            summary="No schema monitor runs found. Scheduled task may have never fired.",
        )

    latest = reports[0]
    age_days = max(0, (_dt.date.today() - _dt.date.fromisoformat(latest.stem[:10])).days)
    content = latest.read_text()
    # Support both report formats: the current generator emits
    # "**Result:** PASS" / "**Result:** FAIL" for each check, and older
    # diagnostic reports used a summary table with PASS/FAIL in cells.
    passed = content.count("**Result:** PASS") + content.count("[PASS]")
    failed = content.count("**Result:** FAIL") + content.count("[FAIL]")
    total = passed + failed

    if age_days > 3:
        status = "YELLOW"
    else:
        status = "GREEN" if failed == 0 else "RED"

    summary = (
        f"Latest run {latest.stem[:10]} ({age_days}d ago): "
        f"{passed}/{total} checks PASS"
        + (f", {failed} FAIL" if failed else "")
    )
    details = [f"- Report: `{latest.relative_to(VENTURE_ROOT)}`"]
    if failed:
        details.append(f"- **Action:** review failing checks before next scheduled run.")
    return SectionResult("SEC schema monitor", status, summary, details)


def check_content_queue() -> SectionResult:
    """Count drafts by state. Approved drafts are the publish queue."""
    pending = list((CONTENT_DIR / "drafts" / "pending").glob("*.md"))
    approved = list((CONTENT_DIR / "drafts" / "approved").glob("*.md"))
    killed = list((CONTENT_DIR / "drafts" / "killed").glob("*.md"))
    published = list((CONTENT_DIR / "drafts" / "published").glob("*.md"))

    total_in_flight = len(pending) + len(approved)
    if total_in_flight == 0:
        status = "RED"
        summary = "Draft queue is empty. Next content will not ship until drafts are generated."
    elif len(approved) == 0 and len(pending) > 0:
        status = "YELLOW"
        summary = f"{len(pending)} drafts pending operator review. Nothing approved for publish."
    else:
        status = "GREEN"
        summary = f"{len(approved)} approved and ready to publish; {len(pending)} pending review."

    details = ["**Pending review (awaiting operator tap):**"]
    if pending:
        for p in sorted(pending):
            details.append(f"- `{p.name}`")
    else:
        details.append("- (none)")
    details.append("")
    details.append("**Approved (publish queue):**")
    if approved:
        for p in sorted(approved):
            details.append(f"- `{p.name}`")
    else:
        details.append("- (none)")
    details.append("")
    details.append(f"**Lifetime:** {len(published)} published, {len(killed)} killed.")
    return SectionResult("Content draft queue", status, summary, details)


def check_deploy_health() -> SectionResult:
    """Ping the live site and report response time and status.

    Render free tier sleeps the service after 15 minutes of inactivity.
    A cold start can take 30-60 seconds. First attempt uses a long
    timeout; retry once after a short wait if the first attempt fails.
    """
    urls = [DEPLOY_URL + DEPLOY_HEALTH_PATH, DEPLOY_URL + "/"]
    last_error = None
    for attempt in range(2):
        for url in urls:
            try:
                start = _dt.datetime.now()
                resp = httpx.get(url, timeout=60, follow_redirects=True)
                elapsed = (_dt.datetime.now() - start).total_seconds()
                if resp.status_code < 400:
                    cold_note = " (cold start)" if elapsed > 10 else ""
                    return SectionResult(
                        title="Deploy health",
                        status="GREEN",
                        summary=f"{url} responded {resp.status_code} in {elapsed:.1f}s{cold_note}",
                        detail_lines=[f"- Checked: {url}"],
                    )
                elif resp.status_code == 404 and "health" in url:
                    # Health endpoint may not exist; try root next loop
                    continue
                else:
                    last_error = f"{url} returned {resp.status_code}"
            except httpx.RequestError as e:
                last_error = f"Deploy unreachable: {type(e).__name__}"
            except Exception as e:
                last_error = f"Health check error: {type(e).__name__}"
        # Wait a moment before retry (render cold start)
        if attempt == 0:
            import time

            time.sleep(10)

    return SectionResult(
        title="Deploy health",
        status="RED",
        summary=last_error or "Deploy unreachable after 2 attempts",
        detail_lines=[f"- Checked: {DEPLOY_URL}"],
    )


def check_tweet_log() -> SectionResult:
    """Parse content/tweet_log.md for posts in the last 7 days."""
    log_path = CONTENT_DIR / "tweet_log.md"
    if not log_path.exists():
        return SectionResult(
            title="Posted content (last 7 days)",
            status="YELLOW",
            summary="No tweet_log.md found.",
        )
    content = log_path.read_text()
    seven_days_ago = _dt.date.today() - _dt.timedelta(days=7)
    # Match lines like "1. **Seed 1 of 6** — 2026-04-06 — ..."
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")
    dates_found = []
    for match in pattern.finditer(content):
        try:
            d = _dt.date.fromisoformat(match.group(1))
            dates_found.append(d)
        except ValueError:
            continue
    recent = [d for d in dates_found if d >= seven_days_ago]
    if recent:
        status = "GREEN"
        summary = f"{len(recent)} item(s) posted in the last 7 days."
    else:
        latest = max(dates_found) if dates_found else None
        gap = (_dt.date.today() - latest).days if latest else None
        status = "YELLOW" if gap and gap > 14 else "INFO"
        summary = (
            f"No posts in last 7 days. Last post: {latest} ({gap}d ago)."
            if latest
            else "No posts ever logged."
        )
    return SectionResult("Posted content (last 7 days)", status, summary)


def check_networking_log() -> SectionResult:
    """Parse content/networking_log.md for follows and escalations in the last 7 days."""
    log_path = CONTENT_DIR / "networking_log.md"
    if not log_path.exists():
        return SectionResult(
            title="Networking activity (last 7 days)",
            status="INFO",
            summary="No networking log yet. Ramp 1 has not started.",
        )
    content = log_path.read_text()
    seven_days_ago = _dt.date.today() - _dt.timedelta(days=7)
    follow_count = 0
    followback_count = 0
    like_count = 0
    escalations: list[str] = []
    for line in content.splitlines():
        # Match "YYYY-MM-DD HH:MM | ACTION | ..."
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}\s*\|\s*(\w+)", line)
        if not m:
            continue
        try:
            d = _dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d < seven_days_ago:
            continue
        action = m.group(2).upper()
        if action == "FOLLOW":
            follow_count += 1
        elif action == "FOLLOW_BACK":
            followback_count += 1
        elif action == "LIKE":
            like_count += 1

    # Count escalations mentioned in the escalations section
    if "## Escalations" in content:
        esc_block = content.split("## Escalations", 1)[1]
        escalations = [
            line.strip("- ").strip()
            for line in esc_block.splitlines()
            if line.strip().startswith("-") and "(empty)" not in line
        ]

    if escalations:
        status = "RED"
        summary = (
            f"{len(escalations)} escalation(s). {follow_count} follows, "
            f"{followback_count} follow-backs, {like_count} likes in last 7d."
        )
    elif follow_count == 0 and like_count == 0:
        status = "YELLOW"
        summary = "No networking activity in last 7 days."
    else:
        status = "GREEN"
        summary = (
            f"{follow_count} follows, {followback_count} follow-backs, "
            f"{like_count} likes in last 7d. No escalations."
        )

    details: list[str] = []
    if escalations:
        details.append("**Escalations:**")
        for e in escalations:
            details.append(f"- {e}")
    return SectionResult(
        "Networking activity (last 7 days)", status, summary, details
    )


def check_github_activity() -> SectionResult:
    """Read recent commits on the fund-autopsy repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(VENTURE_ROOT), "log", "--since=7 days ago", "--oneline"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return SectionResult(
                title="Code activity (last 7 days)",
                status="INFO",
                summary="Not a git repo or git unavailable.",
            )
        commits = [l for l in result.stdout.splitlines() if l.strip()]
        if not commits:
            return SectionResult(
                title="Code activity (last 7 days)",
                status="INFO",
                summary="No commits in last 7 days.",
            )
        details = ["**Recent commits:**"] + [f"- {c}" for c in commits[:10]]
        return SectionResult(
            title="Code activity (last 7 days)",
            status="INFO",
            summary=f"{len(commits)} commits in last 7 days.",
            detail_lines=details,
        )
    except Exception as e:
        return SectionResult(
            title="Code activity (last 7 days)",
            status="INFO",
            summary=f"Git check errored: {type(e).__name__}",
        )


def build_report(today: Optional[_dt.date] = None) -> str:
    today = today or _dt.date.today()
    sections = [
        check_schema_monitor(),
        check_deploy_health(),
        check_content_queue(),
        check_tweet_log(),
        check_networking_log(),
        check_github_activity(),
    ]

    reds = [s for s in sections if s.status == "RED"]
    yellows = [s for s in sections if s.status == "YELLOW"]

    if reds:
        overall = "ACTION REQUIRED"
    elif yellows:
        overall = "ATTENTION"
    else:
        overall = "GREEN"

    header = [
        f"# Fund Autopsy — Autopilot Report {today.isoformat()}",
        "",
        f"**Overall status:** {overall}",
        f"**Generated:** {_dt.datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    summary_lines = ["## Status snapshot", ""]
    for s in sections:
        marker = {
            "GREEN": "OK",
            "YELLOW": "WATCH",
            "RED": "ACTION",
            "INFO": "INFO",
        }[s.status]
        summary_lines.append(f"- **{s.title}:** {marker} — {s.summary}")
    summary_lines.append("")

    if reds:
        summary_lines.append("## What needs operator attention this week")
        summary_lines.append("")
        for s in reds:
            summary_lines.append(f"- **{s.title}.** {s.summary}")
        summary_lines.append("")

    if yellows:
        summary_lines.append("## Watch items")
        summary_lines.append("")
        for s in yellows:
            summary_lines.append(f"- **{s.title}.** {s.summary}")
        summary_lines.append("")

    summary_lines.append("## Details")
    summary_lines.append("")
    for s in sections:
        summary_lines.append(s.to_markdown())

    summary_lines.append("---")
    summary_lines.append("")
    summary_lines.append(
        "_Report generated by `fundautopsy.monitoring.autopilot`. "
        "If this report is RED, the operator's weekly touchpoint should start here._"
    )
    summary_lines.append("")
    summary_lines.append(
        "_Scheduler wiring: create a scheduled task with cron `30 7 * * 1` "
        "(Monday 7:30 AM local) that runs `python -m fundautopsy.monitoring.autopilot` "
        "from the FundAutopsy root. Until then, this report generates only on demand._"
    )

    return "\n".join(header + summary_lines)


def main() -> int:
    today = _dt.date.today()
    report = build_report(today)
    INTELLIGENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = INTELLIGENCE_DIR / f"autopilot-{today.isoformat()}.md"
    out_path.write_text(report)
    print(f"Wrote autopilot report: {out_path.relative_to(VENTURE_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
