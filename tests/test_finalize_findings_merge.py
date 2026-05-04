"""Regression test for `finalize.py:_merge_findings_into_store`: the
verifier-pipeline state (verdict_history, pending_*, demoted_at, etc.) must
be preserved across scans even though the synthesizer never re-emits these
fields. Without preservation, every scan wipes the history and the
hysteresis layer can never accumulate signal across runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import finalize  # noqa: E402


def _make_archie_dir(tmp_path: Path, prior: list) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    if prior is not None:
        (archie_dir / "findings.json").write_text(
            json.dumps({"findings": prior}, indent=2)
        )
    return archie_dir


def test_merge_preserves_verdict_history_when_synthesizer_does_not_reemit(tmp_path: Path) -> None:
    """The synthesizer emits a fresh finding without verifier-pipeline
    fields. Merge should preserve verdict_history, pending_*, demoted_at,
    last_verdict_* from the prior entry — otherwise hysteresis breaks
    across scans."""
    archie_dir = _make_archie_dir(tmp_path, [
        {
            "id": "f_0001",
            "problem_statement": "old wording",
            "first_seen": "2026-04-01T1000",
            "confirmed_in_scan": 3,
            "status": "demoted",
            "verdict_history": ["demote", "demote"],
            "last_verdict_reason": "callers wrap with TransactingRepo",
            "last_verdict_confidence": 0.9,
            "demoted_at": "2026-04-15T1200",
            "pending_promotion": True,
        }
    ])

    # Synthesizer re-emits with new wording but no verifier fields:
    new = [{
        "id": "f_0001",
        "problem_statement": "new clearer wording",
        "evidence": ["src/foo.go:42"],
    }]

    finalize._merge_findings_into_store(archie_dir, new)

    after = json.loads((archie_dir / "findings.json").read_text())
    f = after["findings"][0]

    # New emission's content takes precedence.
    assert f["problem_statement"] == "new clearer wording"
    assert f["evidence"] == ["src/foo.go:42"]
    # First-seen and status preserved.
    assert f["first_seen"] == "2026-04-01T1000"
    assert f["status"] == "demoted"
    assert f["confirmed_in_scan"] == 4
    # Verifier-pipeline state preserved — this is the bug we're guarding.
    assert f["verdict_history"] == ["demote", "demote"]
    assert f["last_verdict_reason"] == "callers wrap with TransactingRepo"
    assert f["last_verdict_confidence"] == 0.9
    assert f["demoted_at"] == "2026-04-15T1200"
    assert f["pending_promotion"] is True


def test_merge_lets_new_emission_override_verifier_state_when_explicit(tmp_path: Path) -> None:
    """If the synthesizer (or any upstream step) DOES emit a verifier
    field explicitly, it should take precedence — preservation is a
    fallback for the common case, not a hard override."""
    archie_dir = _make_archie_dir(tmp_path, [
        {
            "id": "f_0002",
            "problem_statement": "x",
            "verdict_history": ["demote", "demote"],
            "status": "demoted",
        }
    ])

    new = [{
        "id": "f_0002",
        "problem_statement": "x",
        "verdict_history": [],  # explicit reset
        "status": "active",     # explicit override
    }]

    finalize._merge_findings_into_store(archie_dir, new)

    after = json.loads((archie_dir / "findings.json").read_text())
    f = after["findings"][0]
    assert f["verdict_history"] == []
    assert f["status"] == "active"


def test_merge_new_finding_starts_clean(tmp_path: Path) -> None:
    """A finding the store has never seen before gets default status =
    active, no verifier-pipeline fields seeded — apply_verdicts populates
    them on first verification."""
    archie_dir = _make_archie_dir(tmp_path, [])
    new = [{"id": "f_new", "problem_statement": "fresh"}]

    finalize._merge_findings_into_store(archie_dir, new)

    after = json.loads((archie_dir / "findings.json").read_text())
    f = after["findings"][0]
    assert f["status"] == "active"
    assert f["confirmed_in_scan"] == 1
    assert "verdict_history" not in f
    assert "demoted_at" not in f
