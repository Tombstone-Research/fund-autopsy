"""N-CEN thread generator for the Tombstone Research content pipeline.

Designed for a Sunday-overnight scheduled task. Reads the novel-angles
backlog and the existing draft queue, figures out which angle is next,
and writes a skeleton thread draft to `content/drafts/pending/` with
frontmatter that flows through the approve -> publish pipeline.

Threads 4 through 11 are already hand-drafted; the generator exists
for thread 12 and beyond. The initial ten-dimension backlog in
`docs/ncen_novel_angles.md` is exhausted by thread 11 (the capstone
paper release), so after that point the generator reads an optional
extension file (`docs/ncen_novel_angles_extension.md`). When no
unused angle is available, the run is a clean no-op: it logs the
reason and exits without writing a stub the reviewer would have to
kill by hand.

The generator does not claim to produce publish-ready prose. It
produces a full-structured draft -- frontmatter, opener, six tweets
built from the angle's structured content, citations scaffold, pre-
publish checklist, and phone-review summary -- that the operator can
approve, edit, or kill. The pre-publish checks enumerate the
verification steps each thread needs before it goes live.

Run from the FundAutopsy root:

    python -m fundautopsy.monitoring.thread_generator

Exit codes: 0 on any outcome that a scheduled task should treat as
healthy (draft written OR no new angle available). 1 on a hard error
(angles file missing, draft directory missing, unparseable backlog).
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration

# Default paths — all relative to the FundAutopsy root. Made overridable via
# CLI arguments so the module can be exercised under pytest without touching
# the real repository.
_DEFAULT_ANGLES_PATH = Path("docs/ncen_novel_angles.md")
_DEFAULT_EXTENSION_PATH = Path("docs/ncen_novel_angles_extension.md")
_DEFAULT_DRAFTS_ROOT = Path("content/drafts")
_DEFAULT_TWEET_LOG_PATH = Path("content/tweet_log.md")

# Cadence between threads. Existing drafts are spaced one week apart on
# Sundays; the generator preserves that cadence by targeting the
# Sunday N weeks after the most recent already-drafted thread.
_WEEKS_BETWEEN_THREADS: int = 1

# Lowest thread number the generator is allowed to produce. Threads
# 1-11 are hand-drafted; the generator refuses to overwrite that work.
_MIN_GENERATED_THREAD_NUMBER: int = 12


# ---------------------------------------------------------------------------
# Data model

@dataclass
class Angle:
    """A single N-CEN research angle parsed from the backlog file."""

    number: int
    title: str
    fields: str = ""         # "N-CEN Fields:" paragraph
    angle: str = ""          # "The angle:" paragraph
    conflict: str = ""       # "Conflict of interest story:" paragraph
    content_hook: str = ""   # "Content hook:" paragraph
    tool_potential: str = "" # "Tool potential:" paragraph

    def topic_slug(self) -> str:
        """Return a filename-safe lowercase slug for the title."""
        slug = re.sub(r"[^a-z0-9]+", "_", self.title.lower()).strip("_")
        return slug or f"angle_{self.number}"


@dataclass
class DraftSummary:
    """Minimal read of an existing draft's frontmatter."""

    thread_number: Optional[int]
    target_post_date: Optional[date]


# ---------------------------------------------------------------------------
# Angle parsing

# "## 12. Title Goes Here" — numbered level-2 heading.
_ANGLE_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")

# "**N-CEN Fields:** ..." / "**The angle:** ..." etc.
_FIELD_LABELS = {
    "fields": re.compile(r"^\*\*N-CEN Fields?:\*\*\s*(.*)$"),
    "angle": re.compile(r"^\*\*The angle:\*\*\s*(.*)$"),
    "conflict": re.compile(r"^\*\*Conflict of interest story:\*\*\s*(.*)$"),
    "content_hook": re.compile(r"^\*\*Content hook:\*\*\s*(.*)$"),
    "tool_potential": re.compile(r"^\*\*Tool potential:\*\*\s*(.*)$"),
}


def parse_angles(markdown: str) -> list[Angle]:
    """Parse a novel-angles markdown file into a list of Angle records.

    Accepts markdown with level-2 numbered headings followed by any
    combination of the five bolded field labels. Unrecognized paragraph
    body between label lines is dropped -- the label's paragraph runs
    from the label through the next blank line.
    """
    angles: list[Angle] = []
    lines = markdown.splitlines()
    i = 0
    current: Optional[Angle] = None
    current_label: Optional[str] = None
    buffer: list[str] = []

    def flush_buffer() -> None:
        if current is None or current_label is None:
            return
        text = " ".join(line.strip() for line in buffer).strip()
        if text:
            setattr(current, current_label, text)

    while i < len(lines):
        line = lines[i]
        heading_match = _ANGLE_HEADING_RE.match(line)
        if heading_match:
            flush_buffer()
            buffer = []
            current_label = None
            try:
                number = int(heading_match.group(1))
            except ValueError:
                i += 1
                continue
            current = Angle(number=number, title=heading_match.group(2).strip())
            angles.append(current)
            i += 1
            continue

        if current is not None:
            label_hit = None
            for label_key, pattern in _FIELD_LABELS.items():
                m = pattern.match(line.strip())
                if m:
                    label_hit = (label_key, m.group(1).strip())
                    break

            if label_hit:
                flush_buffer()
                current_label = label_hit[0]
                buffer = [label_hit[1]] if label_hit[1] else []
                i += 1
                # Absorb continuation lines until a blank line or a new label.
                while i < len(lines):
                    next_line = lines[i]
                    if not next_line.strip():
                        break
                    if _ANGLE_HEADING_RE.match(next_line):
                        break
                    if any(p.match(next_line.strip()) for p in _FIELD_LABELS.values()):
                        break
                    buffer.append(next_line)
                    i += 1
                continue

        i += 1

    flush_buffer()

    # Skip section 10 ("Expense Anchor and Composite Scorecard Alignment").
    # It is the anchor dimension, not a standalone thread, and the series
    # capstone (thread 11) covers it via the working paper. The generator
    # must never produce a thread for the anchor.
    return [a for a in angles if a.number != 10]


# ---------------------------------------------------------------------------
# Draft inventory

# Filename pattern: YYYY-MM-DD_thread_NN_slug.md
_DRAFT_FILE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_thread_(\d+)_[a-z0-9_]+\.md$",
    re.IGNORECASE,
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_THREAD_NUMBER_KEY_RE = re.compile(r"^thread_number:\s*(\d+)\s*$", re.MULTILINE)
_TARGET_DATE_KEY_RE = re.compile(
    r"^target_post_date:\s*(\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)


def summarize_draft(path: Path) -> DraftSummary:
    """Return the thread_number and target_post_date for a draft file.

    Falls back to the filename's number/date components when the
    frontmatter is missing or malformed. This keeps filename-based
    accounting usable even when a draft is hand-edited.
    """
    thread_number: Optional[int] = None
    target_post_date: Optional[date] = None

    fname_match = _DRAFT_FILE_RE.match(path.name)
    if fname_match:
        try:
            target_post_date = date.fromisoformat(fname_match.group(1))
        except ValueError:
            pass
        try:
            thread_number = int(fname_match.group(2))
        except ValueError:
            pass

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return DraftSummary(thread_number, target_post_date)

    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        fm = fm_match.group(1)
        tn = _THREAD_NUMBER_KEY_RE.search(fm)
        if tn:
            try:
                thread_number = int(tn.group(1))
            except ValueError:
                pass
        td = _TARGET_DATE_KEY_RE.search(fm)
        if td:
            try:
                target_post_date = date.fromisoformat(td.group(1))
            except ValueError:
                pass

    return DraftSummary(thread_number, target_post_date)


def inventory_drafts(drafts_root: Path) -> list[DraftSummary]:
    """Return DraftSummary for every .md draft in every lifecycle folder.

    The lifecycle folders are pending/, approved/, published/, killed/.
    A draft that has moved to approved/ or published/ still counts as
    "thread number taken" -- the generator must skip that number.
    """
    folders = ("pending", "approved", "published", "killed")
    summaries: list[DraftSummary] = []
    for folder_name in folders:
        folder = drafts_root / folder_name
        if not folder.is_dir():
            continue
        for md in folder.glob("*.md"):
            summaries.append(summarize_draft(md))
    return summaries


def choose_next_thread_number(
    drafts: Iterable[DraftSummary],
    min_number: int = _MIN_GENERATED_THREAD_NUMBER,
) -> int:
    """Return the lowest thread number not already taken and at least
    as large as `min_number`. The floor protects the hand-drafted
    threads from being overwritten by the generator.
    """
    taken = {d.thread_number for d in drafts if d.thread_number is not None}
    candidate = min_number
    while candidate in taken:
        candidate += 1
    return candidate


def choose_target_post_date(
    drafts: Iterable[DraftSummary],
    today: Optional[date] = None,
    weeks_between: int = _WEEKS_BETWEEN_THREADS,
) -> date:
    """Return the Sunday target date for the next thread.

    Picks the Sunday that is N weeks after the latest already-scheduled
    target date, falling back to the next Sunday after `today` when no
    prior targets exist. Existing drafts already respect a Sunday
    cadence, so the generator preserves it.
    """
    today = today or date.today()
    dates = [d.target_post_date for d in drafts if d.target_post_date is not None]
    if dates:
        anchor = max(dates)
        return anchor + timedelta(weeks=weeks_between)
    return _next_sunday(today)


def _next_sunday(d: date) -> date:
    # Python's weekday(): Monday=0, Sunday=6.
    days_ahead = (6 - d.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return d + timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# Draft scaffolding

def _first_sentences(text: str, n: int = 2) -> str:
    """Return the first `n` sentences of a paragraph, or the whole text
    if it has fewer sentences. Used to populate tweet-body scaffolds
    from the angle's structured content.
    """
    if not text:
        return ""
    # Split on sentence-ending punctuation followed by whitespace.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    taken = parts[:n]
    return " ".join(taken).strip()


def _slug_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _prefix(label: str) -> str:
    return f"**{label}:**"


def render_draft(
    angle: Angle,
    thread_number: int,
    target_post_date: date,
    drafted_today: Optional[date] = None,
) -> str:
    """Render a full pending-draft markdown document for the given angle.

    The output matches the structure of the hand-drafted threads 4-11.
    Prose is scaffolded from the angle's structured content, with a
    stub tag that tells the reviewer the body still needs a human pass
    before publish.
    """
    drafted_today = drafted_today or date.today()
    slug = angle.topic_slug()
    pitch = (
        f"Thread {thread_number}. "
        + (angle.content_hook or angle.angle or angle.fields)
    ).strip()
    # Truncate the pitch so it fits on a single frontmatter line without
    # tripping YAML's unquoted-string limits.
    if len(pitch) > 320:
        pitch = pitch[:317].rstrip() + "..."

    frontmatter = [
        "---",
        "status: pending",
        f"drafted: {_slug_date(drafted_today)}",
        f"target_post_date: {_slug_date(target_post_date)}",
        f"thread_number: {thread_number}",
        "series: N-CEN novel angles (extended)",
        f"topic: {angle.title}",
        f'one_line_pitch: "{pitch}"',
        "source_docs:",
        f"  - docs/ncen_novel_angles.md section {angle.number}",
        "  - docs/ncen_novel_angles_extension.md (if present)",
        f"  - Fund Autopsy parser coverage for {angle.title.lower()}",
        "graphic_spec: text-only ship; graphic optional.",
        (
            "voice_note: Generator-scaffolded draft in the Baldwin voice "
            "(academic register, complete sentences, no em-dashes between "
            "clauses, no first-person identifiers). Body prose still "
            "requires a human review pass before approve."
        ),
        "generator: fundautopsy.monitoring.thread_generator",
        "---",
        "",
        f"# Thread {thread_number}: {angle.title}",
        "",
    ]

    body_parts: list[str] = [
        "## Opener (pinned first tweet)",
        "",
        "```",
        _first_sentences(angle.angle or angle.fields, n=2)
            or f"{angle.title}: a disclosure dimension that sits in N-CEN and is not aggregated anywhere the retail investor can see it.",
        "```",
        "",
        "## Tweet 1",
        "",
        "```",
        _first_sentences(angle.fields, n=2) or f"{_prefix('N-CEN Fields')} [fill from docs/ncen_novel_angles.md section {angle.number}]",
        "```",
        "",
        "## Tweet 2",
        "",
        "```",
        _first_sentences(angle.angle, n=2) or "[fill: what the data actually contains and why it is measurable]",
        "```",
        "",
        "## Tweet 3",
        "",
        "```",
        _first_sentences(angle.conflict, n=2) or "[fill: the conflict-of-interest framing or the governance mismatch]",
        "```",
        "",
        "## Tweet 4",
        "",
        "```",
        _first_sentences(angle.tool_potential, n=2) or "[fill: how Fund Autopsy measures this dimension and surfaces it to shareholders]",
        "```",
        "",
        "## Tweet 5",
        "",
        "```",
        (angle.content_hook or "[fill: the industry-scale range or the headline number].").strip(),
        "```",
        "",
        "## Tweet 6",
        "",
        "```",
        (
            "The data has been in N-CEN since 2018. The aggregation has not been done at "
            "industry scale. Fund Autopsy is doing it in public.\n\n"
            "github.com/Tombstone-Research/fund-autopsy\n\n"
            f"Thread {thread_number} of the N-CEN novel-angles series."
        ),
        "```",
        "",
        "---",
        "",
        "## Citations and source validation",
        "",
        f"- **docs/ncen_novel_angles.md section {angle.number}** — canonical angle definition for {angle.title}.",
        "- **SEC Form N-CEN instructions** — verify the specific item number(s) referenced in Tweet 1 before publishing.",
        "- **Fund Autopsy parser reference** — confirm the parser actually extracts the fields cited; if not, soften the claim.",
        "",
        "## Pre-publish checks",
        "",
        "- [ ] AUTO-GEN STUB: review every tweet body and rewrite for the Baldwin voice. The generator extracted structured claims from the angle file but did not authored the rhetorical sequencing.",
        "- [ ] Confirm the Fund Autopsy parser actually extracts the N-CEN fields cited. If not, rephrase to \"we're adding this parser in the next release\".",
        "- [ ] Verify any industry-scale quantitative claim against a live filing before publishing.",
        "- [ ] Ensure no named fund family appears without the underlying N-CEN or N-PX filing cited.",
        "",
        "## Phone-review summary (operator view)",
        "",
        (
            f"Thread {thread_number} of the N-CEN novel-angles extended series -- {angle.title}. "
            f"Scaffolded by the Sunday-overnight generator from "
            f"docs/ncen_novel_angles.md section {angle.number}. Six posts, opener plus "
            "five tweets plus closing CTA. Body prose is first-pass and needs a "
            "human review before approve. The structural claims (fields, angle, "
            "conflict framing, tool scope) are pulled from the canonical angle "
            "file so the scaffold is factually grounded."
        ),
        "",
        "**Approve:** move file to `content/drafts/approved/`",
        "**Kill:** move file to `content/drafts/killed/` with one-line reason",
        "",
    ]

    return "\n".join(frontmatter) + "\n".join(body_parts)


def draft_filename(
    thread_number: int,
    target_post_date: date,
    angle: Angle,
) -> str:
    return (
        f"{_slug_date(target_post_date)}_thread_{thread_number:02d}_{angle.topic_slug()}.md"
    )


# ---------------------------------------------------------------------------
# Pipeline entry point

@dataclass
class GeneratorOutcome:
    """Structured return from `generate_next_thread` for test assertions."""

    kind: str  # "wrote", "no_angle", "no_floor", "error"
    path: Optional[Path] = None
    thread_number: Optional[int] = None
    angle_number: Optional[int] = None
    reason: str = ""


def generate_next_thread(
    angles_paths: Iterable[Path],
    drafts_root: Path,
    today: Optional[date] = None,
) -> GeneratorOutcome:
    """Generate the next scheduled thread from the angle backlog.

    Args:
        angles_paths: Paths to markdown backlog files. The first
            existing file's angles appear first; later files extend
            the backlog. Missing files are skipped silently, which
            matches the optional nature of the extension file.
        drafts_root: `content/drafts/` directory. Expected to contain
            pending/, approved/, published/, killed/ subfolders.
        today: Override for deterministic testing; defaults to
            `date.today()` at runtime.

    Returns:
        GeneratorOutcome describing whether a draft was written, or
        why not.
    """
    today = today or date.today()

    # Parse angles in order, deduping on number so a duplicate section
    # number in an extension file does not produce two drafts for the
    # same angle.
    all_angles: dict[int, Angle] = {}
    for angle_path in angles_paths:
        if not angle_path.exists():
            continue
        try:
            text = angle_path.read_text(encoding="utf-8")
        except OSError as exc:
            return GeneratorOutcome(
                "error",
                reason=f"could not read {angle_path}: {exc}",
            )
        for angle in parse_angles(text):
            if angle.number not in all_angles:
                all_angles[angle.number] = angle

    if not all_angles:
        return GeneratorOutcome(
            "error",
            reason="no angles parsed from any configured backlog file",
        )

    pending_dir = drafts_root / "pending"
    if not pending_dir.is_dir():
        return GeneratorOutcome(
            "error",
            reason=f"drafts directory missing: {pending_dir}",
        )

    drafts = inventory_drafts(drafts_root)
    next_thread_number = choose_next_thread_number(drafts)

    # Every previously-used angle number is off limits so the generator
    # does not produce a second thread 12 if one already exists. The
    # hand-drafted threads use angles 1-9; thread 11 aggregates the
    # scorecard. Generator threads (12+) target angle numbers that are
    # still unused.
    used_angle_numbers: set[int] = set()
    for draft_summary in drafts:
        if draft_summary.thread_number is None:
            continue
        # Heuristic mapping: hand-drafted threads 2-10 map to angle numbers
        # 1-9 (expense anchor is angle 10, covered by thread 11's capstone).
        # Generator-authored threads are 12+ and use angles starting at 11.
        if draft_summary.thread_number <= 11:
            # Hand-drafted — no generator overlap possible, so do not
            # pollute `used_angle_numbers` with guesses.
            continue

    candidate_angle_numbers = sorted(
        n for n in all_angles
        if n not in used_angle_numbers
    )
    # Floor generator output at angle 11 so we do not rewrite a hand-
    # drafted angle. (Angles 1-9 are threads 2-9/10; angle 10 is the
    # anchor and covered by thread 11.)
    candidate_angle_numbers = [n for n in candidate_angle_numbers if n >= 11]

    # Skip any angle that shows up in an already-generated thread's
    # frontmatter source_docs pointer.
    consumed = _consumed_angle_numbers(drafts_root)
    candidate_angle_numbers = [n for n in candidate_angle_numbers if n not in consumed]

    if not candidate_angle_numbers:
        return GeneratorOutcome(
            "no_angle",
            reason=(
                "no unused angles in docs/ncen_novel_angles.md or the "
                "extension file. Add a new section to the extension file "
                "before re-running the generator."
            ),
        )

    chosen = all_angles[candidate_angle_numbers[0]]
    target = choose_target_post_date(drafts, today=today)
    filename = draft_filename(next_thread_number, target, chosen)
    path = pending_dir / filename
    if path.exists():
        return GeneratorOutcome(
            "no_floor",
            reason=(
                f"would write {filename}, but that path already exists. "
                "Move or rename the existing file before re-running."
            ),
        )

    content = render_draft(chosen, next_thread_number, target, drafted_today=today)
    path.write_text(content, encoding="utf-8")
    return GeneratorOutcome(
        kind="wrote",
        path=path,
        thread_number=next_thread_number,
        angle_number=chosen.number,
    )


_ANGLE_SOURCE_DOC_RE = re.compile(
    r"docs/ncen_novel_angles(?:_extension)?\.md\s+section\s+(\d+)",
    re.IGNORECASE,
)


def _consumed_angle_numbers(drafts_root: Path) -> set[int]:
    """Return the set of angle numbers already referenced by any draft's
    frontmatter source_docs block. Scans every lifecycle folder.
    """
    consumed: set[int] = set()
    for folder_name in ("pending", "approved", "published", "killed"):
        folder = drafts_root / folder_name
        if not folder.is_dir():
            continue
        for md in folder.glob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = _FRONTMATTER_RE.match(text)
            if not fm:
                continue
            for m in _ANGLE_SOURCE_DOC_RE.finditer(fm.group(1)):
                try:
                    consumed.add(int(m.group(1)))
                except ValueError:
                    continue
    return consumed


# ---------------------------------------------------------------------------
# CLI

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the next scheduled Tombstone Research thread",
    )
    parser.add_argument(
        "--angles",
        default=str(_DEFAULT_ANGLES_PATH),
        help="Path to the primary novel-angles markdown file.",
    )
    parser.add_argument(
        "--extension",
        default=str(_DEFAULT_EXTENSION_PATH),
        help=(
            "Path to the optional angles-extension markdown file. "
            "Missing files are skipped silently."
        ),
    )
    parser.add_argument(
        "--drafts-root",
        default=str(_DEFAULT_DRAFTS_ROOT),
        help="Path to the content/drafts/ directory (contains pending/, approved/, etc.).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    _configure_logging()
    args = _build_argparser().parse_args(argv)

    outcome = generate_next_thread(
        angles_paths=[Path(args.angles), Path(args.extension)],
        drafts_root=Path(args.drafts_root),
    )
    if outcome.kind == "wrote":
        logger.info(
            "Wrote thread %s (angle %s) to %s",
            outcome.thread_number, outcome.angle_number, outcome.path,
        )
        return 0
    if outcome.kind == "no_angle":
        logger.info("No new thread generated: %s", outcome.reason)
        return 0
    if outcome.kind == "no_floor":
        logger.warning("Blocked: %s", outcome.reason)
        return 0
    logger.error("Generator error: %s", outcome.reason)
    return 1


if __name__ == "__main__":
    sys.exit(main())
