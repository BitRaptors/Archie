"""finalize: --from 5 redo must REPLACE Wave-2 sections, not append (idempotent);
patch mode must NOT clear unchanged sections."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import finalize as F  # noqa: E402


def _write_agents(a: Path, kd: str, pid: str, diag: str, summ: str) -> list[str]:
    (a / "tmp").mkdir(parents=True, exist_ok=True)
    (a / "tmp" / "design.json").write_text(json.dumps({
        "decisions": {
            "key_decisions": [{"title": kd}],
            "trade_offs": [{"accept": "x", "caused_by": kd}],
            "decision_chain": {"root": "r", "forces": []},
        },
        "implementation_guidelines": [{"capability": "auth"}],
        "communication": {"patterns": [{"name": "REST", "do_not_apply_when": ["x"]}]},
    }))
    (a / "tmp" / "risk.json").write_text(json.dumps(
        {"findings": [], "pitfalls": [{"id": pid, "problem_statement": "c", "root_cause": kd}]}))
    (a / "tmp" / "overview.json").write_text(json.dumps(
        {"architecture_diagram": diag, "meta": {"executive_summary": summ}}))
    return [str(a / "tmp" / f) for f in ("design.json", "risk.json", "overview.json")]


def test_from5_redo_replaces_not_appends(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "blueprint_raw.json").write_text(json.dumps({
        "meta": {"platforms": ["backend"]},
        "components": {"components": [{"name": "API"}]},
        "communication": {"patterns": [{"name": "REST", "how_it_works": "base"}]},
    }))
    F.finalize(tmp_path, _write_agents(a, "Use Postgres", "pf_0001", "graph TD\n A1", "One."))
    # Simulate a `--from 5` redo with reworded reasoning.
    F.finalize(tmp_path, _write_agents(a, "Adopt PostgreSQL with Ent", "pf_0002", "graph TD\n B2", "Two."))

    bp = json.loads((a / "blueprint.json").read_text())
    assert len(bp["decisions"]["key_decisions"]) == 1
    assert bp["decisions"]["key_decisions"][0]["title"] == "Adopt PostgreSQL with Ent"
    assert len(bp["decisions"]["trade_offs"]) == 1
    assert [p["id"] for p in bp["pitfalls"]] == ["pf_0002"]
    assert bp["architecture_diagram"].strip().endswith("B2")     # not stale
    assert bp["meta"]["executive_summary"] == "Two."             # not stale
    assert bp["meta"]["platforms"] == ["backend"]                # Wave-1 meta preserved
    assert len(bp["implementation_guidelines"]) == 1
    assert len(bp["communication"]["patterns"]) == 1             # deduped, no dup


def test_patch_mode_does_not_clear(tmp_path):
    # Incremental (patch) agents return only deltas — clearing would wipe
    # unchanged sections. Verify the reset is full-mode-only.
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "blueprint_raw.json").write_text(json.dumps({
        "decisions": {"key_decisions": [{"title": "Existing"}]},
        "pitfalls": [{"id": "pf_0001"}],
        "components": {"components": []},
    }))
    (a / "tmp").mkdir()
    patch = a / "tmp" / "inc.json"
    patch.write_text(json.dumps({"architecture_diagram": "graph TD\n X"}))
    F.finalize(tmp_path, [str(patch)], patch_mode=True)

    bp = json.loads((a / "blueprint.json").read_text())
    assert len(bp["decisions"]["key_decisions"]) == 1   # preserved
    assert bp["pitfalls"] == [{"id": "pf_0001"}]         # preserved
    assert bp["architecture_diagram"].strip().endswith("X")
