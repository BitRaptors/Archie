"""Tests for sync.py — the Living Blueprint change ledger, Phase 1.

Phase 1 guarantee: `record` produces a versioned change file under .archie/changes/
and mutates NOTHING else (no blueprint.json, no CLAUDE.md). These tests pin that
guarantee plus the diff acquisition, claim classification, provenance (branch),
versioning, and malformed-input rejection.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import sync  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "checkout", "-q", "-b", "main")
    (tmp_path / "seed.txt").write_text("seed\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _stage_change(root: Path, rel: str, content: str = "x\n") -> None:
    """Create + stage a file so `git diff --name-only HEAD` (fallback) sees it."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(root, "add", "-A")


def _write_payload(tmp_path: Path, claims: list) -> Path:
    # Write OUTSIDE the repo (tmp_path is the repo root) so the payload file does not
    # itself appear as an untracked working-tree change.
    p = tmp_path.parent / f"payload_{tmp_path.name}.json"
    p.write_text(json.dumps(claims))
    return p


def _record(root: Path, payload: Path, capsys, agent: str = "claude") -> dict:
    rc = sync.main(["sync.py", "record", str(root), "--input", str(payload), "--agent", agent])
    out = capsys.readouterr().out.strip()
    return {"rc": rc, **json.loads(out)}


def _claim(kind="behavior", statement="Repo now persists via DataSource", evidence=None,
           confidence="high", reconstructed=False):
    return {
        "kind": kind,
        "statement": statement,
        "evidence_files": evidence if evidence is not None else ["data/Repo.kt"],
        "confidence": confidence,
        "reconstructed": reconstructed,
    }


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_record_writes_versioned_change_file(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "data/Repo.kt")
    res = _record(root, _write_payload(tmp_path, [_claim()]), capsys)

    assert res["ok"] is True
    assert res["version"] == 1
    assert res["folded"] is False
    changes = sorted((root / ".archie" / "changes").glob("change_*.json"))
    assert len(changes) == 1
    assert (root / ".archie" / "changes" / "latest.json").exists()
    rec = json.loads(changes[0].read_text())
    assert rec["folded"] is False
    assert rec["diff"]["changed_files"] == ["data/Repo.kt"]
    assert "data" in rec["diff"]["affected_folders"]


def test_phase1_does_not_touch_blueprint_or_claude(tmp_path, capsys):
    root = _init_repo(tmp_path)
    archie = root / ".archie"
    archie.mkdir()
    bp = archie / "blueprint.json"
    bp.write_text(json.dumps({"meta": {"x": 1}}))
    claude = root / "CLAUDE.md"
    claude.write_text("# hand authored\n")
    bp_before, claude_before = bp.read_bytes(), claude.read_bytes()

    _stage_change(root, "data/Repo.kt")
    res = _record(root, _write_payload(tmp_path, [_claim()]), capsys)

    assert res["ok"] is True
    # The Phase-1 guarantee: nothing but the ledger changed.
    assert bp.read_bytes() == bp_before
    assert claude.read_bytes() == claude_before


def test_classification_eligible_vs_staged(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "data/Repo.kt")
    claims = [
        _claim(statement="Eligible one", evidence=["data/Repo.kt"], confidence="high"),
        _claim(statement="No evidence in diff", evidence=["unrelated/other.kt"], confidence="high"),
        _claim(statement="Low confidence", evidence=["data/Repo.kt"], confidence="low"),
    ]
    res = _record(root, _write_payload(tmp_path, claims), capsys)
    assert res["eligible"] == 1
    assert res["staged"] == 2

    rec = json.loads((root / ".archie" / "changes" / "latest.json").read_text())
    by_stmt = {c["statement"]: c["status"] for c in rec["claims"]}
    assert by_stmt["Eligible one"] == "eligible"
    assert by_stmt["No evidence in diff"] == "staged"
    assert by_stmt["Low confidence"] == "staged"


def test_reconstructed_claim_is_staged(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "data/Repo.kt")
    claims = [_claim(evidence=["data/Repo.kt"], confidence="high", reconstructed=True)]
    res = _record(root, _write_payload(tmp_path, claims), capsys)
    assert res["eligible"] == 0
    assert res["staged"] == 1
    rec = json.loads((root / ".archie" / "changes" / "latest.json").read_text())
    assert rec["provenance"]["reconstructed"] is True


def test_branch_captured_in_provenance(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "feature/living-blueprint")
    _stage_change(root, "data/Repo.kt")
    _record(root, _write_payload(tmp_path, [_claim()]), capsys)
    rec = json.loads((root / ".archie" / "changes" / "latest.json").read_text())
    assert rec["provenance"]["branch"] == "feature/living-blueprint"
    assert rec["provenance"]["git_head"]


def test_version_increments_and_latest_matches(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "data/Repo.kt")
    _record(root, _write_payload(tmp_path, [_claim()]), capsys)
    _stage_change(root, "data/Other.kt")
    res2 = _record(root, _write_payload(tmp_path, [_claim(statement="Second")]), capsys)

    assert res2["version"] == 2
    files = sorted((root / ".archie" / "changes").glob("change_*.json"))
    assert len(files) == 2
    latest = json.loads((root / ".archie" / "changes" / "latest.json").read_text())
    assert latest["version"] == 2
    assert latest["id"] == res2["id"]


def test_malformed_payload_rejected_nothing_written(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "data/Repo.kt")
    bad = _write_payload(tmp_path, [{"type": "bogus", "title": "x"}])
    res = _record(root, bad, capsys)
    assert res["ok"] is False
    assert "invalid payload" in res["error"]
    assert not (root / ".archie" / "changes").exists()


def test_too_large_diff_writes_nothing(tmp_path, capsys):
    root = _init_repo(tmp_path)
    archie = root / ".archie"
    archie.mkdir()
    base_sha = _git(root, "rev-parse", "HEAD")
    # Small known universe so the ratio guard trips, plus >30 changed files.
    (archie / "scan.json").write_text(json.dumps({"file_tree": ["seed.txt"]}))
    (archie / "last_deep_scan.json").write_text(json.dumps({"commit_sha": base_sha, "mode": "full"}))
    for i in range(31):
        (root / f"f{i}.txt").write_text("y\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "many")

    res = _record(root, _write_payload(tmp_path, [_claim()]), capsys)
    assert res["ok"] is False
    assert res["mode"] == "full"
    assert not (archie / "changes").exists()


def test_stale_baseline_captures_worktree_change(tmp_path, capsys):
    """The real BabyWeather bug: a stale/huge committed baseline (detect-changes says
    'too large') must NOT block recording a small uncommitted edit. Capture the work
    in the tree; ignore the stale committed delta."""
    root = _init_repo(tmp_path)
    archie = root / ".archie"
    archie.mkdir()
    base_sha = _git(root, "rev-parse", "HEAD")
    # Simulate the stale baseline: tiny known universe, then >30 committed files so
    # detect-changes reports full/too-large against the baseline.
    (archie / "scan.json").write_text(json.dumps({"file_tree": ["seed.txt"]}))
    (archie / "last_deep_scan.json").write_text(json.dumps({"commit_sha": base_sha, "mode": "full"}))
    for i in range(40):
        (root / f"bulk{i}.txt").write_text("y\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "bulk baseline drift")
    # Now the actual session change: one uncommitted source edit.
    (root / "app" / "Main.kt").parent.mkdir(parents=True, exist_ok=True)
    (root / "app" / "Main.kt").write_text("// real fix\n")

    res = _record(root, _write_payload(tmp_path, [
        _claim(statement="Silence background errors", evidence=["app/Main.kt"], confidence="high")
    ]), capsys)

    assert res["ok"] is True, res
    rec = json.loads((root / ".archie" / "changes" / "latest.json").read_text())
    assert rec["diff"]["changed_files"] == ["app/Main.kt"]  # only the real edit, no bulk/.archie
    assert res["eligible"] == 1


def test_list_returns_records(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "data/Repo.kt")
    _record(root, _write_payload(tmp_path, [_claim()]), capsys)
    capsys.readouterr()  # drain

    rc = sync.main(["sync.py", "list", str(root), "--json"])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert len(out) == 1
    assert out[0]["version"] == 1
    assert out[0]["eligible"] == 1


def test_list_empty_ledger(tmp_path, capsys):
    root = _init_repo(tmp_path)
    rc = sync.main(["sync.py", "list", str(root), "--json"])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out == []


# --------------------------------------------------------------------------
# Phase 2 — fold plumbing (scope resolution + apply). The AI edit between the
# two steps is simulated here by editing blueprint.json directly.
# --------------------------------------------------------------------------

def _minimal_blueprint() -> dict:
    return {
        "meta": {"architecture_style": "MVVM"},
        "components": {"components": []},
        "decisions": {"key_decisions": [], "decision_chain": {}, "trade_offs": []},
        "pitfalls": [],
        "communication": {"patterns": []},
        "technology": {},
        "implementation_guidelines": {},
        "development_rules": [],
        "quick_reference": {},
    }


def _setup_foldable(tmp_path, capsys, claims):
    root = _init_repo(tmp_path)
    archie = root / ".archie"
    archie.mkdir()
    (archie / "blueprint.json").write_text(json.dumps(_minimal_blueprint()))
    (root / "app").mkdir()
    (root / "app" / "CLAUDE.md").write_text("# app context\n")
    _stage_change(root, "app/Main.kt")
    _record(root, _write_payload(tmp_path, claims), capsys)
    capsys.readouterr()  # drain record output
    return root, archie


def test_fold_context_resolves_scope(tmp_path, capsys):
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="behavior", statement="MainViewModel now filters background errors",
               evidence=["app/Main.kt"], confidence="high"),
        _claim(kind="rule", statement="Only user errors show the dialog",
               evidence=["app/Main.kt"], confidence="high"),
    ])
    rc = sync.main(["sync.py", "fold-context", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"]
    # advisory 'rule' is now staged (contract), so only the descriptive claim folds
    assert out["eligible_count"] == 1
    by = {t["kind"]: t for t in out["targets"]}
    assert "rule" not in by                       # advisory is NOT a fold target
    assert by["behavior"]["edit_file"].endswith("blueprint.json")
    assert by["behavior"]["blueprint_sections"] == ["components", "communication"]
    assert by["behavior"]["advisory"] is False
    # the rule surfaces as a PROPOSED amendment, not folded
    assert "rule" in {a["kind"] for a in out["staged_amendments"]}
    assert "app/CLAUDE.md" in out["intent_files"]
    # guardrail snapshot persisted into the change record (keys + contract fingerprint)
    rec = json.loads((archie / "changes" / "latest.json").read_text())
    assert "blueprint_top_level_keys" in rec["fold_guardrail"]
    assert "contract_fingerprint" in rec["fold_guardrail"]


def test_fold_context_intent_files_are_leaf_scoped(tmp_path, capsys):
    """Intent targets must be the LEAF folder owning the change, not every ancestor.
    A change in a/b/c must target a/b/c/CLAUDE.md, never the top-level a/CLAUDE.md."""
    root = _init_repo(tmp_path)
    archie = root / ".archie"
    archie.mkdir()
    (archie / "blueprint.json").write_text(json.dumps(_minimal_blueprint()))
    # CLAUDE.md at both a top ancestor and the leaf — already committed (as in a
    # real repo), so they are NOT part of the change delta.
    (root / "a").mkdir()
    (root / "a" / "CLAUDE.md").write_text("# a (top)\n")
    (root / "a" / "b" / "c").mkdir(parents=True)
    (root / "a" / "b" / "c" / "CLAUDE.md").write_text("# leaf\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "intent layer")
    # The actual change: one source file in the leaf folder.
    _stage_change(root, "a/b/c/Main.kt")
    _record(root, _write_payload(tmp_path, [
        _claim(kind="behavior", statement="leaf change", evidence=["a/b/c/Main.kt"], confidence="high"),
    ]), capsys)
    capsys.readouterr()

    sync.main(["sync.py", "fold-context", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert out["intent_files"] == ["a/b/c/CLAUDE.md"]  # leaf only
    assert "a/CLAUDE.md" not in out["intent_files"]     # NOT the ancestor


def test_fold_context_advisory_is_staged_not_folded(tmp_path, capsys):
    # Advisory kinds (pitfall/rule/decision/guideline) are the CONTRACT — never a fold
    # target. They surface as proposed amendments; the law changes only deliberately.
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="pitfall", statement="P", evidence=["app/Main.kt"], confidence="high"),
    ])
    rc = sync.main(["sync.py", "fold-context", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"]
    assert out["eligible_count"] == 0
    assert out["targets"] == []
    assert [a["kind"] for a in out["staged_amendments"]] == ["pitfall"]


def test_advisory_kinds_always_staged(tmp_path, capsys):
    root = _init_repo(tmp_path)
    _stage_change(root, "app/Main.kt")
    claims = [_claim(kind=k, statement=f"adv {k}", evidence=["app/Main.kt"], confidence="high")
              for k in ("decision", "pitfall", "rule", "guideline")]
    claims.append(_claim(kind="behavior", statement="desc one", evidence=["app/Main.kt"], confidence="high"))
    res = _record(root, _write_payload(tmp_path, claims), capsys)
    assert res["eligible"] == 1 and res["staged"] == 4  # only the descriptive folds
    rec = json.loads((root / ".archie" / "changes" / "latest.json").read_text())
    by = {c["statement"]: c["status"] for c in rec["claims"]}
    for k in ("decision", "pitfall", "rule", "guideline"):
        assert by[f"adv {k}"] == "staged"
    assert by["desc one"] == "eligible"


def test_fold_apply_reports_deliberate_rule_change(tmp_path, capsys):
    # A deliberate rule change during a fold is ALLOWED (rules legitimately change) but
    # SURFACED via contract_changed, so the law never moves silently.
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="behavior", statement="desc", evidence=["app/Main.kt"], confidence="high"),
    ])
    (archie / "rules.json").write_text(json.dumps({"rules": [{"id": "r1", "description": "old"}]}))
    sync.main(["sync.py", "fold-context", str(root)]); capsys.readouterr()
    # The dev deliberately moved a rule (extensive work) alongside the fold.
    (archie / "rules.json").write_text(json.dumps({"rules": [{"id": "r1", "description": "CHANGED"}]}))
    rc = sync.main(["sync.py", "fold-apply", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True          # NOT blocked
    assert out["contract_changed"] is True         # but surfaced
    assert "note" in out


def test_fold_apply_reports_deliberate_invariant_change(tmp_path, capsys):
    root = _init_repo(tmp_path)
    archie = root / ".archie"
    archie.mkdir()
    bp = _minimal_blueprint()
    bp["domain_invariants"] = [{"id": "inv-1", "invariant": "must hold"}]
    (archie / "blueprint.json").write_text(json.dumps(bp))
    (root / "app").mkdir()
    (root / "app" / "CLAUDE.md").write_text("# app\n")
    _stage_change(root, "app/Main.kt")
    _record(root, _write_payload(tmp_path, [
        _claim(kind="behavior", statement="d", evidence=["app/Main.kt"], confidence="high")]), capsys)
    capsys.readouterr()
    sync.main(["sync.py", "fold-context", str(root)]); capsys.readouterr()
    # Deliberately weaken an invariant during the fold — allowed, but flagged.
    bp2 = json.loads((archie / "blueprint.json").read_text())
    bp2["domain_invariants"][0]["invariant"] = "WEAKENED"
    (archie / "blueprint.json").write_text(json.dumps(bp2))
    rc = sync.main(["sync.py", "fold-apply", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["contract_changed"] is True


def test_contract_fingerprint_covers_prescriptive_blueprint_sections(tmp_path):
    # The law-in-the-blueprint (development_rules / infrastructure_rules / architecture_rules)
    # is part of the contract fingerprint, not just the invariants + rule files.
    root = tmp_path
    (root / ".archie").mkdir()
    fp = sync._contract_fingerprint
    assert fp(root, {"development_rules": [{"rule": "A"}]}) != fp(root, {"development_rules": [{"rule": "B"}]})
    assert fp(root, {"infrastructure_rules": [{"rule": "A"}]}) != fp(root, {"infrastructure_rules": [{"rule": "B"}]})
    assert fp(root, {"architecture_rules": {"naming_conventions": ["A"]}}) != \
           fp(root, {"architecture_rules": {"naming_conventions": ["B"]}})
    # a pure mirror section is NOT part of the contract fingerprint
    assert fp(root, {"components": {"components": [1]}}) == fp(root, {"components": {"components": [2]}})


def test_fold_apply_renders_and_marks_folded(tmp_path, capsys):
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="behavior", statement="X now does Y", evidence=["app/Main.kt"], confidence="high"),
    ])
    sync.main(["sync.py", "fold-context", str(root)]); capsys.readouterr()
    # Simulate the AI fold: update a descriptive MIRROR section (not the contract).
    bp = json.loads((archie / "blueprint.json").read_text())
    bp["components"]["components"].append({"name": "X", "responsibilities": ["does Y"]})
    (archie / "blueprint.json").write_text(json.dumps(bp))

    rc = sync.main(["sync.py", "fold-apply", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"], out
    assert out["folded"] == 1
    assert (root / "CLAUDE.md").exists()  # root docs re-rendered
    assert (root / "AGENTS.md").exists()
    rec = json.loads((archie / "changes" / "latest.json").read_text())
    assert rec["folded"] is True
    assert all(c["status"] == "folded" for c in rec["claims"])


def test_fold_apply_does_not_backfill_unrelated_folders(tmp_path, capsys):
    """The churn fix: fold-apply must NOT mass-rewrite per-folder CLAUDE.md
    (no repo-wide inject-scoped). An unrelated folder's CLAUDE.md stays untouched."""
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="behavior", statement="X now does Y", evidence=["app/Main.kt"], confidence="high"),
    ])
    unrel = root / "unrelated" / "CLAUDE.md"
    unrel.parent.mkdir()
    unrel.write_text("# unrelated folder context\n")
    before = unrel.read_bytes()

    sync.main(["sync.py", "fold-context", str(root)]); capsys.readouterr()
    # Simulate the agent's descriptive edit to the blueprint.
    bp = json.loads((archie / "blueprint.json").read_text())
    bp["components"]["components"].append({"name": "X", "responsibilities": ["does Y"]})
    (archie / "blueprint.json").write_text(json.dumps(bp))

    rc = sync.main(["sync.py", "fold-apply", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"]
    assert "intent_updated" not in out  # no repo-wide inject-scoped
    assert unrel.read_bytes() == before  # unrelated folder untouched


def test_fold_apply_render_failure_is_clean(tmp_path, capsys, monkeypatch):
    """If the render throws, fold-apply must NOT leave a half-applied blueprint,
    must report a JSON error (not a traceback), and must not mark the record folded."""
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="pitfall", statement="P", evidence=["app/Main.kt"], confidence="high"),
    ])
    sync.main(["sync.py", "fold-context", str(root)]); capsys.readouterr()
    bp_before = (archie / "blueprint.json").read_bytes()

    import renderer
    def _boom(*a, **k):
        raise RuntimeError("render exploded")
    monkeypatch.setattr(renderer, "generate_all", _boom)

    rc = sync.main(["sync.py", "fold-apply", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["ok"] is False
    assert "render failed" in out["error"]
    assert (archie / "blueprint.json").read_bytes() == bp_before  # untouched
    rec = json.loads((archie / "changes" / "latest.json").read_text())
    assert rec.get("folded") in (False, None)  # not marked folded


def test_fold_apply_guardrail_aborts_on_dropped_section(tmp_path, capsys):
    root, archie = _setup_foldable(tmp_path, capsys, [
        _claim(kind="pitfall", statement="P", evidence=["app/Main.kt"], confidence="high"),
    ])
    sync.main(["sync.py", "fold-context", str(root)]); capsys.readouterr()
    # Simulate a BAD edit that drops a whole top-level section.
    bp = json.loads((archie / "blueprint.json").read_text())
    del bp["decisions"]
    (archie / "blueprint.json").write_text(json.dumps(bp))

    rc = sync.main(["sync.py", "fold-apply", str(root)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["ok"] is False
    assert "guardrail" in out["error"]
    rec = json.loads((archie / "changes" / "latest.json").read_text())
    assert rec.get("folded") in (False, None)  # not marked folded


# ---------------------------------------------------------------------------
# plan-capture / plan-list / plan-consume subcommands
# ---------------------------------------------------------------------------

def _envelope(tool_name: str, tool_input: dict) -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": tool_input})


def _run(argv, capsys, stdin: str = "", monkeypatch=None):
    if stdin and monkeypatch is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    rc = sync.main(argv)
    out = capsys.readouterr().out.strip()
    return {"rc": rc, **(json.loads(out) if out else {})}


def test_plan_capture_writes_file(tmp_path, capsys, monkeypatch):
    root = _init_repo(tmp_path)
    env = _envelope("ExitPlanMode", {"plan": "Filter background refresh errors."})
    res = _run(["sync.py", "plan-capture", str(root)], capsys, stdin=env, monkeypatch=monkeypatch)
    assert res["rc"] == 0 and res["captured"] is True
    plans = list((root / ".archie" / "tmp" / "plans").glob("plan_*.md"))
    assert len(plans) == 1
    assert "Filter background refresh errors." in plans[0].read_text()


def test_plan_capture_no_plan_is_noop(tmp_path, capsys, monkeypatch):
    root = _init_repo(tmp_path)
    env = _envelope("ExitPlanMode", {})
    res = _run(["sync.py", "plan-capture", str(root)], capsys, stdin=env, monkeypatch=monkeypatch)
    assert res["rc"] == 0 and res["captured"] is False
    assert not (root / ".archie" / "tmp" / "plans").exists()


def test_plan_list_and_consume(tmp_path, capsys, monkeypatch):
    root = _init_repo(tmp_path)
    env = _envelope("ExitPlanMode", {"plan": "Decision: cache tokens in memory only."})
    _run(["sync.py", "plan-capture", str(root)], capsys, stdin=env, monkeypatch=monkeypatch)
    listed = _run(["sync.py", "plan-list", str(root)], capsys)
    assert len(listed["plans"]) == 1
    consumed = _run(["sync.py", "plan-consume", str(root)], capsys)
    assert len(consumed["consumed"]) == 1
    assert _run(["sync.py", "plan-list", str(root)], capsys)["plans"] == []
    assert list((root / ".archie" / "tmp" / "plans" / "consumed").glob("plan_*.md"))
