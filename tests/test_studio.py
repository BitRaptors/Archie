"""Tests for the development studio engine (archie/standalone/studio.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

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


def test_render_index_contains_next_ids_and_tables(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "planned", "ISS-001", type="feature", labels="[backend]")
    _write_ticket(issues, "in-progress", "ISS-002", type="bugfix", labels="[frontend]")
    _write_ticket(issues, "done", "ISS-003", type="chore", labels="[infra]")
    tickets = studio.iter_tickets(issues)
    out = studio.render_index(tickets)
    assert "Next issue: ISS-004" in out
    assert "Next epic: EPIC-001" in out
    assert "ISS-001" in out and "ISS-002" in out  # active table
    assert "ISS-003" in out  # done table
    assert "## Active" in out and "## Done" in out


def test_render_index_lists_blocked_separately(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "blocked", "ISS-005")
    out = studio.render_index(studio.iter_tickets(issues))
    assert "## Blocked" in out
    assert "ISS-005" in out


def test_cmd_init_creates_structure(tmp_path: Path):
    studio.cmd_init(tmp_path)
    issues = tmp_path / ".archie" / "issues"
    for sub in studio.STATUSES + ["epics", "evidence"]:
        assert (issues / sub).is_dir(), f"missing {sub}"
    assert (issues / "_TEMPLATE.md").exists()
    assert (issues / "WORKFLOW.md").exists()
    assert (issues / "INDEX.md").exists()
    assert "ISS-NNN" in (issues / "_TEMPLATE.md").read_text()
    assert "Required Workflow" in (issues / "WORKFLOW.md").read_text()


def test_cmd_init_idempotent_keeps_tickets(tmp_path: Path):
    studio.cmd_init(tmp_path)
    issues = tmp_path / ".archie" / "issues"
    (issues / "planned" / "ISS-001-x.md").write_text(
        "---\nid: ISS-001\ntitle: keep\nstatus: planned\n---\n"
    )
    studio.cmd_init(tmp_path)  # re-run
    assert (issues / "planned" / "ISS-001-x.md").exists(), "init destroyed a ticket"


def test_patch_agents_md_creates_when_absent(tmp_path: Path):
    studio.patch_agents_md(tmp_path)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "ARCHIE:STUDIO:START" in content
    assert ".archie/issues/WORKFLOW.md" in content


def test_patch_agents_md_appends_to_existing(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Existing\nkeep me\n")
    studio.patch_agents_md(tmp_path)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "keep me" in content
    assert "ARCHIE:STUDIO:START" in content


def test_patch_agents_md_idempotent_replaces_block(tmp_path: Path):
    studio.patch_agents_md(tmp_path)
    studio.patch_agents_md(tmp_path)  # twice
    content = (tmp_path / "AGENTS.md").read_text()
    assert content.count("ARCHIE:STUDIO:START") == 1, "block was duplicated"


def test_cmd_new_creates_ticket_and_refreshes_index(tmp_path: Path):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="Add upload resize", type_="feature",
                         labels=["backend"], today="2026-06-15")
    assert tid == "ISS-001"
    issues = tmp_path / ".archie" / "issues"
    files = list((issues / "planned").glob("ISS-001-*.md"))
    assert len(files) == 1
    body = files[0].read_text()
    assert "id: ISS-001" in body
    assert "title: Add upload resize" in body
    assert "labels: [backend]" in body
    assert "ISS-001" in (issues / "INDEX.md").read_text()


def test_cmd_new_increments_id(tmp_path: Path):
    studio.cmd_init(tmp_path)
    studio.cmd_new(tmp_path, title="one", type_="feature", labels=[], today="2026-06-15")
    second = studio.cmd_new(tmp_path, title="two", type_="bugfix", labels=[], today="2026-06-15")
    assert second == "ISS-002"


def test_cmd_move_relocates_and_refreshes_index(tmp_path: Path):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="one", type_="feature", labels=[], today="2026-06-15")
    studio.cmd_move(tmp_path, tid, "in-progress")
    issues = tmp_path / ".archie" / "issues"
    assert not list((issues / "planned").glob(f"{tid}-*.md"))
    moved = list((issues / "in-progress").glob(f"{tid}-*.md"))
    assert len(moved) == 1
    assert "status: in-progress" in moved[0].read_text()


def test_cmd_move_rejects_unknown_status(tmp_path: Path):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="one", type_="feature", labels=[], today="2026-06-15")
    with pytest.raises(SystemExit):
        studio.cmd_move(tmp_path, tid, "frozen")


