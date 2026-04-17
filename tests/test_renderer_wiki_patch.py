"""Tests for the CLAUDE.md and AGENTS.md wiki patches in renderer.py."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import renderer  # noqa: E402


def test_wiki_flag_default_on(monkeypatch):
    monkeypatch.delenv("ARCHIE_WIKI_ENABLED", raising=False)
    assert renderer.wiki_enabled() is True


def test_wiki_flag_off_when_env_false(monkeypatch):
    monkeypatch.setenv("ARCHIE_WIKI_ENABLED", "false")
    assert renderer.wiki_enabled() is False


def test_wiki_flag_off_when_env_zero(monkeypatch):
    monkeypatch.setenv("ARCHIE_WIKI_ENABLED", "0")
    assert renderer.wiki_enabled() is False


def test_claude_md_pointer_when_flag_on():
    patch = renderer.claude_md_wiki_pointer()
    assert "Before you implement anything" in patch
    assert ".archie/wiki/index.md" in patch


def test_agents_md_usage_section():
    section = renderer.agents_md_wiki_section()
    assert "Using the Archie Wiki" in section
    assert ".archie/wiki/" in section
    assert "Referenced by" in section  # mentions the backlinks mechanism


def test_wiki_flag_off_when_archie_json_says_so(monkeypatch, tmp_path):
    monkeypatch.delenv("ARCHIE_WIKI_ENABLED", raising=False)
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "archie.json").write_text(json.dumps({"wiki_enabled": False}))
    monkeypatch.chdir(tmp_path)
    assert renderer.wiki_enabled() is False


def test_wiki_flag_env_overrides_archie_json(monkeypatch, tmp_path):
    """Env var set to 'true' must override archie.json wiki_enabled: false."""
    monkeypatch.setenv("ARCHIE_WIKI_ENABLED", "true")
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "archie.json").write_text(json.dumps({"wiki_enabled": False}))
    monkeypatch.chdir(tmp_path)
    assert renderer.wiki_enabled() is True


_MINIMAL_BLUEPRINT = {
    "meta": {},
    "decisions": {},
    "components": [],
    "pitfalls": [],
    "technology": {},
    "deployment": {},
    "architecture_diagram": "",
    "implementation_guidelines": [],
    "development_rules": [],
    "frontend": {},
    "architecture_rules": [],
    "communication": {},
    "quick_reference": {},
}


def test_generate_claude_md_includes_wiki_pointer(monkeypatch):
    monkeypatch.delenv("ARCHIE_WIKI_ENABLED", raising=False)
    md = renderer.generate_claude_md(_MINIMAL_BLUEPRINT)
    assert "## Before you implement anything" in md
    assert ".archie/wiki/index.md" in md


def test_generate_agents_md_includes_wiki_section(monkeypatch):
    monkeypatch.delenv("ARCHIE_WIKI_ENABLED", raising=False)
    md = renderer.generate_agents_md(_MINIMAL_BLUEPRINT)
    assert "## Using the Archie Wiki" in md


def test_generate_claude_md_omits_wiki_pointer_when_flag_off(monkeypatch):
    monkeypatch.setenv("ARCHIE_WIKI_ENABLED", "false")
    md = renderer.generate_claude_md(_MINIMAL_BLUEPRINT)
    assert "Before you implement anything" not in md
