"""Tests for the development studio engine (archie/standalone/studio.py)."""
from __future__ import annotations

from pathlib import Path

from archie.standalone import studio


def test_parse_frontmatter_scalars_and_inline_list():
    text = (
        "---\n"
        "id: ISS-007\n"
        "title: Add upload resize\n"
        "status: planned\n"
        "labels: [backend, infra]\n"
        "type: feature\n"
        "---\n"
        "## Context\nbody here\n"
    )
    fm = studio.parse_frontmatter(text)
    assert fm["id"] == "ISS-007"
    assert fm["title"] == "Add upload resize"
    assert fm["status"] == "planned"
    assert fm["labels"] == ["backend", "infra"]
    assert fm["type"] == "feature"


def test_parse_frontmatter_returns_none_when_absent():
    assert studio.parse_frontmatter("no frontmatter here\n") is None


def test_statuses_constant():
    assert studio.STATUSES == [
        "planned",
        "in-progress",
        "in-review",
        "done",
        "blocked",
    ]


def _write_ticket(issues: Path, status: str, tid: str, **extra):
    folder = issues / status
    folder.mkdir(parents=True, exist_ok=True)
    fm_extra = "".join(f"{k}: {v}\n" for k, v in extra.items())
    (folder / f"{tid}-slug.md").write_text(
        f"---\nid: {tid}\ntitle: t\nstatus: {status}\n{fm_extra}---\n## Context\n"
    )


def test_iter_tickets_collects_across_status_folders(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "planned", "ISS-001")
    _write_ticket(issues, "done", "ISS-002")
    tickets = studio.iter_tickets(issues)
    ids = sorted(t["id"] for t in tickets)
    assert ids == ["ISS-001", "ISS-002"]


def test_iter_tickets_skips_corrupt_file(tmp_path: Path, capsys):
    issues = tmp_path / ".archie" / "issues"
    (issues / "planned").mkdir(parents=True)
    (issues / "planned" / "ISS-001-ok.md").write_text(
        "---\nid: ISS-001\nstatus: planned\n---\n"
    )
    (issues / "planned" / "garbage.md").write_text("no frontmatter\n")
    tickets = studio.iter_tickets(issues)
    assert [t["id"] for t in tickets] == ["ISS-001"]
    assert "skip" in capsys.readouterr().err.lower()


def test_next_id_finds_max_across_folders(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "planned", "ISS-003")
    _write_ticket(issues, "done", "ISS-011")
    _write_ticket(issues, "in-progress", "ISS-007")
    assert studio.next_id(studio.iter_tickets(issues), "ISS") == "ISS-012"


def test_next_id_first_when_empty():
    assert studio.next_id([], "ISS") == "ISS-001"


