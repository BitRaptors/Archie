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


# ── D2 new tests ──────────────────────────────────────────────────────────────

def test_merge_store_bare_list_no_crash(tmp_path: Path) -> None:
    """If findings.json is a bare JSON list (not a dict), _merge_findings_into_store
    must NOT raise; it treats the content as corrupt and proceeds with an empty store."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    # Write a bare list — valid JSON but wrong shape.
    (archie_dir / "findings.json").write_text('[{"id": "old", "problem_statement": "stale"}]')

    new = [{"id": "f_fresh", "problem_statement": "new finding"}]
    # Must not raise AttributeError or any other exception.
    count = finalize._merge_findings_into_store(archie_dir, new)
    assert count >= 1
    # The resulting store must be valid JSON with a dict at the top level.
    result = json.loads((archie_dir / "findings.json").read_text())
    assert isinstance(result, dict)
    assert "findings" in result


def test_corrupt_store_preserved_not_wiped(tmp_path: Path) -> None:
    """When findings.json is truncated/corrupt, a .corrupt sidecar must be created
    preserving the original bytes. The run must still complete (proceed with empty store).
    """
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    corrupt_content = b'{"findings": [{"id": "precious"'  # truncated JSON
    (archie_dir / "findings.json").write_bytes(corrupt_content)

    new = [{"id": "f_new", "problem_statement": "after corruption"}]
    # Must not raise.
    finalize._merge_findings_into_store(archie_dir, new)

    # A .corrupt sidecar must exist containing the original bytes.
    corrupt_path = archie_dir / "findings.json.corrupt"
    assert corrupt_path.exists(), "Expected findings.json.corrupt sidecar to be created"
    assert corrupt_path.read_bytes() == corrupt_content, (
        "Corrupt sidecar does not contain the original bytes — old data was not preserved"
    )

    # The main findings.json must be valid JSON and a dict (run completed).
    result = json.loads((archie_dir / "findings.json").read_text())
    assert isinstance(result, dict)
    ids = {f.get("id") for f in result.get("findings", [])}
    assert "f_new" in ids


def test_store_write_is_atomic(tmp_path: Path) -> None:
    """After a normal merge, findings.json must be valid JSON and no leftover temp
    files should remain in the .archie directory."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()

    new = [{"id": "f_atom", "problem_statement": "atomic write test"}]
    finalize._merge_findings_into_store(archie_dir, new)

    # findings.json must be parseable.
    result = json.loads((archie_dir / "findings.json").read_text())
    assert isinstance(result, dict)

    # No leftover .tmp files should remain.
    tmp_files = list(archie_dir.glob("*.tmp"))
    assert tmp_files == [], f"Leftover temp files found: {tmp_files}"
