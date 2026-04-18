"""Tests for data_models merging in merge.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import merge  # noqa: E402


def test_merge_data_models_validates_refs():
    blueprint = {
        "components": [{"name": "UserService"}, {"name": "UserRepository"}],
    }
    input_models = [
        {
            "name": "User",
            "fields": [{"name": "id", "type": "string"}],
            "used_by_components": ["UserService", "UnknownService"],
        }
    ]
    accepted, dropped = merge.merge_data_models(blueprint, input_models)
    assert accepted == 1
    assert dropped == 1  # UnknownService dropped
    assert blueprint["data_models"][0]["used_by_components"] == ["UserService"]


def test_merge_data_models_handles_empty():
    blueprint = {"components": []}
    accepted, dropped = merge.merge_data_models(blueprint, [])
    assert accepted == 0
    assert dropped == 0
    assert blueprint.get("data_models", []) == []


def test_merge_data_models_creates_key_if_missing():
    blueprint = {"components": [{"name": "X"}]}
    merge.merge_data_models(blueprint, [{"name": "Thing", "used_by_components": ["X"]}])
    assert "data_models" in blueprint
    assert blueprint["data_models"][0]["name"] == "Thing"
