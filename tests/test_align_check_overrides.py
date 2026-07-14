import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import align_check as ac  # noqa: E402

VERDICT = {"diagnostics": [
    {"rule_id": "inv-003", "severity_class": "decision_violation", "verdict": "violates",
     "evidence": "adds cost column", "suggested_fix": "recompute at read time"},
    {"rule_id": "arch-001", "severity_class": "pattern_divergence", "verdict": "violates",
     "evidence": "", "suggested_fix": ""},
]}

ACKED = {"inv-003": {"rule_id": "inv-003", "reason": "store cost — authorized",
                     "authorized_by": "Gabor <g@e.com>", "branch": "demo/x",
                     "created_at": "2026-07-07T00:00:00Z", "status": "acked"}}


def test_acked_rule_demotes_and_unblocks(capsys):
    blocking = ac._render_diagnostics(VERDICT, overrides=ACKED)
    out = capsys.readouterr().out
    assert blocking is False                          # nothing left blocking
    assert "OVERRIDDEN" in out and "Gabor" in out     # still visible, attributed


def test_unacked_block_prints_footer(capsys):
    blocking = ac._render_diagnostics(VERDICT, overrides={})
    out = capsys.readouterr().out
    assert blocking is True
    assert "override-ack" in out                      # the door is advertised


def test_load_overrides_shape(tmp_path):
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "overrides.json").write_text(
        '{"version": 1, "overrides": [{"rule_id": "r1", "status": "acked"},'
        ' {"rule_id": "r2", "status": "ratified"}]}')
    got = ac._load_overrides(tmp_path / ".archie")
    assert set(got) == {"r1"}                         # only acked entries
