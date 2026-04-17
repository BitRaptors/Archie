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


def test_lint_stale_evidence(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[A](./capabilities/a.md)\n",
        "capabilities/a.md": "# A\n",
    })
    # Provenance claims A's evidence is a glob that will match no files.
    prov = {
        "capabilities/a.md": {
            "sha256": "x", "source": "wiki_builder",
            "evidence": ["features/nonexistent/**"],
        }
    }
    (wiki / "_meta" / "provenance.json").write_text(json.dumps(prov))
    # Point fs_root at a project that has no `features/nonexistent/` directory.
    findings = wiki_index.lint(wiki, fs_root=tmp_path)
    assert any(f["kind"] == "stale_evidence" and f["page"] == "capabilities/a.md" for f in findings)


def test_lint_dangling_backlink(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n",
        "components/a.md": "# A\n",
    })
    backlinks = {
        "components/a.md": [
            {"path": "capabilities/gone.md", "title": "Gone", "type": "capability"}
        ]
    }
    (wiki / "_meta" / "backlinks.json").write_text(json.dumps(backlinks))
    findings = wiki_index.lint(wiki, fs_root=tmp_path)
    assert any(f["kind"] == "dangling_backlink" and f["page"] == "components/a.md" for f in findings)


import subprocess

STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"


def test_lint_cli_emits_json(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[Missing](./components/missing.md)\n",
    })
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_index.py"), "--lint",
         "--wiki", str(wiki), "--json"],
        capture_output=True, text=True, check=True,
    )
    findings = json.loads(result.stdout)
    assert any(f["kind"] == "broken_link" for f in findings)
