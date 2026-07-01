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
