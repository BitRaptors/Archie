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


