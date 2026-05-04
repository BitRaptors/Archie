"""Regression tests for verdict-driven hysteresis routing
(`apply_verdicts.py`).

The state machine has four invariants worth pinning:

1. `drop` is fast-path: no hysteresis, transitions immediately. A `keep`
   verdict on a previously-dropped finding re-emerges it.
2. `demote` from `active` requires either two consecutive demote verdicts
   OR a git-diff anchor — single-scan flips on unchanged code stay active
   with `pending_demotion: True` so the user knows there's drift to watch.
3. `keep` from `demoted` (re-promotion) follows the symmetric rule — needs
   two consecutive keeps OR a git-diff anchor to flip back to active.
4. `verdict_history` accumulates newest-first, capped at 3.

We don't shell out to git here — `_has_material_change` is exercised
directly with an injected `recent_files` set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import apply_verdicts  # noqa: E402


NOW = "2026-05-04T1500"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _verdict(v: str, *, confidence: float = 0.85, reason: str = "") -> dict:
    return {"id": "f_test", "verdict": v, "confidence": confidence, "reason": reason}


# ---------------------------------------------------------------------------
# _two_consecutive
# ---------------------------------------------------------------------------

def test_two_consecutive_true_when_first_two_match() -> None:
    assert apply_verdicts._two_consecutive(["demote", "demote", "keep"], "demote")


def test_two_consecutive_false_when_only_first_matches() -> None:
    assert not apply_verdicts._two_consecutive(["demote", "keep", "demote"], "demote")


def test_two_consecutive_false_when_history_too_short() -> None:
    assert not apply_verdicts._two_consecutive(["demote"], "demote")


# ---------------------------------------------------------------------------
# _has_material_change
# ---------------------------------------------------------------------------

def test_material_change_matches_triggering_call_site_path() -> None:
    finding = {"triggering_call_site": "src/foo.py:42\n    bad()"}
    assert apply_verdicts._has_material_change(finding, {"src/foo.py"})


def test_material_change_matches_applies_to() -> None:
    finding = {"triggering_call_site": "", "applies_to": ["src/baz.py"]}
    assert apply_verdicts._has_material_change(finding, {"src/baz.py"})


def test_material_change_no_overlap() -> None:
    finding = {"triggering_call_site": "src/foo.py:42\n", "applies_to": []}
    assert not apply_verdicts._has_material_change(finding, {"src/other.py"})


def test_material_change_empty_recent_files() -> None:
    finding = {"triggering_call_site": "src/foo.py:42\n"}
    assert not apply_verdicts._has_material_change(finding, set())


# ---------------------------------------------------------------------------
# _apply_one — drop verdict
# ---------------------------------------------------------------------------

def test_drop_transitions_active_to_dropped_immediately() -> None:
    f = {"id": "f_1", "status": "active"}
    out = apply_verdicts._apply_one(f, _verdict("drop"), set(), NOW)
    assert out["status"] == "dropped"
    assert out["dropped_at"] == NOW


def test_drop_idempotent_on_already_dropped() -> None:
    f = {"id": "f_1", "status": "dropped", "dropped_at": "earlier"}
    out = apply_verdicts._apply_one(f, _verdict("drop"), set(), NOW)
    assert out["status"] == "dropped"
    # Don't overwrite the original timestamp on a no-op transition.
    assert out["dropped_at"] == "earlier"


# ---------------------------------------------------------------------------
# _apply_one — re-emergence from dropped
# ---------------------------------------------------------------------------

def test_keep_on_dropped_finding_re_emerges_immediately() -> None:
    f = {"id": "f_1", "status": "dropped", "dropped_at": "earlier"}
    out = apply_verdicts._apply_one(f, _verdict("keep"), set(), NOW)
    assert out["status"] == "active"
    assert "dropped_at" not in out


def test_demote_on_dropped_finding_stays_dropped() -> None:
    """Contradictory verdict — drop already said premise unsound; a later
    demote verdict shouldn't accidentally re-activate the finding via the
    `unknown prior status` fallback. Stay dropped."""
    f = {"id": "f_1", "status": "dropped", "dropped_at": "earlier"}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["status"] == "dropped"
    assert out.get("dropped_at") == "earlier"


# ---------------------------------------------------------------------------
# _apply_one — active + demote (hysteresis)
# ---------------------------------------------------------------------------

def test_active_demote_first_time_holds_active_with_pending_flag() -> None:
    """Single demote on unchanged code: the LLM-flicker guard. Stay active,
    record the pending intent for the next scan to confirm or reverse."""
    f = {"id": "f_1", "status": "active", "verdict_history": []}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["status"] == "active"
    assert out.get("pending_demotion") is True
    assert out["verdict_history"] == ["demote"]


def test_active_demote_after_prior_demote_transitions_to_demoted() -> None:
    f = {"id": "f_1", "status": "active", "verdict_history": ["demote"]}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["status"] == "demoted"
    assert out["demoted_at"] == NOW
    assert "pending_demotion" not in out


def test_active_demote_with_material_change_transitions_immediately() -> None:
    """Even a single demote verdict triggers transition when the cited
    file has been touched in the recent diff window — that's a material
    code change, not LLM noise."""
    f = {
        "id": "f_1",
        "status": "active",
        "verdict_history": [],
        "triggering_call_site": "src/foo.py:42\n",
    }
    out = apply_verdicts._apply_one(f, _verdict("demote"), {"src/foo.py"}, NOW)
    assert out["status"] == "demoted"
    assert out["demoted_at"] == NOW


def test_active_keep_clears_pending_demotion() -> None:
    """If a finding was pending_demotion last scan but the verifier now
    confirms it as real, clear the flag."""
    f = {"id": "f_1", "status": "active", "pending_demotion": True,
         "verdict_history": ["demote"]}
    out = apply_verdicts._apply_one(f, _verdict("keep"), set(), NOW)
    assert out["status"] == "active"
    assert "pending_demotion" not in out


# ---------------------------------------------------------------------------
# _apply_one — demoted + keep (re-promotion hysteresis)
# ---------------------------------------------------------------------------

def test_demoted_keep_first_time_holds_demoted_with_pending_flag() -> None:
    f = {"id": "f_1", "status": "demoted", "verdict_history": ["demote"]}
    out = apply_verdicts._apply_one(f, _verdict("keep"), set(), NOW)
    assert out["status"] == "demoted"
    assert out.get("pending_promotion") is True


def test_demoted_keep_after_prior_keep_transitions_to_active() -> None:
    """Two consecutive keep verdicts on a previously-demoted finding re-promote it."""
    f = {"id": "f_1", "status": "demoted", "verdict_history": ["keep", "demote"],
         "demoted_at": "earlier"}
    out = apply_verdicts._apply_one(f, _verdict("keep"), set(), NOW)
    assert out["status"] == "active"
    assert "demoted_at" not in out
    assert "pending_promotion" not in out


def test_demoted_keep_with_material_change_promotes_immediately() -> None:
    f = {"id": "f_1", "status": "demoted", "verdict_history": ["demote"],
         "triggering_call_site": "src/bar.py:10\n", "demoted_at": "earlier"}
    out = apply_verdicts._apply_one(f, _verdict("keep"), {"src/bar.py"}, NOW)
    assert out["status"] == "active"
    assert "demoted_at" not in out


def test_demoted_demote_again_clears_pending_promotion() -> None:
    f = {"id": "f_1", "status": "demoted", "pending_promotion": True,
         "verdict_history": ["keep"]}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["status"] == "demoted"
    assert "pending_promotion" not in out


# ---------------------------------------------------------------------------
# verdict_history accumulation
# ---------------------------------------------------------------------------

def test_verdict_history_capped_at_three() -> None:
    f = {"id": "f_1", "status": "active",
         "verdict_history": ["keep", "keep", "keep"]}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["verdict_history"] == ["demote", "keep", "keep"]
    assert len(out["verdict_history"]) == 3


def test_verdict_history_newest_first() -> None:
    f = {"id": "f_1", "status": "active", "verdict_history": ["keep"]}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["verdict_history"] == ["demote", "keep"]


# ---------------------------------------------------------------------------
# resolved status — sticky unless re-emerged
# ---------------------------------------------------------------------------

def test_resolved_keep_re_emerges_to_active() -> None:
    f = {"id": "f_1", "status": "resolved"}
    out = apply_verdicts._apply_one(f, _verdict("keep"), set(), NOW)
    assert out["status"] == "active"


def test_resolved_demote_stays_resolved() -> None:
    f = {"id": "f_1", "status": "resolved"}
    out = apply_verdicts._apply_one(f, _verdict("demote"), set(), NOW)
    assert out["status"] == "resolved"


# ---------------------------------------------------------------------------
# apply_verdicts (integration over .archie/findings.json + verdicts.json)
# ---------------------------------------------------------------------------

def _setup_archie(tmp_path: Path, findings: list, verdicts: list) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "findings.json").write_text(
        json.dumps({"findings": findings}, indent=2)
    )
    (archie_dir / "verdicts.json").write_text(
        json.dumps({"verdicts": verdicts}, indent=2)
    )
    return archie_dir


def test_apply_verdicts_routes_keep_demote_drop_in_one_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stub the git diff so no finding gets a material-change anchor and
    # hysteresis behaves deterministically.
    monkeypatch.setattr(
        apply_verdicts, "_git_recently_changed_files", lambda root, depth=5: set()
    )

    findings = [
        {"id": "f_real", "status": "active", "verdict_history": ["keep"]},
        {"id": "f_demote_2nd", "status": "active", "verdict_history": ["demote"]},
        {"id": "f_drop", "status": "active", "verdict_history": []},
        {"id": "f_first_demote", "status": "active", "verdict_history": []},
    ]
    verdicts = [
        {"id": "f_real", "verdict": "keep", "confidence": 0.9, "reason": "real"},
        {"id": "f_demote_2nd", "verdict": "demote", "confidence": 0.9, "reason": "callers safe"},
        {"id": "f_drop", "verdict": "drop", "confidence": 0.95, "reason": "premise unsound"},
        {"id": "f_first_demote", "verdict": "demote", "confidence": 0.85, "reason": "callers safe"},
    ]
    archie_dir = _setup_archie(tmp_path, findings, verdicts)

    result = apply_verdicts.apply_verdicts(archie_dir)
    assert result["status"] == "applied"

    after = json.loads((archie_dir / "findings.json").read_text())
    by_id = {f["id"]: f for f in after["findings"]}

    # f_real — verifier confirmed, stays active.
    assert by_id["f_real"]["status"] == "active"
    # f_demote_2nd — second consecutive demote, transitions to demoted.
    assert by_id["f_demote_2nd"]["status"] == "demoted"
    # f_drop — fast-path drop.
    assert by_id["f_drop"]["status"] == "dropped"
    # f_first_demote — first demote on unchanged code, hysteresis holds active.
    assert by_id["f_first_demote"]["status"] == "active"
    assert by_id["f_first_demote"].get("pending_demotion") is True


def test_apply_verdicts_skips_when_verdicts_missing(tmp_path: Path) -> None:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "findings.json").write_text(json.dumps({"findings": []}))
    # NOTE: no verdicts.json
    result = apply_verdicts.apply_verdicts(archie_dir)
    assert result["status"] == "skipped"


def test_apply_verdicts_skips_when_findings_store_missing(tmp_path: Path) -> None:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "verdicts.json").write_text(json.dumps({"verdicts": []}))
    # NOTE: no findings.json
    result = apply_verdicts.apply_verdicts(archie_dir)
    assert result["status"] == "skipped"


def test_apply_verdicts_unmatched_findings_pass_through_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding without a corresponding verdict should be left alone — it
    might be from an older scan whose verifier didn't run, or from a
    parallel pipeline path. Don't touch it."""
    monkeypatch.setattr(
        apply_verdicts, "_git_recently_changed_files", lambda root, depth=5: set()
    )
    findings = [
        {"id": "f_known", "status": "active", "verdict_history": []},
        {"id": "f_orphan", "status": "active", "verdict_history": []},
    ]
    verdicts = [
        {"id": "f_known", "verdict": "drop", "confidence": 0.95, "reason": "out"},
    ]
    archie_dir = _setup_archie(tmp_path, findings, verdicts)
    result = apply_verdicts.apply_verdicts(archie_dir)
    assert result["status"] == "applied"
    summary = result["summary"]
    assert summary["no_verdict"] == 1

    after = json.loads((archie_dir / "findings.json").read_text())
    by_id = {f["id"]: f for f in after["findings"]}
    assert by_id["f_known"]["status"] == "dropped"
    assert by_id["f_orphan"]["status"] == "active"
    # Untouched finding shouldn't have verdict_history populated either.
    assert "last_verdict_reason" not in by_id["f_orphan"]
