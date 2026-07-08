# Review Re-scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** One PR comment that leads with the **contract delta** — what merging this PR accepts — and backs it with **code review**: actionable, blueprint-independent defects a human can fix. Intent grading deleted. API cost cut.

**Architecture:** `override-ack` now writes the contract change **onto the branch**: it removes the rule from `rules.json`, stamps the blueprint invariant `overridden`, and records the reason + authorizer + a snapshot of the law in `overrides.json`. So there is exactly **one carrier** — the source of truth itself — and **merging is the ratification**. `override-ratify` is deleted. `intent_review.py`'s deterministic differ then sees every contract change; `contract_delta.py` partitions those changes into *authorized* (an override explains them — free, no model) and *unexplained* (adds, modifies, and any removal nobody authorized), sending only the unexplained ones to `intent_review`'s existing **one Haiku call** to judge against the retained rules. `delivery_review.py` renders the single comment.

**Tech Stack:** Python 3.9 stdlib only, pytest.

## Global Constraints

- `python3` only (3.9.6 target); zero third-party dependencies.
- Bare sibling imports (`import overrides`), NEVER `from archie.standalone.X`; guard with `sys.path.insert(0, str(Path(__file__).parent))`.
- Canonical → mirror: edit `archie/standalone/*.py` and `archie/assets/**` FIRST; npm mirroring deferred to Task 8. **Do not flag or fix `verify_sync.py` failures in Tasks 1–7.**
- Exit-0 contract: no function in the review path may raise. Missing/corrupt `overrides.json`, `rules.json`, an unresolvable base ref, or a failed model call degrades to a **disclosed** partial section — never to a silent green.
- Every rendered field originating from user text (`reason`, `authorized_by`, law text, `change_summary`, `colliding_rules`) must pass through `delivery_review._sanitize` — it lands in a public PR comment.
- Judge findings and unauthorized violations are **surface-only**. The Action always exits 0. Never add a blocking exit code.
- **Never re-implement `intent_review`'s differ.** Its pure functions (`build_changed_items`, `retained_rules`, `build_prompt`, `call_anthropic`, `finalize_findings`, `glob_ledger`, `normalize_rules`, `fetch_base_file`, `load_branch_file`, `RULE_FILES`) own what changed; the model only judges.
- `override-ack` remains **agent-run only, after explicit user confirmation**. Do not add a user-facing command or weaken that docstring.
- Commits: `git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit ...` with trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Test with `python3 -m pytest <file> -q`.

## Untouched by design

`pre-validate.sh`, `align_check.py`, and the stop-hook task-story imprint. The stop-and-confirm question — and the reason the user types into it — is the *input* to this design: that reason becomes the `Why` column of the contract table and the justification the judge weighs. Task-story capture stays silent and automatic on the developer's machine; only CI-side story **synthesis** and intent **grading** are removed.

The rule-demotion path in the gates stays too. Once `override-ack` removes a rule from `rules.json` the gate cannot fire it at all, so demotion becomes a safety net (e.g. a later deep scan re-derives the law before anyone removes the override entry). Do not delete it.

## File Structure

| File | Responsibility |
|---|---|
| `archie/standalone/sync.py` (modify) | `override-ack` writes the contract change onto the branch. `override-ratify` deleted. |
| `archie/standalone/overrides.py` (modify) | `ack` snapshots the law text. `pending_ratification` / `archive` deleted (nothing ratifies after merge any more). |
| `archie/standalone/contract_delta.py` (new) | Partition the deterministic diff into authorized retirements (free) vs unexplained changes (one Haiku call, via `intent_review`). |
| `archie/standalone/delivery_review.py` (modify) | `render_verdict` rewritten: contract → unauthorized → code review. Intent grading + CI story-synthesis deleted. Posts the one comment. |
| `archie/standalone/intent_review.py` (modify) | `marker` param on the comment helpers. Otherwise unchanged — consumed as a library. |
| `archie/standalone/review_core.py` (modify) | Drop edge-A + edge-C; `passes=1`; skip acked laws. |
| `archie/standalone/invariant_specialist.py` (modify) | `skip_ids` — never pay Opus for an acknowledged law. |
| `archie/standalone/renderer.py` (modify) | Label overridden laws `retired`, not `ratified`. |
| `archie/assets/workflow/sync/SKILL.md`, `deep-scan/steps/step-5d-product.md`, `step-6-rule-synthesis.md` (modify) | Drop `override-ratify`; tombstones read `overrides.json`. |
| `archie/assets/workflows/archie-intent-review.yml` (modify) | One job, one comment. |

---

### Task 1: `override-ack` writes the contract change onto the branch

**Files:**
- Modify: `archie/standalone/overrides.py` (`ack` def ~line 80; delete `pending_ratification` ~111 and `archive` ~119, and the `HISTORY` constant)
- Modify: `archie/standalone/sync.py` (`cmd_override_ack` ~line 816; delete `cmd_override_ratify` ~855–895, its dispatch entry ~1232, and its `_usage` line ~986)
- Modify: `archie/standalone/renderer.py` (the `state = (... else "ratified")` line in `_build_product_laws_rule`)
- Modify: `archie/assets/workflow/sync/SKILL.md` (Step 2b), `archie/assets/workflow/deep-scan/steps/step-5d-product.md`, `step-6-rule-synthesis.md`
- Test: `tests/test_overrides.py`, `tests/test_override_subcommands.py`, `tests/test_workflow_override_text.py`, `tests/test_renderer_overrides.py`

**Interfaces:**
- Produces: `overrides.ack(root, rule_id, reason, law="", now=None) -> dict` — the entry gains a `law` key (a snapshot of the rule's `description` at ack time, because the rule is about to leave `rules.json`).
- Produces: `sync.py override-ack <root> <rule_id> --reason "..."` now, in one atomic-ish step: snapshots the law → **removes the rule** from `rules.json` / `platform_rules.json` → stamps the matching `blueprint.json` `domain_invariants[]` entry `status: "overridden"` + `override: {reason, authorized_by, branch}` → writes the `overrides.json` entry. Prints `{"acked", "branch", "by", "rule_removed": bool}`.
- Removed: `overrides.pending_ratification`, `overrides.archive`, `sync.py override-ratify`.

**Why:** an acked override *is* a proposed contract change. Routing it into a side file (`overrides.json`) meant the source of truth never moved, the rules differ saw nothing, and a separate post-merge `override-ratify` had to apply it later. Writing it onto the branch collapses two carriers into one: the differ sees the removal, the reason justifies it, and **merging accepts it**. The removal-logic already exists — it is `cmd_override_ratify`'s body, relocated.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_overrides.py
def test_ack_snapshots_the_law_text(tmp_path):
    _git_repo(tmp_path)
    e = ov.ack(tmp_path, "inv-003", "store cost", law="Run cost must never be stored")
    assert e["law"] == "Run cost must never be stored"
    assert ov.load(tmp_path)["overrides"][0]["law"] == "Run cost must never be stored"


def test_ack_without_law_defaults_to_empty(tmp_path):
    _git_repo(tmp_path)
    assert ov.ack(tmp_path, "inv-003", "r")["law"] == ""


def test_ratification_helpers_are_gone():
    """merging is the ratification — nothing applies an override after the fact."""
    assert not hasattr(ov, "pending_ratification")
    assert not hasattr(ov, "archive")
```

```python
# REPLACE the two override-ratify tests in tests/test_override_subcommands.py with:
def test_override_ack_removes_the_rule_and_stamps_the_blueprint(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "description": "Run cost must never be stored",
         "forced_by": "Domain law inv-subscribe-workflow-003: ledger is the truth."},
        {"id": "arch-001", "description": "keep me"},
    ]}))
    (tmp_path / ".archie" / "blueprint.json").write_text(json.dumps({"domain_invariants": [
        {"id": "inv-subscribe-workflow-003", "invariant": "cost is never stored"},
        {"id": "inv-other", "invariant": "keep me"},
    ]}))
    r = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                        "inv-003", "--reason", "dashboard reads total_cost"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["acked"] == "inv-003" and out["rule_removed"] is True

    rules = json.loads((tmp_path / ".archie" / "rules.json").read_text())["rules"]
    assert [x["id"] for x in rules] == ["arch-001"]           # removed from the branch

    bp = json.loads((tmp_path / ".archie" / "blueprint.json").read_text())
    inv = next(x for x in bp["domain_invariants"] if x["id"] == "inv-subscribe-workflow-003")
    assert inv["status"] == "overridden"
    assert inv["override"]["reason"] == "dashboard reads total_cost"
    assert "Gabor" in inv["override"]["authorized_by"] or inv["override"]["authorized_by"]
    assert next(x for x in bp["domain_invariants"] if x["id"] == "inv-other").get("status") is None

    e = ov.active(tmp_path)["inv-003"]
    assert e["law"] == "Run cost must never be stored"        # snapshot survives removal
    assert e["reason"] == "dashboard reads total_cost"


def test_override_ack_is_idempotent_and_survives_missing_rule(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": []}))
    r1 = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                         "ghost-9", "--reason", "not in rules.json"],
                        capture_output=True, text=True)
    assert r1.returncode == 0
    assert json.loads(r1.stdout.strip().splitlines()[-1])["rule_removed"] is False
    r2 = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                         "ghost-9", "--reason", "different words"],
                        capture_output=True, text=True)
    assert r2.returncode == 0
    assert len(ov.load(tmp_path)["overrides"]) == 1           # first ruling kept


def test_override_ratify_command_is_gone(tmp_path):
    _git_repo(tmp_path)
    r = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode != 0                                   # unknown subcommand
```

```python
# append to tests/test_workflow_override_text.py
def test_sync_skill_no_longer_references_ratify():
    text = (_WF / "sync" / "SKILL.md").read_text()
    assert "override-ratify" not in text
    assert "merging" in text.lower()          # merge is the ratification


def test_deep_scan_tombstones_read_overrides_json():
    for step in ("step-5d-product.md", "step-6-rule-synthesis.md"):
        text = (_WF / "deep-scan" / "steps" / step).read_text()
        assert "overrides.json" in text
        assert "overrides_history.jsonl" not in text
```

```python
# append to tests/test_renderer_overrides.py
def test_overridden_law_is_labelled_retired_not_ratified():
    bp = {"domain_invariants": [
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "B", "category": "billing",
         "status": "overridden",
         "override": {"reason": "store cost", "authorized_by": "Gabor <g@e.com>", "branch": "demo/x"}},
    ]}
    body = renderer._build_product_laws_rule(bp)["body"]
    assert "retired" in body.lower()
    assert "ratified" not in body.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_overrides.py tests/test_override_subcommands.py tests/test_workflow_override_text.py tests/test_renderer_overrides.py -q`
Expected: FAIL — `ack()` has no `law`; `pending_ratification` still exists; `override-ack` does not remove the rule; `override-ratify` still runs; SKILL still names it.

- [ ] **Step 3: Write the implementation**

**(a) `overrides.py`** — add `law` to `ack`, delete the ratification helpers:

```python
def ack(root, rule_id: str, reason: str, law: str = "", now: str | None = None) -> dict:
    """Record a human-authorized override. ONLY call after the user explicitly
    confirmed crossing the rule in conversation. Idempotent per (rule_id, branch):
    the first ruling is kept.

    `law` snapshots the rule's description at ack time. The caller removes the rule
    from rules.json in the same step, so this entry becomes the only place the
    retired law's text survives."""
    data = load(root)
    branch = current_branch(root)
    for e in data["overrides"]:
        if (e.get("rule_id") == rule_id and e.get("branch") == branch
                and e.get("status") == "acked"):
            return e
    entry = {
        "rule_id": rule_id,
        "law": law,
        "reason": reason,
        "authorized_by": git_user(root),
        "branch": branch,
        "created_at": now or _now(),
        "status": "acked",
    }
    data["overrides"].append(entry)
    save(root, data)
    return entry
```
Delete `pending_ratification`, `archive`, and the `HISTORY = "overrides_history.jsonl"` constant. Update `active`'s docstring: drop the "pending bookkeeping by override-ratify" clause — an acked entry is simply the record of an authorized retirement.

**(b) `sync.py`** — `cmd_override_ack` absorbs the (relocated) removal logic; `cmd_override_ratify` is deleted:

```python
def cmd_override_ack(root: Path, rule_id: str, reason: str) -> int:
    """Record a human-authorized rule override AND apply it to the branch.

    Agent-run ONLY — and only after the user explicitly confirmed crossing the rule
    in conversation. This writes the contract change into the source of truth: the
    rule leaves rules.json, the blueprint invariant is stamped `overridden`, and the
    reason + authorizer + a snapshot of the law text land in overrides.json. The PR
    then carries a real rules diff, the review judges it, and MERGING RATIFIES IT —
    there is no separate ratify step."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    if not rule_id or not reason:
        print('usage: sync.py override-ack <root> <rule_id> --reason "..."', file=sys.stderr)
        return 1
    import overrides as _ov

    archie = root / ".archie"
    law, removed = "", False
    for fname in ("rules.json", "platform_rules.json"):
        rp = archie / fname
        try:
            data = json.loads(rp.read_text())
        except Exception:
            continue
        items = data.get("rules", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        hit = next((r for r in items if isinstance(r, dict) and r.get("id") == rule_id), None)
        if hit is None:
            continue
        law = str(hit.get("description", ""))
        kept = [r for r in items if not (isinstance(r, dict) and r.get("id") == rule_id)]
        if isinstance(data, dict):
            data["rules"] = kept
        else:
            data = kept
        try:
            rp.write_text(json.dumps(data, indent=2) + "\n")
            removed = True
        except Exception:
            pass
        break

    e = _ov.ack(root, rule_id, reason, law=law)

    # Stamp the blueprint invariant(s) this rule is grounded in, so the rendered
    # product-laws stop stating a retired law as live truth and the review engine
    # stops enforcing it (selector skips `overridden`).
    ids = {rule_id} | _ov.rule_aliases(root, rule_id)
    bp_p = archie / "blueprint.json"
    try:
        bp = json.loads(bp_p.read_text())
        for inv in bp.get("domain_invariants") or []:
            if isinstance(inv, dict) and inv.get("id") in ids:
                inv["status"] = "overridden"
                inv["override"] = {"reason": reason,
                                   "authorized_by": e["authorized_by"],
                                   "branch": e["branch"]}
        bp_p.write_text(json.dumps(bp, indent=2) + "\n")
    except Exception:
        pass

    print(json.dumps({"acked": e["rule_id"], "branch": e["branch"],
                      "by": e["authorized_by"], "rule_removed": removed}))
    return 0
```
Delete the whole `cmd_override_ratify` function, its `if cmd == "override-ratify":` dispatch entry, and its `_usage()` line. Update `_usage()`'s `override-ack` line to `(record + apply a user-authorized rule retirement onto this branch)`.

Note the ordering: the rule is read for its `law` **before** removal, and `rule_aliases` is called **after** `ack` (it reads `forced_by` from `rules.json`) — so it must run while the rule is still present, or fall back. To keep it simple and correct, capture aliases *before* the removal loop:
```python
    ids = {rule_id} | _ov.rule_aliases(root, rule_id)   # BEFORE the rule leaves rules.json
```
and move that line above the removal loop. (The `ack` call stays where it is.)

**(c) `renderer.py`** — in `_build_product_laws_rule`, replace:
```python
            state = ("staged on `" + o.get("branch", "?") + "`"
                     if x.get("status") == "override_staged" else "ratified")
```
with:
```python
            state = ("staged on `" + o.get("branch", "?") + "`"
                     if x.get("status") == "override_staged" else "retired")
```

**(d) Workflow texts.** In `archie/assets/workflow/sync/SKILL.md`, replace the whole "Step 2b" section body with:
```markdown
### Step 2b — Fold override acknowledgments

Read `.archie/overrides.json`. For each entry with `status: "acked"` whose `branch` is
the CURRENT branch and which has no staged claim yet, record the break through the
normal Step 2 flow as a staged contract amendment: a `rule` claim titled
`override: <rule_id>`, rationale = the entry's `reason`, evidence_files = the files the
violating change touched.

The rule itself is already gone from `rules.json` and the blueprint invariant is already
stamped `overridden` — `override-ack` did that when the user authorized it. There is no
ratify step: **merging the PR is the ratification.** Never delete or edit an override
entry by hand.
```
In both `deep-scan/steps/step-5d-product.md` and `step-6-rule-synthesis.md`, replace every mention of `.archie/overrides.json` and `.archie/overrides_history.jsonl` with just `.archie/overrides.json` (drop the history file; nothing writes it now). Keep the "do not re-derive" / "do not carry forward" wording — the tests pin it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_overrides.py tests/test_override_subcommands.py tests/test_workflow_override_text.py tests/test_renderer_overrides.py tests/test_align_check_overrides.py tests/test_pre_validate_overrides.py -q`
Expected: all pass. The two old `override-ratify` tests are **replaced** (not weakened) by the new ones; `test_archive_moves_entry_to_history` and `test_pending_ratification_only_foreign_branch_entries` in `tests/test_overrides.py` are now obsolete — **delete them** and name the deletions in your report.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/overrides.py archie/standalone/sync.py archie/standalone/renderer.py \
        archie/assets/workflow/ tests/
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): ack writes the contract change onto the branch; merging is the ratification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `contract_delta.py` — authorized retirements vs judged changes

**Files:**
- Create: `archie/standalone/contract_delta.py`
- Test: `tests/test_contract_delta.py`

**Interfaces:**
- Consumes: `overrides.load(root)`, `overrides.rule_aliases(root, rule_id)`; and from `intent_review`: `load_branch_file`, `fetch_base_file`, `normalize_rules`, `glob_ledger`, `build_changed_items`, `retained_rules`, `build_prompt`, `call_anthropic`, `finalize_findings`, `RULE_FILES`.
- Produces:
  - `retirements(root) -> list[dict]` — per acked override: `rule_id`, `law`, `reason`, `authorized_by`, `date` (`YYYY-MM-DD`), `invariant_ids` (sorted).
  - `acked_rule_ids(root) -> set[str]` — every acked `rule_id` **plus** its invariant aliases.
  - `is_authorized(item, acked_ids) -> bool` — a changed item explained by an override.
  - `judged_changes(root, base_ref, api_key) -> dict` — `{"items": list, "findings": list, "model_failed": bool}`, where `items` are the **unexplained** changed items only. **No model call when `items` is empty.**

`is_authorized` is source-agnostic: a changed item is explained iff its id (branch item's, else base item's) is an acked id, AND either the item is a `remove` (the authorized retirement) or an `update` whose `fields_changed` are only the stamp (`status` / `override`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_contract_delta.py
import json
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import contract_delta as cd  # noqa: E402
import overrides as ov  # noqa: E402


def _project(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "demo/x", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Gabor Bakos"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "g@e.com"], check=True)
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "description": "Run cost must never be stored",
         "forced_by": "Domain law inv-subscribe-workflow-003: ledger is the truth."},
    ]}))


# ---- retirements ----
def test_retirements_use_the_law_snapshot(tmp_path):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "dashboard reads total_cost",
           law="Run cost must never be stored")
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": []}))  # rule now gone
    out = cd.retirements(tmp_path)
    assert len(out) == 1
    c = out[0]
    assert c["law"] == "Run cost must never be stored"     # snapshot, not a live lookup
    assert c["reason"] == "dashboard reads total_cost"
    assert c["authorized_by"] == "Gabor Bakos <g@e.com>"
    assert len(c["date"]) == 10
    assert c["invariant_ids"] == []      # forced_by is gone with the rule; snapshot only


def test_retirements_fall_back_to_rules_json_for_legacy_entries(tmp_path):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")                        # no law snapshot
    out = cd.retirements(tmp_path)
    assert out[0]["law"] == "Run cost must never be stored"  # read from the live rule
    assert out[0]["invariant_ids"] == ["inv-subscribe-workflow-003"]


def test_acked_rule_ids_includes_aliases(tmp_path):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    assert cd.acked_rule_ids(tmp_path) == {"inv-003", "inv-subscribe-workflow-003"}


def test_missing_files_degrade_to_empty(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert cd.retirements(tmp_path) == []
    assert cd.acked_rule_ids(tmp_path) == set()


# ---- is_authorized ----
def test_authorized_rule_removal_is_explained():
    item = {"diff_op": "remove", "base_item": {"id": "inv-003"}, "branch_item": None}
    assert cd.is_authorized(item, {"inv-003"}) is True


def test_authorized_blueprint_stamp_is_explained():
    item = {"diff_op": "update", "base_item": {"id": "inv-subscribe-workflow-003"},
            "branch_item": {"id": "inv-subscribe-workflow-003"},
            "fields_changed": ["status", "override"]}
    assert cd.is_authorized(item, {"inv-subscribe-workflow-003"}) is True


def test_unauthorized_removal_is_not_explained():
    item = {"diff_op": "remove", "base_item": {"id": "inv-004"}, "branch_item": None}
    assert cd.is_authorized(item, {"inv-003"}) is False


def test_substantive_edit_to_an_acked_invariant_is_not_explained():
    """An override retires a law — it does not licence rewriting its text."""
    item = {"diff_op": "update", "base_item": {"id": "inv-003"},
            "branch_item": {"id": "inv-003"}, "fields_changed": ["status", "invariant"]}
    assert cd.is_authorized(item, {"inv-003"}) is False


def test_add_is_never_explained_by_an_override():
    item = {"diff_op": "add", "base_item": None, "branch_item": {"id": "inv-003"}}
    assert cd.is_authorized(item, {"inv-003"}) is False


# ---- judged_changes ----
def _stub_ir(monkeypatch, items):
    import intent_review as ir
    monkeypatch.setattr(ir, "load_branch_file", lambda *a: (True, {}, None))
    monkeypatch.setattr(ir, "fetch_base_file", lambda *a: (True, {}, None))
    monkeypatch.setattr(ir, "glob_ledger", lambda *a: [])
    monkeypatch.setattr(ir, "build_changed_items", lambda *a: items)
    monkeypatch.setattr(ir, "retained_rules", lambda *a: [])
    monkeypatch.setattr(ir, "build_prompt", lambda *a: ("sys", "usr"))
    return ir


def test_only_authorized_changes_makes_no_model_call(tmp_path, monkeypatch):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    ir = _stub_ir(monkeypatch, [{"diff_op": "remove", "base_item": {"id": "inv-003"},
                                 "branch_item": None}])
    monkeypatch.setattr(ir, "call_anthropic",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not judge")))
    out = cd.judged_changes(tmp_path, "origin/main", "sk-test")
    assert out == {"items": [], "findings": [], "model_failed": False}


def test_unexplained_change_is_judged_once(tmp_path, monkeypatch):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    authorized = {"diff_op": "remove", "base_item": {"id": "inv-003"}, "branch_item": None}
    unexplained = {"diff_op": "update", "base_item": {"id": "inv-007"},
                   "branch_item": {"id": "inv-007"}, "fields_changed": ["description"]}
    calls = []
    ir = _stub_ir(monkeypatch, [authorized, unexplained])
    monkeypatch.setattr(ir, "call_anthropic", lambda s, u, k, **kw: calls.append(1) or [{}])
    monkeypatch.setattr(ir, "finalize_findings",
                        lambda mf, ci, cl: [{"type": "silent_weakening", "change_summary": "cap raised",
                                             "diff_op": "update", "layer": 1,
                                             "colliding_rules": ["inv-006"]}])
    out = cd.judged_changes(tmp_path, "origin/main", "sk-test")
    assert len(calls) == 1
    assert out["items"] == [unexplained]          # the authorized removal is filtered out
    assert out["findings"][0]["type"] == "silent_weakening"
    assert out["model_failed"] is False


def test_model_failure_is_disclosed_not_swallowed(tmp_path, monkeypatch):
    _project(tmp_path)
    ir = _stub_ir(monkeypatch, [{"diff_op": "add", "base_item": None,
                                 "branch_item": {"id": "new-1"}}])
    monkeypatch.setattr(ir, "call_anthropic",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429")))
    out = cd.judged_changes(tmp_path, "origin/main", "sk-test")
    assert out["model_failed"] is True and out["findings"] == []
    assert out["items"]                            # the deterministic diff still surfaces


def test_no_api_key_marks_model_failed(tmp_path, monkeypatch):
    _project(tmp_path)
    _stub_ir(monkeypatch, [{"diff_op": "add", "base_item": None, "branch_item": {"id": "n"}}])
    out = cd.judged_changes(tmp_path, "origin/main", "")
    assert out["model_failed"] is True             # a diff we could not judge is NOT clean


def test_unresolvable_base_ref_degrades(tmp_path, monkeypatch):
    import intent_review as ir
    monkeypatch.setattr(ir, "load_branch_file", lambda *a: (True, {}, None))
    monkeypatch.setattr(ir, "fetch_base_file", lambda *a: (False, None, "bad object"))
    out = cd.judged_changes(tmp_path, "origin/nope", "sk-test")
    assert out == {"items": [], "findings": [], "model_failed": False}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_contract_delta.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'contract_delta'`.

- [ ] **Step 3: Write the implementation**

```python
# archie/standalone/contract_delta.py
"""The contract delta: what merging this PR actually accepts.

`override-ack` writes an authorized retirement straight into the source of truth —
the rule leaves rules.json, the blueprint invariant is stamped `overridden`. So the
PR carries a real rules diff, and there is one carrier, not two.

That diff has two halves, and only one needs a model:

  AUTHORIZED — a removal (or the stamp that accompanies it) whose rule id has an
    override entry. The user already decided at the stop-and-confirm prompt; their
    reason is the justification. Reading it is deterministic and free.

  UNEXPLAINED — everything else: rules added or modified by /archie-sync, and any
    removal nobody authorized. Whether these silently weaken or contradict a RETAINED
    rule is a judgment call. `intent_review` already makes it: the script owns the
    deterministic diff (diff_op / layer / ref), the model only judges, and the call
    happens ONLY when unexplained changes exist.

This module composes. It never re-implements the differ.

Import convention: bare-name sibling imports via sys.path (Python 3.9).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
import overrides as _ov       # noqa: E402
import intent_review as _ir   # noqa: E402

# The only fields override-ack adds to a blueprint invariant. An `update` touching
# exactly these is the retirement stamp; anything more is a substantive rewrite that
# an override does not licence.
_STAMP_FIELDS = {"status", "override"}


# ---------------------------------------------------------------- retirements

def _rules(root) -> dict:
    """rule_id -> rule dict, for legacy entries with no law snapshot. Degrades to {}."""
    try:
        data = json.loads((Path(root) / ".archie" / "rules.json").read_text())
        items = data.get("rules", data) if isinstance(data, dict) else data
        return {r["id"]: r for r in items if isinstance(r, dict) and r.get("id")}
    except Exception:
        return {}


def retirements(root) -> list:
    """One entry per acked override: the law, why, and who authorized it.
    Deterministic — the user already decided at the confirm prompt."""
    by_id = None
    out = []
    for e in _ov.load(root).get("overrides", []):
        if e.get("status") != "acked" or not e.get("rule_id"):
            continue
        rid = e["rule_id"]
        law = str(e.get("law", ""))
        if not law:                       # legacy entry (pre-snapshot): read the live rule
            if by_id is None:
                by_id = _rules(root)
            law = str((by_id.get(rid) or {}).get("description", ""))
        out.append({
            "rule_id": rid,
            "law": law,
            "reason": str(e.get("reason", "")),
            "authorized_by": str(e.get("authorized_by", "")),
            "date": str(e.get("created_at", ""))[:10],
            "invariant_ids": sorted(_ov.rule_aliases(root, rid)),
        })
    return out


def acked_rule_ids(root) -> set:
    """Every acknowledged rule id, PLUS the invariant ids those rules are grounded in.
    Reviewers skip these: re-deriving "you violated inv-003" after the user said so
    costs Opus money and tells them nothing."""
    ids = set()
    for c in retirements(root):
        ids.add(c["rule_id"])
        ids.update(c["invariant_ids"])
    return ids


# ------------------------------------------------------------- judged changes

def is_authorized(item, acked_ids) -> bool:
    """Is this changed item explained by an override the user authorized?

    Source-agnostic: match on the item's id, then on the SHAPE of the change. A
    removal is the retirement itself. An update is only explained when it changes
    nothing but the retirement stamp — an override retires a law, it does not licence
    rewriting the law's text. An add is never explained.
    """
    bi = item.get("base_item") or {}
    ci = item.get("branch_item") or {}
    rid = (ci.get("id") if isinstance(ci, dict) else None) or \
          (bi.get("id") if isinstance(bi, dict) else None)
    if not rid or rid not in acked_ids:
        return False
    op = item.get("diff_op")
    if op == "remove":
        return True
    if op == "update":
        changed = set(item.get("fields_changed") or [])
        return bool(changed) and changed <= _STAMP_FIELDS
    return False


_EMPTY = {"items": [], "findings": [], "model_failed": False}


def judged_changes(root, base_ref, api_key) -> dict:
    """Deterministic source-of-truth diff, minus the authorized retirements, plus ONE
    model judgment of whatever is left.

    Returns {"items", "findings", "model_failed"}. `model_failed` True means the
    source of truth changed in ways nobody authorized and we could NOT judge them —
    the caller must disclose that rather than render a clean review.
    """
    root = Path(root)
    try:
        b_exists, branch_bp, _ = _ir.load_branch_file(root, ".archie/blueprint.json")
        if not b_exists or not isinstance(branch_bp, dict):
            return dict(_EMPTY)
        _, base_bp, base_err = _ir.fetch_base_file(root, base_ref, ".archie/blueprint.json")
        if base_err:
            # Base unresolvable: do NOT degrade to an empty baseline and claim
            # "everything is new". Say nothing rather than something wrong.
            return dict(_EMPTY)
        base_bp = base_bp if isinstance(base_bp, dict) else {}

        base_rules, branch_rules = [], []
        for rel in _ir.RULE_FILES:
            _, base_raw, _ = _ir.fetch_base_file(root, base_ref, rel)
            _, branch_raw, _ = _ir.load_branch_file(root, rel)
            base_rules.extend(_ir.normalize_rules(base_raw))
            branch_rules.extend(_ir.normalize_rules(branch_raw))

        claims = _ir.glob_ledger(root, base_ref)
        all_items = _ir.build_changed_items(base_bp, branch_bp, base_rules, branch_rules, claims)
        acked = acked_rule_ids(root)
        items = [it for it in all_items if not is_authorized(it, acked)]
    except Exception:
        return dict(_EMPTY)

    if not items:
        return dict(_EMPTY)          # nothing unexplained -> no model call

    if not api_key:
        return {"items": items, "findings": [], "model_failed": True}

    try:
        retained = _ir.retained_rules(base_rules, items)
        system, user = _ir.build_prompt(items, retained, claims)
        raw = _ir.call_anthropic(system, user, api_key)
        findings = _ir.finalize_findings(raw, items, claims)
        return {"items": items, "findings": findings, "model_failed": False}
    except Exception:
        return {"items": items, "findings": [], "model_failed": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_contract_delta.py tests/test_overrides.py tests/test_intent_review.py -q`
Expected: all pass (14 new).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/contract_delta.py tests/test_contract_delta.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(review): contract_delta — authorized retirements (free) vs judged changes (one Haiku call)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `render_verdict` rewrite — contract → unauthorized → code review

**Files:**
- Modify: `archie/standalone/delivery_review.py` (`render_verdict`, def ~line 72 — read the real body; anchors drift)
- Test: `tests/test_delivery_review.py` (append)

**Interfaces:**
- Consumes: `contract_delta.retirements(root)` and `contract_delta.judged_changes(...)` output (Task 2).
- Produces: `render_verdict(verdict, confirmed, spec=None, retired=None, judged=None, unauthorized=None) -> str`; module constant `DELIVERY_MARKER = "<!-- archie-delivery-review -->"`.
  **The signature changes** — `acked`/`stale_acks` are gone. Task 4 updates the call sites. Positional `(verdict, confirmed, spec)` is preserved.

Section order (this order IS the product):
1. Engine-failure banner (keep existing behavior).
2. `### ⛔ Contract changes — merging this PR accepts them (N)` — retirement table, then judged-change findings grouped by `type`, then the closing italic line.
3. `### 🚨 Unauthorized law violations (N) — not covered by any override`
4. `### 🔍 Code review — N findings`, grouped by lens; order `security, concurrency, resource-perf, null-safety`, then any others alphabetically.
5. Footer summary line.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_delivery_review.py`)

```python
_RETIRED = [{"rule_id": "inv-003", "law": "Run cost must never be stored",
             "reason": "dashboard reads total_cost", "authorized_by": "Gabor <g@e.com>",
             "date": "2026-07-08", "invariant_ids": ["inv-subscribe-workflow-003"]}]


def test_render_verdict_leads_with_contract_delta():
    import delivery_review as dr
    body = dr.render_verdict({"breaks": 0}, [], {}, retired=_RETIRED)
    assert "Contract changes" in body
    assert body.index("Contract changes") < body.index("Code review")
    assert "inv-003" in body and "Run cost must never be stored" in body
    assert "Gabor" in body and "dashboard reads total_cost" in body
    assert "become the contract" in body
    assert "Built the intent?" not in body        # intent grading is GONE
    assert "criteria met" not in body


def test_render_verdict_shows_judged_rule_changes_with_verdicts():
    import delivery_review as dr
    judged = {"items": [{"ref": "r1"}],
              "findings": [{"type": "silent_weakening", "change_summary": "rerun cap 7 -> 12",
                            "diff_op": "update", "layer": 1, "colliding_rules": ["inv-007"]}],
              "model_failed": False}
    body = dr.render_verdict({"breaks": 0}, [], {}, judged=judged)
    assert "Silent weakening" in body
    assert "rerun cap 7 -> 12" in body
    assert "inv-007" in body                       # the retained rule it collides with


def test_render_verdict_discloses_unjudged_rule_changes():
    import delivery_review as dr
    judged = {"items": [{"ref": "r1"}], "findings": [], "model_failed": True}
    body = dr.render_verdict({"breaks": 0}, [], {}, judged=judged)
    assert "could not be judged" in body.lower()
    assert "1 unexplained source-of-truth change" in body


def test_render_verdict_clean_rule_changes_say_so():
    import delivery_review as dr
    judged = {"items": [{"ref": "r1"}], "findings": [], "model_failed": False}
    body = dr.render_verdict({"breaks": 0}, [], {}, judged=judged)
    assert "consistent with the retained rules" in body


def test_render_verdict_groups_code_review_by_lens_security_first():
    import delivery_review as dr
    confirmed = [
        {"kind": "behavioral_break", "problem_statement": "unbounded dict",
         "anchor": {"file": "pool_cache.py", "line": 22}, "source": "universal:resource-perf"},
        {"kind": "behavioral_break", "problem_statement": "cache poisoning via urlparse",
         "anchor": {"file": "pool_cache.py", "line": 33}, "source": "universal:security"},
    ]
    body = dr.render_verdict({"breaks": 2}, confirmed, {})
    assert "Code review — 2 findings" in body
    assert body.index("security") < body.index("resource-perf")
    assert "cache poisoning via urlparse" in body


def test_render_verdict_unauthorized_section_only_when_present():
    import delivery_review as dr
    unauth = [{"kind": "conformance_break", "problem_statement": "violates inv-004: load_page first",
               "anchor": {"file": "persister.py", "line": 1768}}]
    body = dr.render_verdict({"breaks": 0}, [], {}, unauthorized=unauth)
    assert "Unauthorized law violations (1)" in body and "inv-004" in body
    assert "Unauthorized law violations" not in dr.render_verdict({"breaks": 0}, [], {})


def test_render_verdict_sanitizes_contract_fields():
    import delivery_review as dr
    retired = [{"rule_id": "inv-003", "law": "<script>x</script>", "reason": "@everyone ping",
                "authorized_by": "<b>evil</b>", "date": "2026-07-08", "invariant_ids": []}]
    judged = {"items": [{"ref": "r"}], "model_failed": False,
              "findings": [{"type": "contradiction", "change_summary": "<img src=x>",
                            "diff_op": "add", "layer": 1, "colliding_rules": ["<i>r</i>"]}]}
    body = dr.render_verdict({"breaks": 0}, [], {}, retired=retired, judged=judged)
    for bad in ("<script>", "<b>evil</b>", "<img src=x>", "<i>r</i>"):
        assert bad not in body


def test_render_verdict_engine_failed_banner_survives_rewrite():
    import delivery_review as dr
    body = dr.render_verdict({"breaks": 0}, [], {"review_engine_failed": True})
    assert "REVIEW ENGINE FAILED" in body and "not assessed" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_delivery_review.py -q -k "contract or judged or lens or unauthorized or unjudged"`
Expected: FAIL — `render_verdict()` got an unexpected keyword argument `retired`.

- [ ] **Step 3: Write the implementation**

Add the module constant near the top of `delivery_review.py` (Task 5 also uses it):
```python
DELIVERY_MARKER = "<!-- archie-delivery-review -->"
```

Replace the whole body of `render_verdict` with:

```python
_LENS_ORDER = ["security", "concurrency", "resource-perf", "null-safety"]
_JUDGE_HEADERS = {
    "silent_weakening": "⚠️ Silent weakening / removal",
    "contradiction": "⚠️ Contradiction with a retained rule",
    "behavior_violates_rule": "⚠️ Behavior may violate a rule",
}
_JUDGE_ORDER = ["silent_weakening", "contradiction", "behavior_violates_rule"]


def _lens_of(f) -> str:
    """The reviewer that produced this finding: 'universal:security' -> 'security'."""
    return str(f.get("source", "")).split(":")[-1] or "other"


def render_verdict(verdict: dict, confirmed: list, spec=None,
                   retired=None, judged=None, unauthorized=None) -> str:
    """Render the single PR comment.

    Order is the product. The contract delta is what merging ACCEPTS, so it leads:
    the laws the user authorized retiring (with their reason), plus any change
    /archie-sync made that nobody authorized, judged against the retained rules. Code
    review follows as the evidence a human acts on. There is no intent grading — the
    acceptance criteria were extracted from the PR body, so grading the PR against
    them was circular.
    """
    spec = spec or {}
    retired = retired or []
    judged = judged or {}
    unauthorized = unauthorized or []
    j_items = judged.get("items") or []
    j_findings = judged.get("findings") or []
    j_failed = bool(judged.get("model_failed"))
    engine_failed = bool(spec.get("review_engine_failed"))

    lines = [DELIVERY_MARKER, "## Archie review", ""]
    if engine_failed:
        lines += ["> 🛑 **REVIEW ENGINE FAILED — no code review was performed.** "
                  "Do NOT treat this comment as a green verdict. Check the workflow "
                  "logs for `[archie] review core failed`.", ""]

    n_contract = len(retired) + len(j_items)
    if n_contract:
        lines += [f"### ⛔ Contract changes — merging this PR accepts them ({n_contract})", ""]

    if retired:
        lines += ["| Law | Change | Why | Authorized |", "|---|---|---|---|"]
        for c in retired:
            law = _sanitize(c.get("law", "")) or "_(law text unavailable)_"
            lines.append(
                f"| `{_sanitize(c.get('rule_id', '?'))}` {law} | **RETIRE** | "
                f"{_sanitize(c.get('reason', ''))} | {_sanitize(c.get('authorized_by', '?'))}, "
                f"{_sanitize(c.get('date', ''))} |")
        lines.append("")

    if j_items:
        n = len(j_items)
        lines += [f"**{n} unexplained source-of-truth change{'s' if n != 1 else ''}** "
                  "in `rules.json` / `blueprint.json` — no override authorizes "
                  f"{'them' if n != 1 else 'it'}.", ""]
        if j_failed:
            lines += ["⚠️ **These could not be judged** — the model call failed. The source "
                      "of truth changed but was **not** checked against the retained rules. "
                      "Re-run the check or review the diff manually.", ""]
        elif not j_findings:
            lines += ["No findings — consistent with the retained rules.", ""]
        else:
            for flag in _JUDGE_ORDER:
                group = [f for f in j_findings if f.get("type") == flag]
                if not group:
                    continue
                lines.append(f"**{_JUDGE_HEADERS[flag]}**")
                for f in group:
                    collides = ""
                    if f.get("colliding_rules"):
                        collides = " · collides with **" + ", ".join(
                            _sanitize(r) for r in f["colliding_rules"]) + "**"
                    lines.append(f"- {_sanitize(f.get('change_summary', ''))} "
                                 f"({_sanitize(f.get('diff_op', ''))}, "
                                 f"Layer {_sanitize(str(f.get('layer', '')))}){collides}")
                lines.append("")

    if n_contract:
        lines += ["*After merge these changes become the contract. The next deep scan "
                  "re-derives this area from the code.*", ""]

    def _finding(f):
        a = f.get("anchor", {}) or {}
        return (f"- `{_sanitize(a.get('file', ''))}:{_sanitize(str(a.get('line', '')))}` — "
                f"{_sanitize(f.get('problem_statement', ''))}")

    if unauthorized:
        lines += [f"### 🚨 Unauthorized law violations ({len(unauthorized)}) — "
                  "not covered by any override", ""]
        lines += [_finding(f) for f in unauthorized] + [""]

    if engine_failed:
        lines += ["### 🔍 Code review", "", "_not assessed — no reviewer ran._", ""]
    else:
        by_lens = {}
        for f in confirmed:
            by_lens.setdefault(_lens_of(f), []).append(f)
        ordered = [l for l in _LENS_ORDER if l in by_lens] + \
                  sorted(k for k in by_lens if k not in _LENS_ORDER)
        lines += [f"### 🔍 Code review — {len(confirmed)} findings", ""]
        if not confirmed:
            lines.append("_No defects found._")
        for lens in ordered:
            fs = by_lens[lens]
            lines += [f"**{lens} ({len(fs)})**"] + [_finding(f) for f in fs] + [""]

    lines += ["---",
              f"*Contract: {n_contract} change(s), {len(unauthorized)} unauthorized. "
              f"Code: {len(confirmed)} finding(s).*"]
    return "\n".join(lines)
```

Delete from the module: the old `unmet_ids` computation, the `crit` loop, and the `**Built the intent?**` / `**Broke anything?**` / `**Possible issues**` / `**⚠️ Acknowledged overrides**` / `**Stale overrides**` blocks, and the `_Story wrong?` footer. Keep `_sanitize` and `partition_for_verdict` — `sync_review.py` imports the latter, so deleting it breaks the local review.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_delivery_review.py -q`
Expected: the 8 new tests pass. Old tests asserting `"Built the intent?"`, `"criteria met"`, `"Acknowledged overrides"`, `"Stale overrides"`, or `"Possible issues"` will now FAIL — correct: those assertions pin behavior this task deliberately removes. **Delete those obsolete tests** (never weaken a test to keep it green) and name each deletion in your report. `test_render_verdict_discloses_diff_truncation`: if you kept the truncation note, port it to the new signature; if you removed the note, delete the test and say so.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/test_delivery_review.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(review): one comment — contract delta leads, code review backs it

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Wire `run_pr_gate` — compose contract, split unauthorized

**Files:**
- Modify: `archie/standalone/delivery_review.py` (`run_pr_gate` — read the real body)
- Test: `tests/test_delivery_review.py` (append)

**Interfaces:**
- Consumes: `contract_delta.retirements(root)`, `contract_delta.judged_changes(root, base_ref, api_key)` (Task 2); `render_verdict(verdict, confirmed, spec, retired, judged, unauthorized)` (Task 3).
- Produces: `split_findings(findings) -> (code_review, unauthorized)`.

Classification: a finding is **unauthorized** iff `kind == "conformance_break"` (from the invariant specialist / conformance reviewer). After Task 7 the specialist never runs on acked laws, so any conformance finding that survives is uncovered by an override. Everything else is code review.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_delivery_review.py`)

```python
def test_split_findings_separates_conformance_from_code_review():
    import delivery_review as dr
    findings = [
        {"kind": "conformance_break", "problem_statement": "violates inv-004"},
        {"kind": "behavioral_break", "problem_statement": "null deref"},
    ]
    code, unauth = dr.split_findings(findings)
    assert [f["problem_statement"] for f in code] == ["null deref"]
    assert [f["problem_statement"] for f in unauth] == ["violates inv-004"]


def test_pr_gate_renders_contract_even_when_review_core_dies(tmp_path, monkeypatch):
    """The contract delta is deterministic — an engine crash must not hide it."""
    import delivery_review as dr
    import review_core
    import contract_delta as cd
    monkeypatch.setattr(review_core, "run_review",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(cd, "retirements", lambda root: _RETIRED)
    monkeypatch.setattr(cd, "judged_changes",
                        lambda *a: {"items": [], "findings": [], "model_failed": False})
    captured = {}
    monkeypatch.setattr(dr, "render_verdict",
                        lambda v, c, s, **k: captured.update(k) or "body")
    import subprocess as _sp
    _sp.run(["git", "init", "-q", str(tmp_path)])
    (tmp_path / ".archie").mkdir()
    ev = tmp_path / "event.json"
    ev.write_text(json.dumps({"pull_request": {"number": 9, "title": "t", "body": "b",
                                               "base": {"ref": "main", "sha": ""},
                                               "head": {"ref": "x", "sha": ""}}}))
    dr.run_pr_gate(tmp_path, {"GITHUB_EVENT_PATH": str(ev)})
    assert captured["retired"] == _RETIRED        # contract survived the crash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_delivery_review.py -q -k "split_findings or contract_even_when"`
Expected: FAIL — no attribute `split_findings`.

- [ ] **Step 3: Write the implementation**

Add at module scope:

```python
def split_findings(findings):
    """(code_review, unauthorized). Conformance findings are law violations; the
    specialist skips acked laws, so any survivor is uncovered by an override."""
    unauth = [f for f in findings if f.get("kind") == "conformance_break"]
    code = [f for f in findings if f.get("kind") != "conformance_break"]
    return code, unauth
```

In `run_pr_gate`, immediately **after** the blueprint load (step 5) and **before** the review-core call — so it survives an engine crash — insert:

```python
    # 5b. Contract delta — deterministic authorized retirements + (only when the
    #     source of truth moved in ways nobody authorized) one Haiku judgment.
    retired, judged = [], {}
    try:
        import contract_delta as _cd
        retired = _cd.retirements(root)
        base_ref_full = pr_meta.get("base_sha") or f"origin/{env.get('GITHUB_BASE_REF', '')}"
        judged = _cd.judged_changes(root, base_ref_full, env.get("ANTHROPIC_API_KEY", ""))
    except Exception as e:
        print(f"[archie] contract delta failed ({e})")
```

In step 7, replace:
```python
        confirmed = result.get("confirmed", [])
        confirmed, acked_over, stale_over = partition_for_verdict(root, confirmed)
        verdict = aggregate_verdict(spec, confirmed)
```
with:
```python
        confirmed = result.get("confirmed", [])
        confirmed, unauthorized = split_findings(confirmed)
        verdict = aggregate_verdict(spec, confirmed)
```
and change the pre-try defaults `acked_over, stale_over = [], []` to `unauthorized = []`.

In step 8, replace:
```python
        body = render_verdict(verdict, confirmed, spec, acked=acked_over, stale_acks=stale_over)
```
with:
```python
        body = render_verdict(verdict, confirmed, spec, retired=retired,
                              judged=judged, unauthorized=unauthorized)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_delivery_review.py tests/test_delivery_integration.py tests/test_delivery_story_intent.py -q`
Expected: pass. `test_delivery_story_intent.py` asserts story/intent rendering that no longer exists — delete the obsolete tests and name each deletion.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(review): PR gate composes the contract delta; unauthorized split from code review

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: One comment — marker param + drop the duplicate workflow step

**Files:**
- Modify: `archie/standalone/intent_review.py` (`_find_existing_comment_id` ~876, `post_or_update_comment` ~890, `safe_post_comment` ~904)
- Modify: `archie/standalone/delivery_review.py` (the `post_or_update_comment` call, ~line 457)
- Modify: `archie/assets/workflows/archie-intent-review.yml`
- Test: `tests/test_comment_marker.py`

**Why:** proven in the PR #17 run log —
```
[intent-review] posted new comment              <- intent_review posts
[intent-review] updated comment 4913709782      <- delivery_review PATCHes over it
```
Both scripts looked comments up by `intent_review.COMMENT_MARKER`, so delivery silently overwrote intent's comment every run — one leaked comment per run, and intent's judgment never visible. Now that `contract_delta` runs the same judgment inside the delivery comment, the separate step is redundant: **one job, one comment.** The `marker` parameter stays as insurance for anyone running `intent_review.py` standalone.

**Interfaces:** `post_or_update_comment(owner, repo, pr_number, body, token, marker=COMMENT_MARKER)`; `_find_existing_comment_id(owner, repo, pr_number, token, marker=COMMENT_MARKER)`; `safe_post_comment(owner, repo, pr_number, body, token, marker=COMMENT_MARKER)`. Defaults preserve every existing caller.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_comment_marker.py
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent_review as ir  # noqa: E402

COMMENTS = [
    {"id": 1, "body": "<!-- archie-intent-review -->\nintent stuff"},
    {"id": 2, "body": "<!-- archie-delivery-review -->\ndelivery stuff"},
]


def test_finds_comment_by_its_own_marker(monkeypatch):
    monkeypatch.setattr(ir, "_gh_request", lambda *a, **k: (COMMENTS, None))
    assert ir._find_existing_comment_id("o", "r", 1, "t") == 1                  # default
    assert ir._find_existing_comment_id("o", "r", 1, "t",
                                        marker="<!-- archie-delivery-review -->") == 2


def test_delivery_marker_never_matches_intent_comment(monkeypatch):
    monkeypatch.setattr(ir, "_gh_request", lambda *a, **k: ([COMMENTS[0]], None))
    assert ir._find_existing_comment_id(
        "o", "r", 1, "t", marker="<!-- archie-delivery-review -->") is None


def test_post_or_update_threads_the_marker(monkeypatch):
    seen = {}

    def fake_find(o, r, n, t, marker=ir.COMMENT_MARKER):
        seen["marker"] = marker
        return None

    monkeypatch.setattr(ir, "_find_existing_comment_id", fake_find)
    monkeypatch.setattr(ir, "_gh_request", lambda *a, **k: (None, None))
    ir.post_or_update_comment("o", "r", 1, "body", "t",
                              marker="<!-- archie-delivery-review -->")
    assert seen["marker"] == "<!-- archie-delivery-review -->"


def test_workflow_runs_one_review_step():
    wf = (Path(__file__).resolve().parent.parent / "archie" / "assets" /
          "workflows" / "archie-intent-review.yml").read_text()
    assert "intent_review.py" not in wf          # judgment now lives in the delivery comment
    assert wf.count("delivery_review.py") >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_comment_marker.py -q`
Expected: FAIL — `_find_existing_comment_id()` got an unexpected keyword argument `marker`; workflow still runs `intent_review.py`.

- [ ] **Step 3: Write the implementation**

In `intent_review.py`, add `marker=COMMENT_MARKER` as the last parameter of all three functions and use it in place of the module constant:

```python
def _find_existing_comment_id(owner, repo, pr_number, token, marker=COMMENT_MARKER):
    """Find THIS script's comment by ITS marker, following pagination. The marker is
    a parameter because two scripts once posted to the same PR with a shared marker —
    delivery PATCHed over intent's comment on every run."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments?per_page=100"
    while url:
        comments, link = _gh_request("GET", url, token)
        for c in comments if isinstance(comments, list) else []:
            if marker in (c.get("body") or ""):
                return c.get("id")
        url = _next_link(link)
```
`post_or_update_comment(..., marker=COMMENT_MARKER)` passes `marker` to `_find_existing_comment_id`. `safe_post_comment(..., marker=COMMENT_MARKER)` passes it to `post_or_update_comment`.

In `delivery_review.py`, use the Task-3 constant at the call site:
```python
                post_or_update_comment(owner, repo, number, body, token,
                                       marker=DELIVERY_MARKER)
```

In `archie/assets/workflows/archie-intent-review.yml`, **delete the entire `- name: Run Archie Intent Review` step** (its `if git cat-file … intent_review.py … fi` block). Keep the `Run Archie Delivery Review` step exactly as-is. Leave checkout, setup-python, `concurrency`, and `permissions` untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_comment_marker.py tests/test_intent_review.py tests/test_delivery_review.py -q`
Expected: all pass (existing intent-review tests call the 5-arg form; the default keeps them green).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/intent_review.py archie/standalone/delivery_review.py \
        archie/assets/workflows/archie-intent-review.yml tests/test_comment_marker.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "fix(review): one job, one comment — delivery was overwriting the intent review

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Stop synthesizing a task story in CI

**Files:**
- Modify: `archie/standalone/delivery_review.py` (the "Hands-off fallback" block in `run_pr_gate`, ~lines 325–337)
- Test: `tests/test_delivery_review.py` (append)

**Why:** CI calls `story_synthesize.imprint(...)` — two LLM passes — to reconstruct a task story when none is committed. After Tasks 3/4 nothing grades the story and nothing renders it. Paying a model in CI to generate an artifact no consumer reads is waste. A story committed on the branch is still read (free); an absent one stays absent. `assemble_pr_intent` already degrades to the PR-body spec.

**The local stop-hook imprint is NOT touched** — task-story capture stays silent and automatic on the developer's machine.

- [ ] **Step 1: Write the failing test** (append to `tests/test_delivery_review.py`)

```python
def test_pr_gate_never_synthesizes_a_story(tmp_path, monkeypatch):
    """CI must not pay a model to build an artifact no section renders."""
    import delivery_review as dr
    import story_synthesize
    monkeypatch.setattr(story_synthesize, "imprint",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("imprint must not run in CI")))
    import subprocess as _sp
    _sp.run(["git", "init", "-q", str(tmp_path)])
    (tmp_path / ".archie").mkdir()
    ev = tmp_path / "event.json"
    ev.write_text(json.dumps({"pull_request": {"number": 9, "title": "t", "body": "b",
                                               "base": {"ref": "main", "sha": ""},
                                               "head": {"ref": "x", "sha": ""}}}))
    dr.run_pr_gate(tmp_path, {"GITHUB_EVENT_PATH": str(ev)})   # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_review.py -q -k never_synthesizes`
Expected: FAIL — `AssertionError: imprint must not run in CI`.

- [ ] **Step 3: Write the implementation**

Delete the whole `# Hands-off fallback: if no current story exists but turns were captured, imprint now (blind).` block from `run_pr_gate` — the `try:` that imports `story_store, story_synthesize`, computes `_branch`/`_sid`/`_ts`, calls `story_synthesize.imprint(root, _branch, _sid, _ts)`, through its `except` printing `story auto-imprint skipped`. Nothing replaces it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_delivery_review.py tests/test_delivery_story_intent.py -q`
Expected: pass. Any test asserting CI auto-imprint is obsolete — delete it and name the deletion.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/test_delivery_review.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "perf(review): stop synthesizing a task story in CI — no consumer reads it

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Cost — drop intent graders, skip acked laws, one pass

**Files:**
- Modify: `archie/standalone/review_core.py` (`run_review`, thunk list ~lines 59–75)
- Modify: `archie/standalone/invariant_specialist.py` (`review_invariants`, def line 122)
- Test: `tests/test_review_core.py` (append), `tests/test_invariant_specialist.py` (append)

**Interfaces:**
- Consumes: `contract_delta.acked_rule_ids(root) -> set[str]` (Task 2).
- Produces: `review_invariants(root, diff_text, invariants, run=None, skip_ids=frozenset()) -> list[dict]`; `run_review(..., passes=1, ...)` no longer calls `review_edge_a` or `review_edge_c`.

Three cuts, largest first:
1. **Skip acked laws** in the invariant specialist. Each skipped law saves a Sonnet tracer *and* an Opus challenger, both running tool loops. (Belt-and-braces: after Task 1 the blueprint invariant is stamped `overridden`, and `selector` already drops dead-status invariants — so `skip_ids` catches the rule-id path and anything the stamp missed.)
2. **Drop edge-A and edge-C.** Both grade intent, which the comment no longer renders.
3. **`passes=1`.** N-pass union bought agreement-weighted confidence; the comment no longer renders confidence tiers.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_invariant_specialist.py
def test_review_invariants_skips_acked_laws():
    calls = []

    def rec(prompt, root, verifier, model="haiku", **kw):
        calls.append(model)
        return "{}"

    invs = [INV, {"id": "inv-other", "invariant": "x", "entity": "E", "category": "c"}]
    isp.review_invariants(".", DIFF, invs, run=rec, skip_ids={"inv-bill-003"})
    assert calls == [isp.TRACER_MODEL]     # only the unacked law ran; zero Opus


def test_review_invariants_all_acked_makes_no_calls():
    calls = []

    def rec(prompt, root, verifier, model="haiku", **kw):
        calls.append(model)
        return "{}"

    isp.review_invariants(".", DIFF, [INV], run=rec, skip_ids={"inv-bill-003"})
    assert calls == []
```

```python
# append to tests/test_review_core.py
def test_run_review_drops_intent_graders(tmp_path, monkeypatch):
    import review_core as rcmod
    called = []
    monkeypatch.setattr(rcmod, "review_edge_a",
                        lambda *a, **k: called.append("edge_a") or [], raising=False)
    monkeypatch.setattr(rcmod, "review_edge_c",
                        lambda *a, **k: called.append("edge_c") or [], raising=False)
    (tmp_path / "a.py").write_text("x = 1\n")
    rc.run_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"],
                  {"domain_invariants": []}, {},
                  {"acceptance_criteria": [{"id": "ac1", "text": "t"}]},
                  run=lambda *a, **k: "{}", workers=1)
    assert called == []


def test_run_review_defaults_to_one_pass():
    import inspect
    assert inspect.signature(rc.run_review).parameters["passes"].default == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_invariant_specialist.py tests/test_review_core.py -q -k "skips or acked or drops or one_pass"`
Expected: FAIL — `review_invariants()` has no `skip_ids`; edge graders still called; `passes` default is 2.

- [ ] **Step 3: Write the implementation**

In `invariant_specialist.py`:
```python
def review_invariants(root, diff_text, invariants, run=None, skip_ids=frozenset()) -> list[dict]:
```
Immediately inside `for inv in invariants or []:`:
```python
        if inv.get("id") in skip_ids:
            continue   # the user acknowledged this law — do not pay Opus to rediscover it
```
Docstring addition: `skip_ids — invariant ids the user already acknowledged breaking (contract_delta.acked_rule_ids). Skipped entirely: no tracer, no challenger.`

In `review_core.py`: change the default `passes=2` to `passes=1`; delete the `review_edge_a` thunk (first element of `thunks`), the whole `if has_intent:` block (its `review_edge_c` thunk and the `live_invariants` list), and the `has_intent` assignment. Then:

```python
    try:
        from contract_delta import acked_rule_ids
        _skip = acked_rule_ids(root)
    except Exception:
        _skip = frozenset()

    thunks = [
        lambda: behavioral_review_run(root, diff_text, import_graph, changed_files,
                                      run=run, intent=spec, evidence=evidence, passes=passes),
    ]
    for lens in us.LENSES:
        thunks.append(lambda lens=lens: us.review_one(root, diff_text, evidence, spec, lens, run=run))
    if ctx["invariants"]:
        thunks.append(lambda: review_invariants(root, diff_text, ctx["invariants"],
                                                run=run, skip_ids=_skip))
    if ctx["decisions"]:
        thunks.append(lambda: review_conformance(root, diff_text, [], ctx["decisions"],
                      run=run, intent=spec))
```
Remove `review_edge_a` / `review_edge_c` from the `reconcile` import line (keep `review_conformance`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_review_core.py tests/test_invariant_specialist.py tests/test_sync_review.py tests/test_contract_delta.py -q`
Expected: all pass. Existing `review_core` tests asserting edge-A/edge-C ran, or relying on `passes=2` agreement math, will fail — delete the obsolete ones and name each deletion.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/review_core.py archie/standalone/invariant_specialist.py tests/
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "perf(review): drop intent graders, skip acked laws, single pass

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Regenerate the demo branch, field-validate, sync, confirm

**Files:**
- Modify: `npm-package/bin/archie.mjs` (script array ~line 425)
- Copy: every canonical file Tasks 1–7 touched → `npm-package/assets/`

The local CI-replica rig is `/tmp/archie-validate/replay-ci.sh`: it extracts scripts from `origin/feature/archie_test`, runs against the PR-branch worktree, and forces the API path with `ANTHROPIC_API_KEY` from `/tmp/archie-validate/.env`. **The rig is the acceptance test — CI is only a confirmation.**

- [ ] **Step 1: Register the new script + sync the mirror**

Add `"contract_delta.py"` to the `for (const script of [...])` array in `npm-package/bin/archie.mjs` (do not remove or reorder existing entries). Then:
```bash
python3 scripts/verify_sync.py
```
`cp` each canonical file it names into `npm-package/assets/` (never hand-edit an asset). Expected: `contract_delta.py` (new), `overrides.py`, `sync.py`, `delivery_review.py`, `intent_review.py`, `review_core.py`, `invariant_specialist.py`, `renderer.py`, `workflow/sync/SKILL.md`, `workflow/deep-scan/steps/step-5d-product.md`, `step-6-rule-synthesis.md`, `workflows/archie-intent-review.yml`. Re-run until `SYNC CHECK PASSED`.

- [ ] **Step 2: Unit green**

```bash
python3 -m pytest tests/test_contract_delta.py tests/test_comment_marker.py \
  tests/test_delivery_review.py tests/test_review_core.py tests/test_overrides.py \
  tests/test_override_subcommands.py tests/test_invariant_specialist.py \
  tests/test_sync_review.py tests/test_intent_review.py tests/test_renderer_overrides.py \
  tests/test_workflow_override_text.py tests/test_asset_sync.py -q
python3 -m pytest tests/ -q --continue-on-collection-errors 2>&1 | tail -3
```
Expected: targeted subset passes. Broad suite: only the 3 known pre-existing failures (`churn_track`, `stop_nudges`, `codex_prefix`) + ~19 tomllib collection errors. Any other failure — check whether it failed at base (`git stash`) before touching it, and report honestly.

- [ ] **Step 3: Deploy to the base branch**

```bash
cd /Users/hamutarto/DEV/Repos/SubscriberAgent
git checkout feature/archie_test && git pull --ff-only origin feature/archie_test
for f in contract_delta.py overrides.py sync.py delivery_review.py intent_review.py \
         review_core.py invariant_specialist.py renderer.py; do
  cp /Users/hamutarto/DEV/Repos/Archie/npm-package/assets/$f .archie/$f
done
cp /Users/hamutarto/DEV/Repos/Archie/npm-package/assets/workflows/archie-intent-review.yml \
   .github/workflows/archie-intent-review.yml
git add .archie .github
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" \
  commit -q -m "chore(archie): contract delta leads; merging ratifies; one comment"
git push origin feature/archie_test
```

- [ ] **Step 4: Regenerate the demo branch so the diff carries the contract change**

The 8 existing override entries on `demo/archie-override-retest` were written by the OLD `override-ack`: they never removed the rules, so the branch has no rules diff. Re-run the NEW command for each, with its original reason, so `rules.json` + `blueprint.json` actually move. This is the real command doing real work — not a fabricated diff.

```bash
cd /Users/hamutarto/DEV/Repos/SubscriberAgent
git checkout demo/archie-override-retest
git merge --no-edit feature/archie_test          # pick up the new scripts
python3 - <<'PY'
import json, subprocess, sys
sys.path.insert(0, ".archie")
entries = json.load(open(".archie/overrides.json"))["overrides"]
json.dump({"version": 1, "overrides": []}, open(".archie/overrides.json", "w"), indent=2)
for e in entries:                                 # replay each authorization
    subprocess.run([sys.executable, ".archie/sync.py", "override-ack", ".",
                    e["rule_id"], "--reason", e["reason"]], check=True)
PY
git diff --stat .archie/rules.json .archie/blueprint.json   # MUST be non-empty now
git add .archie && git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" \
  commit -q -m "chore(archie): apply the 8 authorized retirements to the source of truth"
git push origin demo/archie-override-retest
```
If `git diff --stat` is empty, STOP — the rules were not removed and Task 1 is wrong.

- [ ] **Step 5: Field-validate on the rig (the acceptance test)**

```bash
source /tmp/archie-validate/.env
cd /tmp/archie-validate/pr17 && git fetch origin && git reset --hard origin/demo/archie-override-retest
bash /tmp/archie-validate/replay-ci.sh > /tmp/archie-validate/rescope.log 2>&1
```
Verify in `/tmp/archie-validate/rescope.log`:
- `### ⛔ Contract changes` appears **before** `### 🔍 Code review`
- 8 retirement rows, each with its law text, reason, and `Gabor Bakos`
- **zero** `unexplained source-of-truth change` — every rules change is explained by an override, so the judge is correctly skipped (proves `is_authorized`)
- `Built the intent?` and `criteria met` appear **zero** times
- Code-review findings grouped, `security` first
- No `[archie] review core failed` / `gate/verdict failed` lines
- Fewer model calls and lower wall-clock than the baseline (`/tmp/archie-validate/local-final.log`: 20 findings, ~12 min)

Then prove the judge fires on an **unauthorized** change: on a scratch commit, hand-edit one retained rule's `description` in `.archie/rules.json` (a weakening, e.g. soften "must never" to "should avoid"), re-run the rig, and confirm the comment shows `⚠️ Silent weakening` with a `collides with` line. Reset the scratch commit afterwards.

If any check fails, fix it and re-run the rig. **Do not push to CI until the rig is green.**

- [ ] **Step 6: Clean the stale comments, commit, one CI confirmation**

PR #17 carries 4 leaked delivery-review comments from the marker bug (fake-green `13/13`, `ENGINE FAILED`, …). Delete all but the newest so the demo shows one comment:
```bash
cd /Users/hamutarto/DEV/Repos/SubscriberAgent
gh api repos/BitRaptors/SubscriberAgent/issues/17/comments --jq \
  '.[] | select(.body | test("archie-(intent|delivery)-review")) | .id' | head -n -1 | \
  while read id; do gh api -X DELETE "repos/BitRaptors/SubscriberAgent/issues/comments/$id"; done
```
Then:
```bash
cd /Users/hamutarto/DEV/Repos/Archie
git add npm-package/
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "chore(review): package sync + register contract_delta.py

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
cd /Users/hamutarto/DEV/Repos/SubscriberAgent && gh run rerun \
  "$(gh run list --branch demo/archie-override-retest --workflow 'Archie Intent Review' --limit 1 --json databaseId --jq '.[0].databaseId')"
```
Confirm PR #17 shows **one** Archie comment, leading with the contract table, and the run log is error-free.

---

## Execution notes

Dependency order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Task 2 needs Task 1's `law` snapshot; Task 3's signature change breaks Task 4's call site until both land; Task 7 needs Task 2's `acked_rule_ids`; Task 8 needs the new `override-ack` to regenerate the demo branch.

**Reviewer guidance:** npm-mirror drift is deferred to Task 8 — do not flag it in Tasks 1–7. Tasks 1, 3, 4, 6, 7 delete behavior on purpose; a test asserting the deleted behavior must be **deleted**, not weakened, and every deletion must be named in the implementer's report. The exit-0 contract is binding: no code path added here may raise, and neither judge findings nor unauthorized violations may block the check. Never re-implement `intent_review`'s differ — compose it.

**The load-bearing invariant of this design:** `override-ack` is the ONLY writer of an authorized contract change, and it writes to the source of truth. If a future change reintroduces a side-channel carrier, the rules diff goes blind again and the review silently stops seeing what merging accepts.
