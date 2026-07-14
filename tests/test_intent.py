"""Tests for intent module: normalization + confidence ceiling + resolve()."""
import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent as it  # noqa: E402


def test_normalize_sets_source_and_confidence():
    spec = it.normalize("Add rate limiting to export", source="prompt", ticket_ids=[])
    assert spec["source"] == "prompt" and spec["confidence"] == "medium"
    assert spec["raw"].startswith("Add rate")


def test_inferred_source_is_low_and_advisory_ceiling():
    spec = it.normalize("", source="inferred", ticket_ids=[])
    assert spec["confidence"] == "low"
    assert it.ceiling_for(spec) <= 0.5


def test_linked_ticket_is_high_confidence():
    spec = it.normalize("AC1: scope by tenant", source="linear", ticket_ids=["ARCH-1"])
    assert spec["confidence"] == "high" and it.ceiling_for(spec) == 1.0


def test_ticket_regex_rejects_standards():
    # C1: common standards prefixes must NOT be treated as ticket IDs
    ids = it.ticket_ids_from("", "fixes CVE-2021-1234 and UTF-8 issue and RFC-822", [])
    assert ids == [], f"Expected [] but got {ids}"


def test_ticket_regex_accepts_real_tickets():
    # C1: real tracker keys still work
    ids = it.ticket_ids_from("feature/ARCH-12", "", [])
    assert "ARCH-12" in ids


def test_ticket_regex_rejects_multiple_standards():
    # C1: all denylist prefixes rejected in one call
    ids = it.ticket_ids_from(
        "",
        "SHA-256 and ISO-8601 and HTTP-301 and AES-128 and RSA-2048",
        [],
    )
    assert ids == [], f"Expected [] but got {ids}"


# --- resolve() tests ---

def test_resolve_populates_criteria():
    """resolve() with a valid LLM response fills goals + acceptance_criteria."""
    payload = json.dumps({
        "goals": ["rate limit exports"],
        "acceptance_criteria": [
            {"id": "ac1", "text": "export endpoint returns 429 after limit"},
            {"id": "ac2", "text": "limit resets after 60 seconds"},
        ],
    })
    called = {"n": 0}
    def fake_run(prompt, path, model): called["n"] += 1; return payload

    spec = it.normalize("Add rate limiting to export", source="prompt", ticket_ids=[])
    out = it.resolve(spec, run=fake_run)

    assert called["n"] == 1
    assert out["goals"] == ["rate limit exports"]
    assert len(out["acceptance_criteria"]) == 2
    assert out["acceptance_criteria"][0]["id"] == "ac1"
    assert "429" in out["acceptance_criteria"][0]["text"]


def test_resolve_empty_raw_noop():
    """resolve() is a no-op and does NOT call run when raw is empty."""
    called = {"n": 0}
    def fake_run(*a, **k): called["n"] += 1; return "{}"

    spec = it.normalize("", source="inferred", ticket_ids=[])
    out = it.resolve(spec, run=fake_run)

    assert called["n"] == 0
    assert out is spec  # same object unchanged


def test_resolve_bad_json_noop():
    """resolve() with garbage LLM output returns spec unchanged, no crash."""
    def garbage_run(prompt, path, model): return "this is not json at all"

    spec = it.normalize("Add retry logic", source="prompt", ticket_ids=[])
    out = it.resolve(spec, run=garbage_run)

    # goals and acceptance_criteria remain empty (unchanged from normalize)
    assert out["goals"] == []
    assert out["acceptance_criteria"] == []


def test_resolve_does_not_alias_input():
    """The returned spec's carried-over list fields must be copies, not aliases —
    mutating the returned spec's ticket_ids must not touch the input's."""
    payload = json.dumps({"goals": ["g"], "acceptance_criteria": [{"id": "ac1", "text": "t"}]})
    def fake_run(prompt, path, model): return payload

    spec = it.normalize("Add feature", source="prompt", ticket_ids=["ARCH-1"])
    out = it.resolve(spec, run=fake_run)

    assert out is not spec
    out["ticket_ids"].append("ARCH-999")
    assert spec["ticket_ids"] == ["ARCH-1"]  # input untouched
    out["non_goals"].append("x")
    assert spec["non_goals"] == []
