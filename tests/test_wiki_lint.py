"""Tests for wiki_index lint."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_index  # noqa: E402


def _make_wiki(tmp_path: Path, files: dict[str, str]) -> Path:
    wiki = tmp_path / "wiki"
    for rel, content in files.items():
        path = wiki / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (wiki / "_meta").mkdir(exist_ok=True)
    return wiki


def test_lint_orphan_page(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[A](./components/a.md)\n",
        "components/a.md": "# A\n",
        "components/orphan.md": "# Orphan\n",
    })
    findings = wiki_index.lint(wiki)
    kinds = {f["kind"] for f in findings}
    assert "orphan" in kinds
    orphans = [f for f in findings if f["kind"] == "orphan"]
    assert any(f["page"] == "components/orphan.md" for f in orphans)
    # index.md itself is exempt from orphan detection.
    assert not any(f["page"] == "index.md" for f in orphans)


def test_lint_broken_link(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[Missing](./components/missing.md)\n",
    })
    findings = wiki_index.lint(wiki)
    broken = [f for f in findings if f["kind"] == "broken_link"]
    assert any(f["target"].endswith("components/missing.md") for f in broken)
