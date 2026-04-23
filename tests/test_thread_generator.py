"""Tests for the N-CEN thread generator.

Exercises the pure-text helpers in
`fundautopsy.monitoring.thread_generator` and the integration entry
point `generate_next_thread`, using `tmp_path` for filesystem state.
The generator runs under a Sunday-overnight scheduled task, so the
tests guard against three specific failure modes:

1. Rewriting a hand-drafted thread (threads 1-11 are authored by hand).
2. Double-drafting the same angle number across two generator runs.
3. Producing a noisy error when the angle backlog is exhausted.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fundautopsy.monitoring import thread_generator as tg
from fundautopsy.monitoring.thread_generator import (
    Angle,
    DraftSummary,
    GeneratorOutcome,
    choose_next_thread_number,
    choose_target_post_date,
    draft_filename,
    generate_next_thread,
    inventory_drafts,
    main,
    parse_angles,
    render_draft,
    summarize_draft,
    _consumed_angle_numbers,
    _first_sentences,
    _next_sunday,
)


# ---------------------------------------------------------------------------
# Angle fixture. Models the shape of docs/ncen_novel_angles.md: a level-2
# numbered heading followed by five bolded field labels with paragraph
# bodies. Includes angle 10 (the expense anchor) so we can confirm the
# parser drops it, and two higher-numbered angles the generator would
# legitimately produce threads for.

_ANGLES_MARKDOWN = """# N-CEN Novel Angles

Some prose preamble that the parser must ignore.

## 1. Soft Dollar Disclosure

**N-CEN Fields:** Item C.7 reports soft-dollar arrangements.

**The angle:** Funds disclose commission-sharing arrangements that
fund research and data. The aggregate dollar amount has grown despite
an industry narrative of cost discipline.

**Conflict of interest story:** The adviser directs brokerage to
affiliated or preferred brokers; the cost is borne by fund
shareholders rather than the adviser.

**Content hook:** Industry-scale soft-dollar spend ranges from
$X million to $Y million annually.

**Tool potential:** Parse Item C.7 across every N-CEN filing and rank
by soft-dollar intensity.

## 10. Expense Anchor and Composite Scorecard Alignment

**The angle:** The anchor dimension against which every other angle
is indexed.

**Tool potential:** Capstone scorecard; not a standalone thread.

## 11. Liquidity Classification Drift

**N-CEN Fields:** Item B.5 reports the fund's liquidity risk
management program classifications.

**The angle:** Funds reclassify holdings between liquidity buckets
over time. The pattern and frequency of reclassification is a
governance signal that no aggregator exposes.

**Conflict of interest story:** A fund under shareholder redemption
pressure has a direct incentive to mark less-liquid holdings as more
liquid than they trade.

**Content hook:** Liquidity-bucket drift is measurable in N-CEN Item
B.5 across every annual filing.

**Tool potential:** Parse B.5 across three years of filings and
compute bucket migration by CUSIP.

## 12. Custodian Affiliation

**N-CEN Fields:** Item C.6 reports each custodian and whether it is
affiliated with the adviser.

**The angle:** Affiliated custodians collect fees that are a second
layer on top of the adviser's management fee. The disclosure exists
but no aggregator surfaces it.

**Conflict of interest story:** The adviser selects an affiliated
custodian and thereby routes more revenue to the parent.

**Content hook:** A meaningful fraction of funds use an affiliated
custodian; shareholders are not told about the fee impact.

**Tool potential:** Join Item C.6 against the SEC adviser registry
to quantify affiliated-custodian fee leakage.
"""


# ---------------------------------------------------------------------------
# Angle dataclass

def test_topic_slug_lowercases_and_replaces_non_alnum():
    angle = Angle(number=12, title="Custodian Affiliation (Item C.6)")
    assert angle.topic_slug() == "custodian_affiliation_item_c_6"


def test_topic_slug_falls_back_to_angle_number_when_title_has_no_alnum():
    angle = Angle(number=42, title="----")
    assert angle.topic_slug() == "angle_42"


# ---------------------------------------------------------------------------
# parse_angles

def test_parse_angles_returns_expected_angle_count_and_skips_10():
    angles = parse_angles(_ANGLES_MARKDOWN)
    numbers = [a.number for a in angles]
    assert numbers == [1, 11, 12]


def test_parse_angles_extracts_all_five_field_labels():
    angles = parse_angles(_ANGLES_MARKDOWN)
    soft_dollar = next(a for a in angles if a.number == 1)
    assert "Item C.7" in soft_dollar.fields
    assert "commission-sharing" in soft_dollar.angle
    assert "affiliated or preferred brokers" in soft_dollar.conflict
    assert "$X million" in soft_dollar.content_hook
    assert "Parse Item C.7" in soft_dollar.tool_potential


def test_parse_angles_preserves_paragraph_text_across_wrapped_lines():
    """Two-line paragraph bodies must be joined with a single space."""
    angles = parse_angles(_ANGLES_MARKDOWN)
    liquidity = next(a for a in angles if a.number == 11)
    # The paragraph wraps "signal that no aggregator exposes." across
    # two source lines; joined text should contain both halves with a
    # single space separator.
    assert "governance signal that no aggregator exposes" in liquidity.angle


def test_parse_angles_skips_angle_ten_expense_anchor():
    angles = parse_angles(_ANGLES_MARKDOWN)
    assert all(a.number != 10 for a in angles), "expense anchor must never be selected"


def test_parse_angles_handles_empty_input():
    assert parse_angles("") == []


def test_parse_angles_handles_heading_without_fields():
    md = "## 99. Standalone Heading With No Fields\n\nSome prose.\n"
    angles = parse_angles(md)
    assert len(angles) == 1
    assert angles[0].number == 99
    assert angles[0].title == "Standalone Heading With No Fields"
    assert angles[0].fields == ""


# ---------------------------------------------------------------------------
# summarize_draft and filename parsing

_FRONTMATTER_DRAFT = """---
status: pending
drafted: 2026-04-20
target_post_date: 2026-05-03
thread_number: 12
series: N-CEN novel angles (extended)
topic: Custodian Affiliation
one_line_pitch: "Thread 12 test"
source_docs:
  - docs/ncen_novel_angles.md section 12
---

# Thread 12: Custodian Affiliation
"""


def test_summarize_draft_reads_frontmatter(tmp_path):
    path = tmp_path / "2026-05-03_thread_12_custodian_affiliation.md"
    path.write_text(_FRONTMATTER_DRAFT, encoding="utf-8")
    summary = summarize_draft(path)
    assert summary.thread_number == 12
    assert summary.target_post_date == date(2026, 5, 3)


def test_summarize_draft_falls_back_to_filename_when_no_frontmatter(tmp_path):
    path = tmp_path / "2026-05-10_thread_13_test_slug.md"
    path.write_text("No frontmatter here.\n", encoding="utf-8")
    summary = summarize_draft(path)
    assert summary.thread_number == 13
    assert summary.target_post_date == date(2026, 5, 10)


def test_summarize_draft_frontmatter_overrides_filename(tmp_path):
    """If frontmatter disagrees with the filename, frontmatter wins."""
    path = tmp_path / "2026-05-10_thread_13_custodian.md"
    path.write_text(_FRONTMATTER_DRAFT, encoding="utf-8")
    summary = summarize_draft(path)
    # Frontmatter values override the filename's 13/2026-05-10.
    assert summary.thread_number == 12
    assert summary.target_post_date == date(2026, 5, 3)


def test_summarize_draft_returns_none_fields_on_unparseable_filename(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("loose notes, no structure", encoding="utf-8")
    summary = summarize_draft(path)
    assert summary.thread_number is None
    assert summary.target_post_date is None


# ---------------------------------------------------------------------------
# inventory_drafts

def _write_draft(folder: Path, name: str, thread_number: int, target_date: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    fm = (
        "---\n"
        f"thread_number: {thread_number}\n"
        f"target_post_date: {target_date}\n"
        "---\n"
        "body"
    )
    path.write_text(fm, encoding="utf-8")
    return path


def test_inventory_drafts_scans_all_lifecycle_folders(tmp_path):
    drafts_root = tmp_path / "drafts"
    _write_draft(drafts_root / "pending", "2026-04-26_thread_04_p.md", 4, "2026-04-26")
    _write_draft(drafts_root / "approved", "2026-04-19_thread_03_a.md", 3, "2026-04-19")
    _write_draft(drafts_root / "published", "2026-04-12_thread_02_pub.md", 2, "2026-04-12")
    _write_draft(drafts_root / "killed", "2026-04-05_thread_01_k.md", 1, "2026-04-05")
    summaries = inventory_drafts(drafts_root)
    assert sorted(s.thread_number for s in summaries) == [1, 2, 3, 4]


def test_inventory_drafts_handles_missing_lifecycle_folders(tmp_path):
    drafts_root = tmp_path / "drafts"
    _write_draft(drafts_root / "pending", "2026-04-26_thread_04_p.md", 4, "2026-04-26")
    # No approved/published/killed folders — should still succeed.
    summaries = inventory_drafts(drafts_root)
    assert [s.thread_number for s in summaries] == [4]


def test_inventory_drafts_returns_empty_for_nonexistent_root(tmp_path):
    summaries = inventory_drafts(tmp_path / "does_not_exist")
    assert summaries == []


# ---------------------------------------------------------------------------
# choose_next_thread_number

def test_choose_next_thread_number_respects_floor():
    drafts = [DraftSummary(thread_number=n, target_post_date=None) for n in (1, 2, 3)]
    # Floor at 12; none of the taken numbers collide.
    assert choose_next_thread_number(drafts) == 12


def test_choose_next_thread_number_skips_taken_numbers_at_or_above_floor():
    drafts = [DraftSummary(thread_number=n, target_post_date=None) for n in (1, 12, 13)]
    assert choose_next_thread_number(drafts) == 14


def test_choose_next_thread_number_handles_none_entries():
    drafts = [
        DraftSummary(thread_number=None, target_post_date=None),
        DraftSummary(thread_number=12, target_post_date=None),
    ]
    assert choose_next_thread_number(drafts) == 13


def test_choose_next_thread_number_with_empty_list():
    assert choose_next_thread_number([]) == 12


def test_choose_next_thread_number_custom_floor():
    drafts = [DraftSummary(thread_number=20, target_post_date=None)]
    assert choose_next_thread_number(drafts, min_number=20) == 21


# ---------------------------------------------------------------------------
# choose_target_post_date and _next_sunday

def test_next_sunday_from_monday_returns_following_sunday():
    # 2026-04-20 is a Monday (weekday=0).
    monday = date(2026, 4, 20)
    assert _next_sunday(monday) == date(2026, 4, 26)


def test_next_sunday_from_sunday_returns_next_sunday_not_today():
    # 2026-04-26 is a Sunday (weekday=6).
    sunday = date(2026, 4, 26)
    assert _next_sunday(sunday) == date(2026, 5, 3)


def test_next_sunday_from_saturday_returns_tomorrow():
    # 2026-04-25 is a Saturday (weekday=5).
    saturday = date(2026, 4, 25)
    assert _next_sunday(saturday) == date(2026, 4, 26)


def test_choose_target_post_date_adds_one_week_to_latest_existing():
    drafts = [
        DraftSummary(thread_number=4, target_post_date=date(2026, 4, 26)),
        DraftSummary(thread_number=5, target_post_date=date(2026, 5, 3)),
        DraftSummary(thread_number=6, target_post_date=date(2026, 5, 10)),
    ]
    # Latest is 2026-05-10 (Sunday); +1 week = 2026-05-17.
    assert choose_target_post_date(drafts, today=date(2026, 5, 1)) == date(2026, 5, 17)


def test_choose_target_post_date_falls_back_to_next_sunday_when_no_drafts():
    # 2026-04-22 is a Wednesday; next Sunday is 2026-04-26.
    target = choose_target_post_date([], today=date(2026, 4, 22))
    assert target == date(2026, 4, 26)


def test_choose_target_post_date_ignores_drafts_without_target_date():
    drafts = [
        DraftSummary(thread_number=4, target_post_date=None),
        DraftSummary(thread_number=5, target_post_date=date(2026, 4, 26)),
    ]
    assert choose_target_post_date(drafts, today=date(2026, 4, 1)) == date(2026, 5, 3)


# ---------------------------------------------------------------------------
# _first_sentences

def test_first_sentences_returns_up_to_n_sentences():
    text = "Sentence one. Sentence two. Sentence three."
    assert _first_sentences(text, n=2) == "Sentence one. Sentence two."


def test_first_sentences_returns_full_text_when_fewer_than_n():
    text = "Only one sentence here."
    assert _first_sentences(text, n=3) == "Only one sentence here."


def test_first_sentences_returns_empty_string_on_empty_input():
    assert _first_sentences("", n=2) == ""


def test_first_sentences_handles_text_without_sentence_terminators():
    text = "no terminating punctuation"
    assert _first_sentences(text, n=2) == "no terminating punctuation"


# ---------------------------------------------------------------------------
# draft_filename

def test_draft_filename_composes_date_thread_and_slug():
    angle = Angle(number=12, title="Custodian Affiliation")
    fname = draft_filename(12, date(2026, 5, 17), angle)
    assert fname == "2026-05-17_thread_12_custodian_affiliation.md"


def test_draft_filename_zero_pads_thread_number():
    angle = Angle(number=5, title="Soft Dollar")
    fname = draft_filename(7, date(2026, 6, 1), angle)
    assert "_thread_07_" in fname


# ---------------------------------------------------------------------------
# render_draft

def _sample_angle() -> Angle:
    return Angle(
        number=12,
        title="Custodian Affiliation",
        fields="Item C.6 reports custodian affiliation.",
        angle="Affiliated custodians charge a second fee layer that shareholders do not see.",
        conflict="The adviser routes fees to its parent via the custodial relationship.",
        content_hook="A meaningful fraction of funds use an affiliated custodian.",
        tool_potential="Fund Autopsy parses Item C.6 and surfaces the affiliation ratio.",
    )


def test_render_draft_includes_frontmatter_keys():
    draft = render_draft(
        _sample_angle(),
        thread_number=12,
        target_post_date=date(2026, 5, 17),
        drafted_today=date(2026, 4, 22),
    )
    assert "status: pending" in draft
    assert "drafted: 2026-04-22" in draft
    assert "target_post_date: 2026-05-17" in draft
    assert "thread_number: 12" in draft
    assert "topic: Custodian Affiliation" in draft
    assert "docs/ncen_novel_angles.md section 12" in draft
    assert "generator: fundautopsy.monitoring.thread_generator" in draft


def test_render_draft_includes_six_tweet_sections():
    draft = render_draft(
        _sample_angle(),
        thread_number=12,
        target_post_date=date(2026, 5, 17),
    )
    # Opener plus tweets 1-6.
    assert "## Opener" in draft
    for i in range(1, 7):
        assert f"## Tweet {i}" in draft


def test_render_draft_includes_prepublish_and_phone_review_blocks():
    draft = render_draft(
        _sample_angle(),
        thread_number=12,
        target_post_date=date(2026, 5, 17),
    )
    assert "## Pre-publish checks" in draft
    assert "## Phone-review summary" in draft
    assert "AUTO-GEN STUB" in draft


def test_render_draft_includes_voice_note_without_em_dashes_between_clauses():
    draft = render_draft(
        _sample_angle(),
        thread_number=12,
        target_post_date=date(2026, 5, 17),
    )
    assert "Baldwin voice" in draft
    assert "no em-dashes between" in draft


def test_render_draft_includes_citations_section_with_angle_reference():
    draft = render_draft(
        _sample_angle(),
        thread_number=12,
        target_post_date=date(2026, 5, 17),
    )
    assert "## Citations and source validation" in draft
    assert "docs/ncen_novel_angles.md section 12" in draft


def test_render_draft_truncates_overlong_pitch():
    long_hook = "Extremely long content hook. " * 30
    angle = Angle(number=99, title="Long Hook", content_hook=long_hook)
    draft = render_draft(angle, thread_number=12, target_post_date=date(2026, 5, 17))
    # Pitch line is wrapped in double quotes; find it.
    pitch_line = next(
        line for line in draft.splitlines() if line.startswith("one_line_pitch:")
    )
    # Full pitch would be much longer than 320 chars; truncated version
    # must end with the ellipsis and total under 340 including the key.
    assert "..." in pitch_line
    assert len(pitch_line) < 340


# ---------------------------------------------------------------------------
# _consumed_angle_numbers

def test_consumed_angle_numbers_extracts_from_pending_folder(tmp_path):
    drafts_root = tmp_path / "drafts"
    pending = drafts_root / "pending"
    pending.mkdir(parents=True)
    (pending / "2026-05-17_thread_12_x.md").write_text(
        "---\nsource_docs:\n  - docs/ncen_novel_angles.md section 12\n---\nbody",
        encoding="utf-8",
    )
    assert _consumed_angle_numbers(drafts_root) == {12}


def test_consumed_angle_numbers_scans_all_lifecycle_folders(tmp_path):
    drafts_root = tmp_path / "drafts"
    for folder_name, section in (("pending", 11), ("approved", 12), ("published", 13), ("killed", 14)):
        folder = drafts_root / folder_name
        folder.mkdir(parents=True)
        (folder / f"2026-01-01_thread_{section}_x.md").write_text(
            f"---\nsource_docs:\n  - docs/ncen_novel_angles.md section {section}\n---\n",
            encoding="utf-8",
        )
    assert _consumed_angle_numbers(drafts_root) == {11, 12, 13, 14}


def test_consumed_angle_numbers_picks_up_extension_file_reference(tmp_path):
    drafts_root = tmp_path / "drafts"
    pending = drafts_root / "pending"
    pending.mkdir(parents=True)
    (pending / "2026-05-17_thread_12_x.md").write_text(
        "---\nsource_docs:\n  - docs/ncen_novel_angles_extension.md section 15\n---\nbody",
        encoding="utf-8",
    )
    assert _consumed_angle_numbers(drafts_root) == {15}


def test_consumed_angle_numbers_returns_empty_when_no_drafts(tmp_path):
    drafts_root = tmp_path / "drafts"
    (drafts_root / "pending").mkdir(parents=True)
    assert _consumed_angle_numbers(drafts_root) == set()


# ---------------------------------------------------------------------------
# generate_next_thread — integration

def _setup_workspace(tmp_path: Path, angles_md: str = _ANGLES_MARKDOWN) -> tuple[Path, Path]:
    """Create a minimal workspace with an angles file and a drafts root.

    Returns (angles_path, drafts_root).
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    angles_path = docs / "ncen_novel_angles.md"
    angles_path.write_text(angles_md, encoding="utf-8")

    drafts_root = tmp_path / "content" / "drafts"
    for folder in ("pending", "approved", "published", "killed"):
        (drafts_root / folder).mkdir(parents=True)
    return angles_path, drafts_root


def test_generate_next_thread_writes_draft_when_angle_available(tmp_path):
    angles_path, drafts_root = _setup_workspace(tmp_path)
    outcome = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "wrote"
    assert outcome.thread_number == 12
    # First unused angle at or above 11 — angle 11 (liquidity drift).
    assert outcome.angle_number == 11
    assert outcome.path is not None
    assert outcome.path.exists()
    # The filename slug comes from angle 11's title.
    assert "thread_12_liquidity_classification_drift" in outcome.path.name


def test_generate_next_thread_returns_no_angle_when_backlog_exhausted(tmp_path):
    # Angles 1-10 do not count (angles 1-9 map to hand-drafted threads, 10 is anchor).
    # The generator only draws from angle 11+.
    md = "## 1. Soft Dollars\n\n**The angle:** text.\n"
    angles_path, drafts_root = _setup_workspace(tmp_path, angles_md=md)
    outcome = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "no_angle"
    assert "no unused angles" in outcome.reason


def test_generate_next_thread_skips_consumed_angles(tmp_path):
    angles_path, drafts_root = _setup_workspace(tmp_path)
    # Seed a pending draft that has already consumed angle 11.
    (drafts_root / "pending" / "2026-05-17_thread_12_prev.md").write_text(
        "---\n"
        "thread_number: 12\n"
        "target_post_date: 2026-05-17\n"
        "source_docs:\n  - docs/ncen_novel_angles.md section 11\n"
        "---\nbody",
        encoding="utf-8",
    )
    outcome = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    # Next available thread is 13, next available angle is 12.
    assert outcome.kind == "wrote"
    assert outcome.thread_number == 13
    assert outcome.angle_number == 12


def test_generate_next_thread_extends_via_optional_extension_file(tmp_path):
    # Primary angles file has only the hand-drafted span (angles 1 and 10).
    primary_md = (
        "## 1. Soft Dollars\n\n**The angle:** text.\n\n"
        "## 10. Expense Anchor\n\n**The angle:** text.\n"
    )
    angles_path, drafts_root = _setup_workspace(tmp_path, angles_md=primary_md)
    extension_path = tmp_path / "docs" / "ncen_novel_angles_extension.md"
    extension_path.write_text(
        "## 15. Derivative Counterparty Concentration\n\n"
        "**N-CEN Fields:** Item D.3.\n\n"
        "**The angle:** Single-counterparty concentration is disclosed but not aggregated.\n",
        encoding="utf-8",
    )
    outcome = generate_next_thread(
        angles_paths=[angles_path, extension_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "wrote"
    assert outcome.angle_number == 15


def test_generate_next_thread_errors_when_drafts_dir_missing(tmp_path):
    angles_path = tmp_path / "angles.md"
    angles_path.write_text(_ANGLES_MARKDOWN, encoding="utf-8")
    # Drafts root intentionally missing pending/.
    drafts_root = tmp_path / "content" / "drafts"
    outcome = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "error"
    assert "drafts directory missing" in outcome.reason


def test_generate_next_thread_errors_when_no_angles_parsed(tmp_path):
    angles_path, drafts_root = _setup_workspace(tmp_path, angles_md="no headings here\n")
    outcome = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "error"
    assert "no angles parsed" in outcome.reason


def test_generate_next_thread_skips_missing_angle_files(tmp_path):
    """A missing extension file is a silent skip, not a hard error."""
    angles_path, drafts_root = _setup_workspace(tmp_path)
    missing_extension = tmp_path / "docs" / "does_not_exist.md"
    outcome = generate_next_thread(
        angles_paths=[angles_path, missing_extension],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "wrote"


def test_generate_next_thread_advances_thread_number_across_runs(tmp_path):
    angles_path, drafts_root = _setup_workspace(tmp_path)
    first = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert first.kind == "wrote"
    assert first.thread_number == 12

    # Second run must pick thread 13 and angle 12 (custodian affiliation).
    second = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert second.kind == "wrote"
    assert second.thread_number == 13
    assert second.angle_number == 12


def test_generate_next_thread_never_overwrites_hand_drafted_threads(tmp_path):
    """Simulate the real-world state: threads 4-11 already exist as hand-drafted
    pending files. The generator must pick thread 12, never overwrite an
    existing thread number.
    """
    angles_path, drafts_root = _setup_workspace(tmp_path)
    for thread_num, offset in zip(range(4, 12), range(0, 8)):
        target = date(2026, 4, 26).toordinal() + offset * 7
        target_date = date.fromordinal(target)
        _write_draft(
            drafts_root / "pending",
            f"{target_date.isoformat()}_thread_{thread_num:02d}_x.md",
            thread_num,
            target_date.isoformat(),
        )
    outcome = generate_next_thread(
        angles_paths=[angles_path],
        drafts_root=drafts_root,
        today=date(2026, 4, 22),
    )
    assert outcome.kind == "wrote"
    assert outcome.thread_number == 12
    # Target should be one week after the latest existing draft.
    assert outcome.path is not None
    # Latest thread_11 target is 2026-04-26 + 7*7 = 2026-06-14; +1 week = 2026-06-21.
    assert "2026-06-21" in outcome.path.name


# ---------------------------------------------------------------------------
# CLI main()

def test_main_returns_zero_on_wrote_outcome(tmp_path, capsys):
    angles_path, drafts_root = _setup_workspace(tmp_path)
    exit_code = main([
        "--angles", str(angles_path),
        "--extension", str(tmp_path / "missing.md"),
        "--drafts-root", str(drafts_root),
    ])
    assert exit_code == 0
    # Generator wrote a new pending draft.
    pending_files = list((drafts_root / "pending").glob("*.md"))
    assert len(pending_files) == 1


def test_main_returns_zero_on_no_angle_outcome(tmp_path):
    """Backlog exhausted is a healthy outcome for the scheduled task."""
    angles_path, drafts_root = _setup_workspace(
        tmp_path,
        angles_md="## 1. Soft Dollars\n\n**The angle:** text.\n",
    )
    exit_code = main([
        "--angles", str(angles_path),
        "--extension", str(tmp_path / "missing.md"),
        "--drafts-root", str(drafts_root),
    ])
    assert exit_code == 0


def test_main_returns_one_on_hard_error(tmp_path):
    # Pass a bogus angles file and no extension; parse returns no angles.
    angles_path = tmp_path / "empty.md"
    angles_path.write_text("", encoding="utf-8")
    drafts_root = tmp_path / "content" / "drafts"
    for folder in ("pending", "approved", "published", "killed"):
        (drafts_root / folder).mkdir(parents=True)
    exit_code = main([
        "--angles", str(angles_path),
        "--extension", str(tmp_path / "missing.md"),
        "--drafts-root", str(drafts_root),
    ])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# GeneratorOutcome

def test_generator_outcome_defaults_populate_empty_fields():
    outcome = GeneratorOutcome(kind="no_angle", reason="backlog exhausted")
    assert outcome.path is None
    assert outcome.thread_number is None
    assert outcome.angle_number is None
    assert outcome.reason == "backlog exhausted"
