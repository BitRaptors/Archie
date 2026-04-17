"""Tests for capabilities merging in merge.py."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import merge  # noqa: E402


def test_merge_capabilities_validates_refs(tmp_path):
    # Blueprint with known components, decisions, pitfalls.
    blueprint = {
        "components": [{"name": "UserService"}, {"name": "AuthController"}],
        "decisions": {"key_decisions": [{"title": "JWT over sessions"}]},
        "pitfalls": [{"area": "Password storage"}],
    }
    # Capabilities with mix of known and unknown refs.
    capabilities_input = [
        {
            "name": "User Authentication",
            "purpose": "login",
            "uses_components": ["UserService", "UnknownComponent"],
            "constrained_by_decisions": ["JWT over sessions", "UnknownDecision"],
            "related_pitfalls": ["Password storage"],
        },
        {
            "name": "Another Cap",
            "purpose": "stuff",
            "uses_components": ["NotAComponent"],
            "constrained_by_decisions": [],
            "related_pitfalls": [],
        },
    ]

    accepted, dropped = merge.merge_capabilities(blueprint, capabilities_input)

    assert accepted == 2  # both entries kept, bad refs dropped
    assert dropped == 3  # UnknownComponent + UnknownDecision + NotAComponent

    caps = blueprint["capabilities"]
    assert len(caps) == 2

    first = caps[0]
    assert first["name"] == "User Authentication"
    assert first["uses_components"] == ["UserService"]
    assert first["constrained_by_decisions"] == ["JWT over sessions"]
    assert first["related_pitfalls"] == ["Password storage"]

    second = caps[1]
    assert second["uses_components"] == []


def test_merge_capabilities_handles_empty_input():
    blueprint = {"components": [], "decisions": {"key_decisions": []}, "pitfalls": []}
    accepted, dropped = merge.merge_capabilities(blueprint, [])
    assert accepted == 0
    assert dropped == 0
    assert blueprint.get("capabilities", []) == []


def test_merge_capabilities_creates_key_if_missing():
    blueprint = {"components": [{"name": "X"}], "decisions": {}, "pitfalls": []}
    caps = [{"name": "Cap", "uses_components": ["X"]}]
    merge.merge_capabilities(blueprint, caps)
    assert "capabilities" in blueprint
    assert blueprint["capabilities"][0]["name"] == "Cap"
