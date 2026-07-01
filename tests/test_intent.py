"""Tests for intent module: normalization + confidence ceiling."""
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
