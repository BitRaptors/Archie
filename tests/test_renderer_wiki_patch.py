"""Tests for the CLAUDE.md and AGENTS.md wiki patches in renderer.py."""

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
