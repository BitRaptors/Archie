"""Tests for archie/standalone/code_shape.py — Phase 2 trigger DSL."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_code_shape",
    REPO_ROOT / "archie" / "standalone" / "code_shape.py",
)
assert _SPEC and _SPEC.loader
_cs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_cs)


# ---------------------------------------------------------------------------
# Path glob
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path,pattern,expected",
    [
        # Directory-prefix shorthand
        ("src/api/routes.py", "src/api/", True),
        ("src/api", "src/api/", True),
        ("src/web/page.py", "src/api/", False),
        # Plain literal exact match
        ("README.md", "README.md", True),
        ("docs/README.md", "README.md", False),
        # Single * (within segment)
        ("src/foo.go", "src/*.go", True),
        ("src/sub/foo.go", "src/*.go", False),
        # Double ** (across segments)
        ("openmeter/billing/charges/adapter/foo.go", "openmeter/billing/**/adapter/**", True),
        ("openmeter/billing/adapter/foo.go", "openmeter/billing/**/adapter/**", True),
        ("openmeter/customer/foo.go", "openmeter/billing/**/adapter/**", False),
        # Empty pattern is never a match
        ("anything", "", False),
    ],
)
def test_matches_path_glob(rel_path, pattern, expected):
    assert _cs.matches_path_glob(rel_path, pattern) is expected


def test_any_path_glob_matches_short_circuits():
    assert _cs.any_path_glob_matches(
        "src/api/routes.py",
        ["nope/", "src/api/"],
    ) is True
    assert _cs.any_path_glob_matches(
        "src/api/routes.py",
        ["nope/", "also-nope/"],
    ) is False


# ---------------------------------------------------------------------------
# code_shape — regex_in_content
# ---------------------------------------------------------------------------


def test_must_match_array_or_string_both_work():
    """Sonnet may emit must_match as a single string or an array. Both accepted."""
    shape_str = {"kind": "regex_in_content", "must_match": "foo"}
    shape_arr = {"kind": "regex_in_content", "must_match": ["foo"]}
    assert _cs.matches_code_shape("xfoox", shape_str)
    assert _cs.matches_code_shape("xfoox", shape_arr)


def test_must_match_any_of_array_fires():
    shape = {"kind": "regex_in_content", "must_match": ["alpha", "beta"]}
    assert _cs.matches_code_shape("hello beta world", shape)
    assert not _cs.matches_code_shape("nothing here", shape)


def test_must_not_match_blocks_when_present():
    """Negative pattern blocks the match when the ESCAPE pattern (e.g.,
    `entutils.Tx`) is present alongside the positive (e.g., `*entdb.Client`)."""
    shape = {
        "kind": "regex_in_content",
        "must_match": [r"\*entdb\.Client"],
        "must_not_match": [r"entutils\.Tx\("],
    }
    bad = "func foo(c *entdb.Client) error { /* raw */ return nil }"
    good = "func foo(c *entdb.Client) error { return entutils.Tx(c, ...) }"
    assert _cs.matches_code_shape(bad, shape)
    assert not _cs.matches_code_shape(good, shape)


def test_empty_must_match_never_fires():
    """A shape with no positive pattern is meaningless — return False."""
    assert not _cs.matches_code_shape("anything", {"kind": "regex_in_content"})
    assert not _cs.matches_code_shape("anything", {
        "kind": "regex_in_content",
        "must_match": [],
        "must_not_match": ["nope"],
    })


def test_unknown_kind_returns_false():
    """Forward-compat: future shape kinds shouldn't crash older hooks."""
    shape = {"kind": "function_signature_treesitter", "must_match": "foo"}
    assert not _cs.matches_code_shape("foo", shape)


def test_invalid_regex_does_not_crash():
    shape = {"kind": "regex_in_content", "must_match": ["[invalid("]}
    # Bad regex is silently skipped — function returns False because no pattern matched
    assert not _cs.matches_code_shape("anything", shape)


# ---------------------------------------------------------------------------
# rule_triggers_match — composite gate
# ---------------------------------------------------------------------------


def test_rule_without_triggers_block_always_matches():
    """Old-shape rules pass through the trigger gate unchanged."""
    rule = {"id": "legacy", "description": "..."}
    assert _cs.rule_triggers_match(rule, "any/path", "any content")


def test_rule_with_empty_triggers_never_matches_at_edit_time():
    """Classifier-only rules — explicitly empty triggers — skip edit-time enforcement."""
    rule = {"id": "classifier-only", "triggers": {}}
    assert not _cs.rule_triggers_match(rule, "any/path", "any content")


def test_path_glob_only_rule_fires_when_path_matches():
    rule = {
        "id": "layer-rule",
        "triggers": {"path_glob": ["domain/**"]},
    }
    assert _cs.rule_triggers_match(rule, "domain/order.go", "")
    assert not _cs.rule_triggers_match(rule, "ui/foo.tsx", "")


def test_code_shape_only_rule_fires_when_content_matches():
    rule = {
        "id": "ctx-rule",
        "triggers": {
            "code_shape": [{"kind": "regex_in_content", "must_match": [r"context\.TODO\("]}],
        },
    }
    assert _cs.rule_triggers_match(rule, "any/path", "x = context.TODO()")
    assert not _cs.rule_triggers_match(rule, "any/path", "no match here")


def test_path_and_code_shape_must_both_fire():
    rule = {
        "id": "tx-001",
        "triggers": {
            "path_glob": ["openmeter/billing/**/adapter/**"],
            "code_shape": [{
                "kind": "regex_in_content",
                "must_match": [r"\*entdb\.Client"],
                "must_not_match": [r"entutils\.Tx\("],
            }],
        },
    }
    bad_content = "func F(c *entdb.Client) error { return nil }"
    good_content = "func F(c *entdb.Client) error { return entutils.Tx(c, ...) }"
    # Both path + content match -> fires
    assert _cs.rule_triggers_match(rule, "openmeter/billing/charges/adapter/foo.go", bad_content)
    # Path matches but content has the escape -> doesn't fire
    assert not _cs.rule_triggers_match(rule, "openmeter/billing/charges/adapter/foo.go", good_content)
    # Content matches but path doesn't -> doesn't fire
    assert not _cs.rule_triggers_match(rule, "openmeter/customer/foo.go", bad_content)
