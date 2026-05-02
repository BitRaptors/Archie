"""Regression guard for ``intent_layer.cmd_inject_scoped`` and the related
``cmd_extract_guardrails`` deterministic extractor.

The injection projects blueprint-level scoped patterns into the component-root
``CLAUDE.md`` between ``<!-- archie:scoped-start -->``/``<!-- archie:scoped-end -->``
markers. The extractor is the deterministic preprocessor that feeds Wave 2's
compound-learning loop without letting Archie's own previous output amplify
across runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import intent_layer  # noqa: E402


def _write_blueprint(root: Path, *, lockr_scope: list[str]) -> None:
    bp = {
        "components": {"components": [
            {"name": "billing", "location": "src/billing", "responsibility": "Billing"},
            {"name": "app", "location": "src/app", "responsibility": "App"},
        ]},
        "implementation_guidelines": [
            {
                "capability": "Per-key advisory lock",
                "category": "persistence",
                "libraries": ["lockr"],
                "pattern_description": "Acquire advisory lock keyed on (ns, id).",
                "key_files": ["lockr/lock.go"],
                "usage_example": "Acquire(ctx, key)",
                "applicable_when": "schema declares unique on key",
                "do_not_apply_when": ["non-unique key — would serialize unrelated rows"],
                "scope": lockr_scope,
                "tips": [],
            },
        ],
        "communication": {"patterns": []},
    }
    (root / ".archie").mkdir(exist_ok=True)
    (root / ".archie" / "blueprint.json").write_text(json.dumps(bp))


def _seed_ai_claude_md(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CLAUDE.md").write_text(
        f"# {name}\n\n<!-- archie:ai-start -->\n\n> {name}\n\n## Patterns\n\n**Local pattern** — derived from this folder's source.\n\n<!-- archie:ai-end -->\n"
    )


def test_injects_block_into_in_scope_component(tmp_path):
    _write_blueprint(tmp_path, lockr_scope=["billing"])
    _seed_ai_claude_md(tmp_path / "src" / "billing", "billing")
    _seed_ai_claude_md(tmp_path / "src" / "app", "app")

    intent_layer.cmd_inject_scoped(tmp_path)

    billing_md = (tmp_path / "src" / "billing" / "CLAUDE.md").read_text()
    app_md = (tmp_path / "src" / "app" / "CLAUDE.md").read_text()

    assert "<!-- archie:scoped-start -->" in billing_md
    assert "Per-key advisory lock" in billing_md
    assert "<!-- archie:scoped-start -->" not in app_md, "app is not in scope"
    assert "Per-key advisory lock" not in app_md


def test_injection_preserves_ai_section(tmp_path):
    _write_blueprint(tmp_path, lockr_scope=["billing"])
    _seed_ai_claude_md(tmp_path / "src" / "billing", "billing")

    intent_layer.cmd_inject_scoped(tmp_path)

    billing_md = (tmp_path / "src" / "billing" / "CLAUDE.md").read_text()
    assert "<!-- archie:ai-start -->" in billing_md
    assert "<!-- archie:ai-end -->" in billing_md
    assert "Local pattern" in billing_md, "AI-generated body must survive injection"


def test_injection_is_idempotent(tmp_path):
    _write_blueprint(tmp_path, lockr_scope=["billing"])
    _seed_ai_claude_md(tmp_path / "src" / "billing", "billing")

    intent_layer.cmd_inject_scoped(tmp_path)
    after_first = (tmp_path / "src" / "billing" / "CLAUDE.md").read_text()

    intent_layer.cmd_inject_scoped(tmp_path)
    after_second = (tmp_path / "src" / "billing" / "CLAUDE.md").read_text()

    assert after_first == after_second, "second run must be byte-identical"
    assert after_second.count("<!-- archie:scoped-start -->") == 1, "no duplication"


def test_scope_shrink_clears_stale_block(tmp_path):
    # Run 1: scoped to billing.
    _write_blueprint(tmp_path, lockr_scope=["billing"])
    _seed_ai_claude_md(tmp_path / "src" / "billing", "billing")
    intent_layer.cmd_inject_scoped(tmp_path)
    assert "Per-key advisory lock" in (tmp_path / "src" / "billing" / "CLAUDE.md").read_text()

    # Run 2: scope shrunk to []. The pattern no longer applies to billing.
    _write_blueprint(tmp_path, lockr_scope=[])
    intent_layer.cmd_inject_scoped(tmp_path)

    billing_md = (tmp_path / "src" / "billing" / "CLAUDE.md").read_text()
    assert "<!-- archie:scoped-start -->" not in billing_md, "stale block must be cleared"
    assert "Per-key advisory lock" not in billing_md
    assert "<!-- archie:ai-start -->" in billing_md, "AI section must remain"


def test_creates_claude_md_when_missing(tmp_path):
    """Component folder exists but has no CLAUDE.md (intent_layer skipped it).
    Scoped rules still need a delivery vehicle, so we create a minimal file.
    """
    _write_blueprint(tmp_path, lockr_scope=["billing"])
    (tmp_path / "src" / "billing").mkdir(parents=True)  # folder exists, no CLAUDE.md

    intent_layer.cmd_inject_scoped(tmp_path)

    billing_md_path = tmp_path / "src" / "billing" / "CLAUDE.md"
    assert billing_md_path.exists(), "must create CLAUDE.md when folder exists but file doesn't"
    body = billing_md_path.read_text()
    assert "Per-key advisory lock" in body
    assert "<!-- archie:scoped-start -->" in body


def test_skips_when_component_folder_missing(tmp_path):
    """Blueprint references a component whose location doesn't exist (e.g.
    repo restructure mid-flight). Inject must not crash; just skip."""
    _write_blueprint(tmp_path, lockr_scope=["billing"])
    # Don't create src/billing or src/app at all.

    intent_layer.cmd_inject_scoped(tmp_path)
    assert not (tmp_path / "src" / "billing").exists()


# ---------------------------------------------------------------------------
# Maintainer-guardrail extractor — the deterministic preprocessor for §11
# ---------------------------------------------------------------------------

def test_extract_strips_archie_blocks(tmp_path):
    """Bullets inside Archie's own marker blocks must NOT appear in output —
    that's the self-amplification guard.
    """
    (tmp_path / ".archie").mkdir()
    folder = tmp_path / "src" / "app"
    folder.mkdir(parents=True)
    (folder / "CLAUDE.md").write_text(
        "# app\n\n"
        "<!-- archie:ai-start -->\n\n"
        "## Anti-Patterns\n\n"
        "- AI-claimed anti-pattern (must be excluded — Archie's own output)\n\n"
        "<!-- archie:ai-end -->\n\n"
        "<!-- archie:scoped-start -->\n\n"
        "## Anti-Patterns\n\n"
        "- Scoped-injected anti-pattern (must be excluded — Archie's own output)\n\n"
        "<!-- archie:scoped-end -->\n\n"
        "## Anti-Patterns\n\n"
        "- Maintainer-curated guardrail (must be included)\n"
    )

    intent_layer.cmd_extract_guardrails(tmp_path)

    payload = json.loads((tmp_path / ".archie" / "maintainer_guardrails.json").read_text())
    all_items = [item for entry in payload["guardrails"] for item in entry["items"]]
    assert "Maintainer-curated guardrail (must be included)" in all_items
    assert all("Archie's own output" not in item for item in all_items), (
        "self-amplification guard breached: archie's own marker-block content leaked"
    )


def test_extract_handles_no_anti_patterns_section(tmp_path):
    """A CLAUDE.md without an Anti-Patterns section should contribute nothing."""
    (tmp_path / ".archie").mkdir()
    folder = tmp_path / "src" / "lib"
    folder.mkdir(parents=True)
    (folder / "CLAUDE.md").write_text("# lib\n\n## Patterns\n\n- Some pattern\n")

    intent_layer.cmd_extract_guardrails(tmp_path)
    payload = json.loads((tmp_path / ".archie" / "maintainer_guardrails.json").read_text())
    assert payload["guardrails"] == []


def test_extract_skips_archie_internal_dirs(tmp_path):
    """CLAUDE.md files under .archie/, .claude/, node_modules/, etc. must
    be skipped — Archie owns those, not the maintainer.
    """
    (tmp_path / ".archie").mkdir()
    for skip_dir in (".archie", ".claude", "node_modules"):
        d = tmp_path / skip_dir / "leaf"
        d.mkdir(parents=True)
        (d / "CLAUDE.md").write_text(
            "# leaf\n\n## Anti-Patterns\n\n- guardrail under " + skip_dir + "\n"
        )

    real = tmp_path / "src" / "real"
    real.mkdir(parents=True)
    (real / "CLAUDE.md").write_text(
        "# real\n\n## Anti-Patterns\n\n- real-folder guardrail\n"
    )

    intent_layer.cmd_extract_guardrails(tmp_path)
    payload = json.loads((tmp_path / ".archie" / "maintainer_guardrails.json").read_text())
    sources = {entry["source"] for entry in payload["guardrails"]}
    assert sources == {"src/real/CLAUDE.md"}, (
        f"only the non-archie folder should contribute; got {sources}"
    )


def test_extract_skips_repo_root_claude_md(tmp_path):
    """The root CLAUDE.md is fully Archie-generated; never extract from it."""
    (tmp_path / ".archie").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# root\n\n## Anti-Patterns\n\n- root guardrail\n")
    folder = tmp_path / "src" / "lib"
    folder.mkdir(parents=True)
    (folder / "CLAUDE.md").write_text("# lib\n\n## Anti-Patterns\n\n- lib guardrail\n")

    intent_layer.cmd_extract_guardrails(tmp_path)
    payload = json.loads((tmp_path / ".archie" / "maintainer_guardrails.json").read_text())
    sources = {entry["source"] for entry in payload["guardrails"]}
    assert sources == {"src/lib/CLAUDE.md"}
