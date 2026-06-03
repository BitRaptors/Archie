"""Tests for comprehensive-depth render-slice lifting in the standalone renderer.

In default depth the renderer trims several blueprint sections to a fixed cap
(data_models[:8], templates[:6], forces[:5], trade_offs[:3], etc.) so CLAUDE.md /
AGENTS.md stay lean. Comprehensive depth lifts those caps — every item that the
blueprint carries renders. These tests pin both behaviors so the cap can't drift.
"""
from __future__ import annotations

import importlib

import archie.standalone.renderer as renderer


def _bp_with_data_models(n: int) -> dict:
    """Blueprint carrying `n` distinctly-named data models so the rendered
    rows can be counted unambiguously."""
    models = [
        {"name": f"Model{i:02d}", "kind": "entity", "location": f"src/m{i}.py"}
        for i in range(n)
    ]
    return {
        "meta": {"repository": "test-repo", "schema_version": "2.0.0"},
        "data_models": models,
    }


def _count_model_rows(body: str, n: int) -> int:
    return sum(1 for i in range(n) if f"`Model{i:02d}`" in body)


def test_default_depth_caps_data_models_at_eight():
    """Default depth: only the first 8 data models render."""
    renderer._COMPREHENSIVE = False
    bp = _bp_with_data_models(12)
    body = renderer._generate_agent_body(bp, h1="AGENTS.md")
    assert _count_model_rows(body, 12) == 8


def test_comprehensive_depth_renders_all_data_models():
    """Comprehensive depth: every data model renders (cap lifted)."""
    renderer._COMPREHENSIVE = True
    try:
        bp = _bp_with_data_models(12)
        body = renderer._generate_agent_body(bp, h1="AGENTS.md")
        assert _count_model_rows(body, 12) == 12
    finally:
        renderer._COMPREHENSIVE = False


def test_comprehensive_flag_defaults_to_false():
    """The module-level switch is off unless --comprehensive is passed."""
    importlib.reload(renderer)
    assert renderer._COMPREHENSIVE is False
