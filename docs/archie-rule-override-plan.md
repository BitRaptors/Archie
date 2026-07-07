# Rule Override & Ratification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Archie's enforcement gates from hard walls into stop-and-confirm doors: a human-authorized rule violation is recorded once (`.archie/overrides.json`), demotes that rule to WARN at edit- and commit-time, is surfaced by the PR delivery review as an "Acknowledged override" (not a break), is applied to the contract on merge (ratification), and is handed to deep scan as a tombstone so the blueprint re-derives from code.

**Architecture:** One new standalone module (`overrides.py`) owns the record: load/save/ack/active/pending/archive/matching/partition. Consumers: `pre-validate.sh` (inline JSON read — keeps the bash hook import-free), `align_check.py`, `delivery_review.py`, `sync_review.py`, `sync.py` (two new subcommands: `override-ack`, `override-ratify`), `renderer.py` (doc markers), and two workflow skill texts (sync fold-in step, deep-scan tombstones). Design: `docs/archie-rule-override-design.md`.

**Tech Stack:** Python 3.9 stdlib only, bash, pytest.

## Global Constraints

- `python3` only (3.9.6 target); zero third-party dependencies.
- Sibling imports are bare (`import overrides`), NEVER `from archie.standalone.X import Y`; guard with `sys.path.insert(0, str(Path(__file__).parent))` when the file doesn't have it already.
- Canonical → mirror: edit `archie/standalone/*.py`, `archie/assets/hook_scripts/*.sh`, `archie/assets/workflow/**` FIRST; npm mirroring (`npm-package/assets/...`) is deferred wholesale to Task 10 — **do not flag or fix `verify_sync.py` failures in Tasks 1–9** (expected red until Task 10, established pattern).
- Exit-0 degradation contract: reading a missing/corrupt `overrides.json` must never crash a gate, review, or renderer — degrade to "no overrides".
- The ack is written ONLY on explicit user confirmation; every consumer docstring/message must say so.
- Timestamp format everywhere: `%Y-%m-%dT%H:%M:%SZ` (UTC).
- Commits: `git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit ...` with trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Run tests with `python3 -m pytest <file> -q`.

## File Structure

| File | Role |
|---|---|
| `archie/standalone/overrides.py` (new) | The record: schema, ack, active, pending_ratification, archive, finding_matches, partition |
| `archie/standalone/sync.py` (modify) | `override-ack` + `override-ratify` subcommands |
| `archie/assets/hook_scripts/pre-validate.sh` (modify) | Edit-gate demotion + footer + self-exemption |
| `archie/standalone/align_check.py` (modify) | Commit-gate demotion + footer |
| `archie/standalone/delivery_review.py` (modify) | Verdict join: acked section, stale flag, breaks exclusion |
| `archie/standalone/sync_review.py` + `sync.py cmd_review` (modify) | Same partition locally; status-line count |
| `archie/standalone/renderer.py` (modify) | Overridden/staged markers in product-laws.md |
| `archie/assets/workflow/sync/SKILL.md` (modify) | Step 2b: ratify + fold acks into staged claims |
| `archie/assets/workflow/deep-scan/steps/step-5d-product.md`, `step-6-rule-synthesis.md` (modify) | Tombstone prompts |
| `npm-package/**` + `npm-package/bin/archie.mjs` (Task 10 only) | Mirror + register `overrides.py` |

---

### Task 1: `overrides.py` — the human-ruling record

**Files:**
- Create: `archie/standalone/overrides.py`
- Test: `tests/test_overrides.py`

**Interfaces:**
- Consumes: nothing (stdlib + git CLI).
- Produces (later tasks call these exactly):
  - `load(root) -> dict` — `{"version": 1, "overrides": [entry...]}`; corrupt/missing → empty shape.
  - `ack(root, rule_id: str, reason: str, now: str | None = None) -> dict` — append entry, idempotent per (rule_id, branch).
  - `active(root) -> dict` — `{rule_id: entry}` for every `status == "acked"` entry.
  - `pending_ratification(root) -> list` — acked entries whose `branch != current_branch(root)`.
  - `archive(root, entry: dict, status: str = "ratified", now: str | None = None) -> None` — remove from active file, append to `overrides_history.jsonl`.
  - `finding_matches(finding: dict, rule_id: str) -> bool`
  - `partition(findings: list, active: dict) -> tuple` — `(unacked: list, acked: list[(entry, [findings])], stale: list[entry])`.
  - `current_branch(root) -> str`, `git_user(root) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_overrides.py
import json
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import overrides as ov  # noqa: E402


def _git_repo(tmp_path, branch="feature/x"):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    (tmp_path / ".archie").mkdir()


def test_ack_writes_entry_with_git_identity_and_is_idempotent(tmp_path):
    _git_repo(tmp_path)
    e1 = ov.ack(tmp_path, "inv-003", "store cost — perf decision")
    assert e1["rule_id"] == "inv-003" and e1["status"] == "acked"
    assert e1["branch"] == "feature/x"
    assert e1["authorized_by"] == "Test User <t@example.com>"
    assert e1["created_at"].endswith("Z")
    e2 = ov.ack(tmp_path, "inv-003", "different words")   # same rule+branch
    data = ov.load(tmp_path)
    assert len(data["overrides"]) == 1                     # idempotent
    assert e2["reason"] == e1["reason"]                    # first ruling kept


def test_load_corrupt_file_degrades_to_empty(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "overrides.json").write_text("{not json")
    assert ov.load(tmp_path) == {"version": 1, "overrides": []}


def test_active_maps_rule_ids(tmp_path):
    _git_repo(tmp_path)
    ov.ack(tmp_path, "inv-003", "r1")
    ov.ack(tmp_path, "trd-002", "r2")
    act = ov.active(tmp_path)
    assert set(act) == {"inv-003", "trd-002"}


def test_pending_ratification_only_foreign_branch_entries(tmp_path):
    _git_repo(tmp_path, branch="develop")
    ov.ack(tmp_path, "inv-here", "on this branch")         # branch == develop
    data = ov.load(tmp_path)
    data["overrides"].append({"rule_id": "inv-003", "reason": "merged in",
                              "authorized_by": "X", "branch": "demo/other",
                              "created_at": "2026-07-07T00:00:00Z", "status": "acked"})
    ov.save(tmp_path, data)
    pend = ov.pending_ratification(tmp_path)
    assert [e["rule_id"] for e in pend] == ["inv-003"]


def test_archive_moves_entry_to_history(tmp_path):
    _git_repo(tmp_path)
    e = ov.ack(tmp_path, "inv-003", "r")
    ov.archive(tmp_path, e, status="ratified")
    assert ov.active(tmp_path) == {}
    hist = (tmp_path / ".archie" / "overrides_history.jsonl").read_text().strip().splitlines()
    rec = json.loads(hist[0])
    assert rec["rule_id"] == "inv-003" and rec["status"] == "ratified"
    assert rec["archived_at"].endswith("Z")


def test_finding_matches_by_id_statement_and_assumptions():
    assert ov.finding_matches({"id": "f_inv_inv-003"}, "inv-003")
    assert ov.finding_matches({"problem_statement": "violates inv-003: cost stored"}, "inv-003")
    assert ov.finding_matches({"assumptions": ["invariant inv-003", "trace: x"]}, "inv-003")
    assert not ov.finding_matches({"id": "f_x", "problem_statement": "null deref"}, "inv-003")
    assert not ov.finding_matches({"problem_statement": "anything"}, "")


def test_partition_splits_unacked_acked_stale(tmp_path):
    _git_repo(tmp_path)
    e3 = ov.ack(tmp_path, "inv-003", "r")
    e9 = ov.ack(tmp_path, "inv-999", "never observed")
    act = ov.active(tmp_path)
    findings = [
        {"id": "f_inv_inv-003", "kind": "conformance_break"},
        {"id": "f_b1", "kind": "behavioral_break", "problem_statement": "null deref"},
    ]
    unacked, acked, stale = ov.partition(findings, act)
    assert [f["id"] for f in unacked] == ["f_b1"]
    assert len(acked) == 1 and acked[0][0]["rule_id"] == "inv-003"
    assert [f["id"] for f in acked[0][1]] == ["f_inv_inv-003"]
    assert [e["rule_id"] for e in stale] == ["inv-999"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_overrides.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'overrides'`.

- [ ] **Step 3: Write the implementation**

```python
# archie/standalone/overrides.py
"""Rule override records — what the HUMAN ruled.

Complements .archie/findings.json (what the machine observed). A finding says
"this is broken"; an override entry says "the user saw it and authorized it".
Findings are machine-managed (verifier + hysteresis may rewrite them); a ruling
is durable — nothing machine-managed may erase it.

Lifecycle (design: docs/archie-rule-override-design.md):
  acked     — written by the agent at the moment the user explicitly confirms
              crossing a rule. Gates demote that rule from BLOCK to WARN.
  ratified  — the entry arrived on another branch via merge; the first sync
              applies the amendment to the contract and archives the entry.
  archived  — moved to overrides_history.jsonl (append-only audit trail).

Branch scoping is free: the file is committed, so an entry exists only where
its commit is reachable. An entry whose branch != the current branch can only
have arrived via merge — which IS ratification.

Import convention: bare-name sibling imports via sys.path (Python 3.9).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

FILE = "overrides.json"
HISTORY = "overrides_history.jsonl"


def _path(root) -> Path:
    return Path(root) / ".archie" / FILE


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(root, *args) -> str:
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def current_branch(root) -> str:
    return _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "HEAD"


def git_user(root) -> str:
    name = _git(root, "config", "user.name")
    email = _git(root, "config", "user.email")
    if name or email:
        return f"{name} <{email}>".strip()
    return "unknown"


def load(root) -> dict:
    try:
        d = json.loads(_path(root).read_text())
        if isinstance(d, dict) and isinstance(d.get("overrides"), list):
            return d
    except Exception:
        pass
    return {"version": 1, "overrides": []}


def save(root, data) -> None:
    p = _path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(p)


def ack(root, rule_id: str, reason: str, now: str | None = None) -> dict:
    """Record a human-authorized override. ONLY call after the user explicitly
    confirmed crossing the rule in conversation. Idempotent per (rule_id, branch):
    the first ruling is kept."""
    data = load(root)
    branch = current_branch(root)
    for e in data["overrides"]:
        if (e.get("rule_id") == rule_id and e.get("branch") == branch
                and e.get("status") == "acked"):
            return e
    entry = {
        "rule_id": rule_id,
        "reason": reason,
        "authorized_by": git_user(root),
        "branch": branch,
        "created_at": now or _now(),
        "status": "acked",
    }
    data["overrides"].append(entry)
    save(root, data)
    return entry


def active(root) -> dict:
    """rule_id -> entry for every acked override. Any committed acked entry
    suppresses its rule: on the authoring branch it is the confirmed override;
    anywhere else it can only have arrived via merge (= ratified, pending
    bookkeeping by override-ratify)."""
    return {e["rule_id"]: e for e in load(root)["overrides"]
            if e.get("status") == "acked" and e.get("rule_id")}


def pending_ratification(root) -> list:
    """Acked entries that merged in from another branch — merge IS ratification;
    these await the contract application + archive step."""
    b = current_branch(root)
    return [e for e in load(root)["overrides"]
            if e.get("status") == "acked" and e.get("branch") != b]


def archive(root, entry: dict, status: str = "ratified", now: str | None = None) -> None:
    data = load(root)
    data["overrides"] = [e for e in data["overrides"]
                         if not (e.get("rule_id") == entry.get("rule_id")
                                 and e.get("branch") == entry.get("branch"))]
    save(root, data)
    rec = dict(entry)
    rec["status"] = status
    rec["archived_at"] = now or _now()
    h = Path(root) / ".archie" / HISTORY
    h.parent.mkdir(parents=True, exist_ok=True)
    with h.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def finding_matches(finding: dict, rule_id: str) -> bool:
    """Join a review finding to a rule id: invariant findings carry the id in
    their finding id (f_inv_<rule>), problem statement, or assumptions."""
    if not rule_id:
        return False
    if str(finding.get("id", "")).startswith(f"f_inv_{rule_id}"):
        return True
    if rule_id in str(finding.get("problem_statement", "")):
        return True
    return any(rule_id in str(a) for a in (finding.get("assumptions") or []))


def partition(findings: list, active_map: dict) -> tuple:
    """Split findings by ruling: (unacked, acked, stale).

    unacked — findings with no matching override (count as breaks).
    acked   — [(entry, [matching findings])] (surfaced, not counted).
    stale   — override entries with NO matching finding this run (the violation
              is no longer observed — flag for removal before merge)."""
    unacked = []
    by_rule: dict = {}
    for f in findings:
        rid = next((r for r in active_map if finding_matches(f, r)), None)
        if rid is None:
            unacked.append(f)
        else:
            by_rule.setdefault(rid, []).append(f)
    acked = [(active_map[r], fs) for r, fs in by_rule.items()]
    stale = [e for r, e in active_map.items() if r not in by_rule]
    return unacked, acked, stale
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_overrides.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/overrides.py tests/test_overrides.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): overrides.py — the human-ruling record (ack/active/ratify/partition)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `sync.py override-ack` subcommand

**Files:**
- Modify: `archie/standalone/sync.py` (dispatch tail is at ~line 1086–1140; add the command function near `cmd_review` at ~line 834 — read the real file, anchors drift)
- Test: `tests/test_override_subcommands.py`

**Interfaces:**
- Consumes: `overrides.ack(root, rule_id, reason)` (Task 1).
- Produces: CLI `python3 sync.py override-ack <root> <rule_id> --reason "..."` → exit 0, prints one-line JSON `{"acked": ..., "branch": ..., "by": ...}`. This exact invocation string is what the gate footers print (Tasks 3–4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_override_subcommands.py
import json
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import overrides as ov  # noqa: E402

SYNC = _STANDALONE / "sync.py"


def _git_repo(tmp_path, branch="feature/x"):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    (tmp_path / ".archie").mkdir()


def test_override_ack_cli_records_entry(tmp_path):
    _git_repo(tmp_path)
    r = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                        "inv-003", "--reason", "store cost — user authorized"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["acked"] == "inv-003"
    act = ov.active(tmp_path)
    assert act["inv-003"]["reason"] == "store cost — user authorized"


def test_override_ack_requires_rule_and_reason(tmp_path):
    _git_repo(tmp_path)
    r = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_override_subcommands.py -q`
Expected: FAIL — unknown subcommand (sync.py prints usage / non-zero for `override-ack`).

- [ ] **Step 3: Write minimal implementation**

Add near `cmd_review` (module scope, follow the file's lazy-import style):

```python
def cmd_override_ack(root: Path, rule_id: str, reason: str) -> int:
    """Record a human-authorized rule override. Agent-run ONLY — and only after
    the user explicitly confirmed crossing the rule in conversation. Gates then
    demote this rule from BLOCK to WARN on this branch; the PR delivery review
    surfaces it as an acknowledged override; merge ratifies it."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    if not rule_id or not reason:
        print('usage: sync.py override-ack <root> <rule_id> --reason "..."', file=sys.stderr)
        return 1
    import overrides as _ov
    e = _ov.ack(root, rule_id, reason)
    print(json.dumps({"acked": e["rule_id"], "branch": e["branch"], "by": e["authorized_by"]}))
    return 0
```

In the `main()` dispatch tail (the `if cmd == ...` chain, e.g. right before `if cmd == "review":`), add:

```python
    if cmd == "override-ack":
        rid = rest[0] if rest and not rest[0].startswith("--") else ""
        return cmd_override_ack(root, rid, _opt(rest, "--reason") or "")
```

(`_opt` already exists — it is used for `--change`. Verify its exact name in the real file before use.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_override_subcommands.py tests/test_overrides.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/sync.py tests/test_override_subcommands.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): sync.py override-ack — record a user-authorized violation

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `pre-validate.sh` — demotion, footer, self-exemption

**Files:**
- Modify: `archie/assets/hook_scripts/pre-validate.sh` (canonical — do NOT touch the npm mirror)
- Test: `tests/test_pre_validate_overrides.py`

**Interfaces:**
- Consumes: `.archie/overrides.json` shape from Task 1 (read inline with `json` — the bash hook stays import-free) and the Task 2 CLI string for the footer.
- Produces: fired blocking rule with an acked override → printed as `WARN (overridden ...)`, exit 0. Genuine block → footer naming `override-ack`. Writes targeting `.archie/overrides.json` are never rule-matched.

The hook's embedded Python (between `python3 << 'PYEOF'` and `PYEOF`) currently: parses the tool JSON, computes `rel_path`, loads rules, classifies fired rules into `errors`/`warns`/`infos`, renders, and `sys.exit(2)` if `errors`. Read the real script; the three edits below anchor on code text.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pre_validate_overrides.py
import json
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / "pre-validate.sh"

RULES = {"rules": [{
    "id": "inv-003",
    "severity_class": "decision_violation",
    "description": "Run cost must never be stored",
    "why": "a stored cost can drift from the billable_steps ledger",
    "check": "forbidden_content",
    "applies_to": "",
    "forbidden_patterns": ["stored_cost"],
}]}


def _project(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "feature/x", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e.com"], check=True)
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps(RULES))


def _run_hook(tmp_path, file_path, content):
    envelope = json.dumps({"tool_name": "Write",
                           "tool_input": {"file_path": str(file_path), "content": content}})
    return subprocess.run(["bash", str(HOOK)], input=envelope, capture_output=True,
                          text=True, cwd=str(tmp_path))


def test_block_footer_names_the_sanctioned_door(tmp_path):
    _project(tmp_path)
    r = _run_hook(tmp_path, tmp_path / "a.py", "stored_cost = 1")
    assert r.returncode == 2
    assert "BLOCKED" in r.stdout and "inv-003" in r.stdout
    assert "override-ack" in r.stdout            # the door is advertised
    assert "user" in r.stdout.lower()            # ...and gated on user authorization


def test_acked_override_demotes_block_to_warn(tmp_path):
    _project(tmp_path)
    (tmp_path / ".archie" / "overrides.json").write_text(json.dumps({
        "version": 1, "overrides": [{
            "rule_id": "inv-003", "reason": "store cost — authorized",
            "authorized_by": "Gabor <g@e.com>", "branch": "feature/x",
            "created_at": "2026-07-07T00:00:00Z", "status": "acked"}]}))
    r = _run_hook(tmp_path, tmp_path / "a.py", "stored_cost = 1")
    assert r.returncode == 0                     # no longer blocks
    assert "overridden" in r.stdout.lower()      # still visible
    assert "Gabor" in r.stdout


def test_write_to_overrides_file_is_exempt(tmp_path):
    _project(tmp_path)
    # content would trip the rule, but the target is the overrides file itself
    r = _run_hook(tmp_path, tmp_path / ".archie" / "overrides.json",
                  '{"overrides": [{"reason": "stored_cost"}]}')
    assert r.returncode == 0
    assert "BLOCKED" not in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pre_validate_overrides.py -q`
Expected: `test_block_footer...` FAILS (no `override-ack` in output), `test_acked_override...` FAILS (returncode 2), `test_write_to_overrides...` FAILS (blocked).

- [ ] **Step 3: Edit the embedded Python (three splices)**

**(a) Self-exemption** — right after `fp = ti.get("file_path", "") or ti.get("path", "")` / the `if not fp: sys.exit(0)` block:

```python
# The overrides ledger is written by the sanctioned ack flow; matching rules
# against its content would recursively block the door itself.
if fp.replace("\\", "/").endswith(".archie/overrides.json"):
    sys.exit(0)
```

**(b) Load acked overrides** — right after the `rules = []` loading loop:

```python
overrides_active = {}
try:
    with open(os.path.join(project_root, ".archie", "overrides.json")) as _f:
        for _e in (json.load(_f).get("overrides") or []):
            if _e.get("status") == "acked" and _e.get("rule_id"):
                overrides_active[_e["rule_id"]] = _e
except Exception:
    pass
```

**(c) Demote + footer** — the classification loop currently ends with:

```python
    sc = r.get("severity_class", "")
    if sc in SEVERITY_BLOCKING or (not sc and r.get("severity") == "error"):
        errors.append((r, conf))
    elif sc in SEVERITY_INFO:
        infos.append((r, conf))
    else:
        warns.append((r, conf))
```

Replace with (adds an `overridden` bucket; `overridden = []` must be initialized next to `errors = []`):

```python
    sc = r.get("severity_class", "")
    if r.get("id", "") in overrides_active:
        overridden.append((r, conf, overrides_active[r["id"]]))
    elif sc in SEVERITY_BLOCKING or (not sc and r.get("severity") == "error"):
        errors.append((r, conf))
    elif sc in SEVERITY_INFO:
        infos.append((r, conf))
    else:
        warns.append((r, conf))
```

And the render tail currently ends with:

```python
for r, c in errors:
    render_fired(r, c, "BLOCKED")
if errors:
    sys.exit(2)
```

Replace with:

```python
for r, c, e in overridden[:5]:
    render_fired(r, c, f"WARN (overridden by {e.get('authorized_by', '?')}: {e.get('reason', '')[:80]})")
for r, c in errors:
    render_fired(r, c, "BLOCKED")
if errors:
    ids = ", ".join(r.get("id", "?") for r, _ in errors)
    print("")
    print("[Archie] These are hard architectural rules. Do NOT reword the change to dodge")
    print("them and do NOT modify enforcement hooks. If the USER explicitly authorizes")
    print(f"crossing a rule in this conversation, record it and retry (one per rule id: {ids}):")
    print("  python3 .archie/sync.py override-ack . <rule-id> --reason \"<the user's stated reason>\"")
    sys.exit(2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pre_validate_overrides.py tests/test_hook_enforcement.py -q`
Expected: all pass (`test_hook_enforcement.py` guards no regression in existing hook behavior).

- [ ] **Step 5: Commit**

```bash
git add archie/assets/hook_scripts/pre-validate.sh tests/test_pre_validate_overrides.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): edit gate demotes acked rules to WARN + advertises the door

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `align_check.py` — commit-gate demotion + footer

**Files:**
- Modify: `archie/standalone/align_check.py` (`_render_diagnostics` at ~line 259; `cmd_plan` ~313; `cmd_commit` ~331 — anchors drift, read first)
- Test: `tests/test_align_check_overrides.py`

**Interfaces:**
- Consumes: `.archie/overrides.json` (loaded via the module's existing `_load_json`).
- Produces: `_render_diagnostics(verdict, overrides=None) -> bool` — acked blocking rules demote to a printed WARN and never make the return True; genuine block prints the `override-ack` footer.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_align_check_overrides.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_align_check_overrides.py -q`
Expected: FAIL — `_render_diagnostics() got an unexpected keyword argument 'overrides'` / no `_load_overrides`.

- [ ] **Step 3: Write minimal implementation**

Add after `_load_architectural_rules`:

```python
def _load_overrides(archie_dir: Path) -> dict[str, Any]:
    """rule_id -> acked override entry (the human-authorized violations).
    See overrides.py / docs/archie-rule-override-design.md."""
    data = _load_json(archie_dir / "overrides.json")
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for e in data.get("overrides") or []:
            if isinstance(e, dict) and e.get("status") == "acked" and e.get("rule_id"):
                out[e["rule_id"]] = e
    return out
```

Change `_render_diagnostics(verdict)` to `_render_diagnostics(verdict, overrides=None)`; inside the loop, right after `rid`/`sc`/`evidence`/`fix` are read and before the existing label branching, insert:

```python
        if sc in SEVERITY_BLOCKING and overrides and rid in overrides:
            e = overrides[rid]
            print(f"[Archie WARN] {rid} [{sc}] — OVERRIDDEN by "
                  f"{e.get('authorized_by', '?')}: {e.get('reason', '')}")
            if evidence:
                print(f"  Evidence: {evidence}")
            continue
```

At the end of `_render_diagnostics`, before `return blocking`:

```python
    if blocking:
        print("")
        print("[Archie] Hard rule fired. Do NOT reword the diff or touch enforcement hooks.")
        print("If the USER explicitly authorizes crossing it, record it and retry:")
        print('  python3 .archie/sync.py override-ack . <rule-id> --reason "<the user\'s stated reason>"')
```

In `cmd_plan` and `cmd_commit`, replace `blocking = _render_diagnostics(verdict)` with:

```python
    blocking = _render_diagnostics(verdict, overrides=_load_overrides(archie_dir))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_align_check_overrides.py -q` (plus any existing `align_check` tests: `python3 -m pytest tests/ -q -k align`)
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/align_check.py tests/test_align_check_overrides.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): commit gate demotes acked rules + advertises the door

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Delivery review — acknowledged-overrides section

**Files:**
- Modify: `archie/standalone/delivery_review.py` (`render_verdict` ~line 72; `run_pr_gate` step 7 gate/verdict block ~line 365 — read first)
- Test: `tests/test_delivery_review.py` (append)

**Interfaces:**
- Consumes: `overrides.active(root)` + `overrides.partition(findings, active)` (Task 1).
- Produces: `render_verdict(verdict, confirmed, spec=None, acked=None, stale_acks=None)`; acked findings excluded from `aggregate_verdict` counting; PR comment gains "⚠️ Acknowledged overrides" + "Stale overrides" sections.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_delivery_review.py`, follow its existing import pattern)

```python
def test_render_verdict_acknowledged_overrides_section():
    import delivery_review as dr
    verdict = {"intent_completeness": "1/1", "breaks": 0, "conflicts": 0}
    entry = {"rule_id": "inv-003", "reason": "store cost — authorized",
             "authorized_by": "Gabor <g@e.com>", "created_at": "2026-07-07T00:00:00Z"}
    finding = {"kind": "conformance_break", "id": "f_inv_inv-003",
               "problem_statement": "violates inv-003: cost stored",
               "anchor": {"file": "a.py", "line": 3}, "source": "invariant_specialist:ctc"}
    body = dr.render_verdict(verdict, [], {}, acked=[(entry, [finding])],
                             stale_acks=[{"rule_id": "inv-999", "reason": "gone"}])
    assert "Acknowledged overrides" in body
    assert "inv-003" in body and "Gabor" in body
    assert "not counted as breaks" in body
    assert "Stale overrides" in body and "inv-999" in body


def test_run_pr_gate_partitions_acked_findings(tmp_path, monkeypatch):
    # An acked finding must not count as a break; an unacked one must.
    import delivery_review as dr
    import overrides as ov
    entry = {"rule_id": "inv-003", "reason": "r", "authorized_by": "G",
             "branch": "b", "created_at": "t", "status": "acked"}
    monkeypatch.setattr(ov, "active", lambda root: {"inv-003": entry})
    confirmed = [
        {"kind": "conformance_break", "id": "f_inv_inv-003", "confidence": 0.9,
         "problem_statement": "violates inv-003", "anchor": {"file": "a.py", "line": 1}},
        {"kind": "behavioral_break", "id": "f_b", "confidence": 0.9,
         "problem_statement": "null deref", "anchor": {"file": "b.py", "line": 2}},
    ]
    unacked, acked, stale = dr.partition_for_verdict(tmp_path, confirmed)
    assert [f["id"] for f in unacked] == ["f_b"]
    assert acked[0][0]["rule_id"] == "inv-003"
    assert stale == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_review.py -q -k override`
Expected: FAIL — unexpected kwarg `acked` / no `partition_for_verdict`.

- [ ] **Step 3: Write minimal implementation**

Add to `delivery_review.py` (module scope, after `render_verdict`):

```python
def partition_for_verdict(root, confirmed):
    """Split confirmed findings by human ruling (overrides.partition). Degrades
    to (confirmed, [], []) when the overrides module/file is absent — the exit-0
    contract must survive a missing ledger."""
    try:
        import overrides as _ov
        act = _ov.active(root)
        if not act:
            return confirmed, [], []
        return _ov.partition(confirmed, act)
    except Exception:
        return confirmed, [], []
```

In `render_verdict`, change the signature to:

```python
def render_verdict(verdict: dict, confirmed: list[dict], spec=None, acked=None, stale_acks=None) -> str:
```

and insert right BEFORE the closing footer line (`lines.append("_Story wrong? ...")`):

```python
    if acked:
        lines.append("")
        lines.append(f"**⚠️ Acknowledged overrides** ({len(acked)} — user-authorized, "
                     "not counted as breaks; merging ratifies the amendment):")
        for entry, fs in acked:
            lines.append(f"- `{_sanitize(entry.get('rule_id', '?'))}` — "
                         f"{_sanitize(entry.get('reason', ''))} · authorized by "
                         f"**{_sanitize(entry.get('authorized_by', '?'))}** on "
                         f"{_sanitize(str(entry.get('created_at', ''))[:10])}")
            for f in fs:
                lines.append("  " + _render_finding(f))
    if stale_acks:
        lines.append("")
        lines.append("**Stale overrides** (no matching violation observed this run — if the "
                     "change was reverted, remove the entry from `.archie/overrides.json`):")
        for e in stale_acks:
            lines.append(f"- `{_sanitize(e.get('rule_id', '?'))}` — {_sanitize(e.get('reason', ''))}")
```

(Note: `_render_finding` is a closure inside `render_verdict` in the current code — the insertion is inside the same function, so it is in scope.)

In `run_pr_gate`, the step-7 block currently computes `confirmed` then `verdict = aggregate_verdict(spec, confirmed)`. Splice the partition between them, and thread the render call:

```python
        confirmed = result.get("confirmed", [])
        confirmed, acked_over, stale_over = partition_for_verdict(root, confirmed)
        verdict = aggregate_verdict(spec, confirmed)
```

(`acked_over, stale_over = [], []` must also be initialized next to the existing `confirmed = []` default before the try, so the render call below never sees unbound names.) Then in step 8 change:

```python
        body = render_verdict(verdict, confirmed, spec)
```

to:

```python
        body = render_verdict(verdict, confirmed, spec, acked=acked_over, stale_acks=stale_over)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_delivery_review.py tests/test_delivery_story_intent.py tests/test_delivery_integration.py -q`
Expected: all pass (the two new tests + no regressions).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/test_delivery_review.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): PR verdict surfaces acknowledged overrides, excludes them from breaks

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Local sync review — same ruling, same treatment

**Files:**
- Modify: `archie/standalone/sync_review.py` (the gate/return block at the end of `run_sync_review`, ~lines 116–132) and `archie/standalone/sync.py` `cmd_review` (~line 834, the verdict print)
- Test: `tests/test_sync_review.py` (append)

**Interfaces:**
- Consumes: `delivery_review.partition_for_verdict` — do NOT reimplement; import it (`from delivery_review import partition_for_verdict`) so local and CI share one join.
- Produces: `run_sync_review(...)` return dict gains `"acked": [(entry, [findings])]` and `"stale_acks": [entry]`; verdict counts exclude acked findings; `cmd_review` prints `· N acknowledged override(s)` when N > 0.

- [ ] **Step 1: Write the failing test** (append to `tests/test_sync_review.py`)

```python
def test_sync_review_excludes_acked_findings_from_verdict(tmp_path, monkeypatch):
    (tmp_path / ".archie").mkdir()
    (tmp_path / "a.py").write_text("x = 1\n")
    import overrides as ov
    entry = {"rule_id": "inv-003", "reason": "r", "authorized_by": "G",
             "branch": "b", "created_at": "t", "status": "acked"}
    monkeypatch.setattr(ov, "active", lambda root: {"inv-003": entry})

    import review_core

    def fake_core(*a, **k):
        return [{"kind": "conformance_break", "id": "f_inv_inv-003", "edge": "B",
                 "problem_statement": "violates inv-003: cost stored",
                 "anchor": {"file": "a.py", "line": 1, "changed": True},
                 "assumptions": [], "evidence": ["e"], "falsification": "f",
                 "confidence": 0.9, "source": "invariant_specialist:ctc"}]
    monkeypatch.setattr(review_core, "run_review", fake_core)

    out = sr.run_sync_review(str(tmp_path), "main", {"domain_invariants": []}, {},
                             "diff --git a/a.py b/a.py", ["a.py"], {}, {},
                             run=lambda *a, **k: "{}")
    assert out["skipped"] is False
    assert out["verdict"]["breaks"] == 0            # acked → not a break
    assert out["acked"][0][0]["rule_id"] == "inv-003"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sync_review.py -q`
Expected: FAIL — `KeyError: 'acked'` (or breaks == 1).

- [ ] **Step 3: Write minimal implementation**

In `run_sync_review`, the tail currently reads:

```python
    result = gate(raw, store, changed_lines=changed_lines, floors=floors)

    return {
        "skipped": False,
        "confirmed": result["confirmed"],
        "verdict": aggregate_verdict(spec, result["confirmed"]),
    }
```

Replace with:

```python
    result = gate(raw, store, changed_lines=changed_lines, floors=floors)

    # Human rulings: acked overrides are surfaced, not counted — the SAME
    # partition the CI delivery review uses (one join for both surfaces).
    from delivery_review import partition_for_verdict
    confirmed, acked, stale_acks = partition_for_verdict(root, result["confirmed"])

    return {
        "skipped": False,
        "confirmed": confirmed,
        "acked": acked,
        "stale_acks": stale_acks,
        "verdict": aggregate_verdict(spec, confirmed),
    }
```

In `sync.py` `cmd_review`, the verdict print currently reads:

```python
            v = out.get("verdict", {})
            print(f"[archie] delivery review — {v.get('intent_completeness', '?')} criteria · "
                  f"{v.get('breaks', 0)} break(s) · {v.get('drift', 0)} drift · "
                  f"{len(out.get('confirmed', []))} finding(s)")
```

Replace with:

```python
            v = out.get("verdict", {})
            ack_note = (f" · {len(out.get('acked', []))} acknowledged override(s)"
                        if out.get("acked") else "")
            print(f"[archie] delivery review — {v.get('intent_completeness', '?')} criteria · "
                  f"{v.get('breaks', 0)} break(s) · {v.get('drift', 0)} drift · "
                  f"{len(out.get('confirmed', []))} finding(s)" + ack_note)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sync_review.py tests/test_review_core.py tests/test_delivery_review.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/sync_review.py archie/standalone/sync.py tests/test_sync_review.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): local sync review shares the acked/stale partition (one join, both surfaces)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: `sync.py override-ratify` — merge applies the amendment

**Files:**
- Modify: `archie/standalone/sync.py` (new command + dispatch entry, same regions as Task 2)
- Test: `tests/test_override_subcommands.py` (append)

**Interfaces:**
- Consumes: `overrides.pending_ratification(root)`, `overrides.archive(root, entry)` (Task 1).
- Produces: CLI `python3 sync.py override-ratify <root>` → for each acked entry whose `branch != current`: removes the rule from `.archie/rules.json`, stamps the matching `blueprint.json` `domain_invariants[]` entry with `status: "overridden"` + `override: {...}`, archives the entry. No-op (exit 0, `{"ratified": []}`) when nothing is pending. Renderer (Task 8) reads the stamp.

- [ ] **Step 1: Write the failing test** (append to `tests/test_override_subcommands.py`)

```python
def test_override_ratify_applies_contract_and_archives(tmp_path):
    _git_repo(tmp_path, branch="develop")           # entry below is from demo/x → pending
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "severity_class": "decision_violation", "description": "never store cost"},
        {"id": "arch-001", "severity_class": "pattern_divergence", "description": "keep"},
    ]}))
    (tmp_path / ".archie" / "blueprint.json").write_text(json.dumps({"domain_invariants": [
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "BillableStep"},
        {"id": "inv-001", "invariant": "keep me", "entity": "AgentRun"},
    ]}))
    (tmp_path / ".archie" / "overrides.json").write_text(json.dumps({"version": 1, "overrides": [
        {"rule_id": "inv-003", "reason": "store cost", "authorized_by": "Gabor <g@e.com>",
         "branch": "demo/x", "created_at": "2026-07-07T00:00:00Z", "status": "acked"}]}))

    r = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"ratified": ["inv-003"]}

    rules = json.loads((tmp_path / ".archie" / "rules.json").read_text())["rules"]
    assert [x["id"] for x in rules] == ["arch-001"]              # retired
    bp = json.loads((tmp_path / ".archie" / "blueprint.json").read_text())
    inv3 = next(x for x in bp["domain_invariants"] if x["id"] == "inv-003")
    assert inv3["status"] == "overridden"
    assert inv3["override"]["authorized_by"] == "Gabor <g@e.com>"
    assert ov.active(tmp_path) == {}                             # archived
    hist = (tmp_path / ".archie" / "overrides_history.jsonl").read_text()
    assert "ratified" in hist

    # idempotent: second run is a no-op
    r2 = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                        capture_output=True, text=True)
    assert json.loads(r2.stdout.strip().splitlines()[-1]) == {"ratified": []}


def test_override_ratify_skips_current_branch_entries(tmp_path):
    _git_repo(tmp_path, branch="demo/x")            # entry authored HERE → still active
    (tmp_path / ".archie" / "overrides.json").write_text(json.dumps({"version": 1, "overrides": [
        {"rule_id": "inv-003", "reason": "r", "authorized_by": "G",
         "branch": "demo/x", "created_at": "t", "status": "acked"}]}))
    r = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                       capture_output=True, text=True)
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"ratified": []}
    assert "inv-003" in ov.active(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_override_subcommands.py -q`
Expected: the two new tests FAIL (unknown subcommand).

- [ ] **Step 3: Write minimal implementation**

Add next to `cmd_override_ack`:

```python
def cmd_override_ratify(root: Path) -> int:
    """Apply ratified overrides to the contract. An acked entry whose branch is
    not the current branch can only have arrived via merge — merge IS the
    ratification. For each: retire the rule from rules.json, stamp the blueprint
    invariant `overridden` (the renderer marks it; the next deep scan re-derives
    the area from code), archive the entry. Deliberate contract change — run
    from the sync workflow. No-op when nothing is pending."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    import overrides as _ov
    archie = root / ".archie"
    done = []
    for e in _ov.pending_ratification(root):
        rid = e.get("rule_id", "")
        rp = archie / "rules.json"
        try:
            rules = json.loads(rp.read_text())
            items = rules.get("rules", []) if isinstance(rules, dict) else rules
            kept = [r for r in items if r.get("id") != rid]
            if len(kept) != len(items):
                if isinstance(rules, dict):
                    rules["rules"] = kept
                else:
                    rules = kept
                rp.write_text(json.dumps(rules, indent=2) + "\n")
        except Exception:
            pass
        bp_p = archie / "blueprint.json"
        try:
            bp = json.loads(bp_p.read_text())
            for inv in bp.get("domain_invariants") or []:
                if isinstance(inv, dict) and inv.get("id") == rid:
                    inv["status"] = "overridden"
                    inv["override"] = {"reason": e.get("reason", ""),
                                       "authorized_by": e.get("authorized_by", ""),
                                       "ratified_from": e.get("branch", "")}
            bp_p.write_text(json.dumps(bp, indent=2) + "\n")
        except Exception:
            pass
        _ov.archive(root, e, status="ratified")
        done.append(rid)
    print(json.dumps({"ratified": done}))
    return 0
```

Dispatch entry (next to `override-ack`):

```python
    if cmd == "override-ratify":
        return cmd_override_ratify(root)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_override_subcommands.py tests/test_overrides.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/sync.py tests/test_override_subcommands.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): sync.py override-ratify — merge applies the amendment to the contract

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Renderer — overridden/staged markers in product-laws.md

**Files:**
- Modify: `archie/standalone/renderer.py` — `_build_product_laws_rule(bp)` (def at ~line 2272) and `main()` (bp loaded at ~line 2445; anchors drift, read first)
- Test: `tests/test_renderer_overrides.py`

**Interfaces:**
- Consumes: `status: "overridden"` + `override: {...}` stamps from Task 7; `overrides.active(root)` for branch-staged acks.
- Produces: `product-laws.md` renders overridden/staged laws in a separate "no longer enforced" section instead of stating dead law as live truth.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_renderer_overrides.py
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import renderer  # noqa: E402


def test_product_laws_moves_overridden_out_of_enforced():
    bp = {"domain_invariants": [
        {"id": "inv-001", "invariant": "email unique per run", "entity": "EmailRotation",
         "category": "workflow", "enforced_at": ["worker/main.py:764"]},
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "BillableStep",
         "category": "billing", "enforced_at": ["worker/persister.py:1327"],
         "status": "overridden",
         "override": {"reason": "store cost — perf decision",
                      "authorized_by": "Gabor <g@e.com>", "ratified_from": "demo/x"}},
    ]}
    rule = renderer._build_product_laws_rule(bp)
    body = rule["body"]
    assert "Overridden — no longer enforced" in body
    assert "inv-003" in body and "store cost" in body and "Gabor" in body
    # the dead law must NOT appear in the enforced section
    enforced_part = body.split("Overridden — no longer enforced")[0]
    assert "cost is never stored" not in enforced_part
    assert "email unique per run" in enforced_part


def test_product_laws_marks_branch_staged_override():
    bp = {"domain_invariants": [
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "BillableStep",
         "category": "billing", "status": "override_staged",
         "override": {"reason": "store cost", "authorized_by": "Gabor <g@e.com>",
                      "branch": "demo/x"}},
    ]}
    body = renderer._build_product_laws_rule(bp)["body"]
    assert "staged" in body.lower() and "demo/x" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_renderer_overrides.py -q`
Expected: FAIL — no "Overridden" section; the dead law renders as enforced.

- [ ] **Step 3: Write minimal implementation**

In `_build_product_laws_rule`, right after `domain = [...]` is built, partition:

```python
    overridden = [x for x in domain if x.get("status") in ("overridden", "override_staged")]
    domain = [x for x in domain if x.get("status") not in ("overridden", "override_staged")]
```

After the grounded section (`lines += _render_grounded_by_role(domain, derived)` / its trailing `lines.append("")`), insert:

```python
    if overridden:
        lines += [
            "## ⛔ Overridden — no longer enforced",
            "",
            "_These laws were deliberately overridden by the user. `ratified` entries "
            "merged; `staged` entries are pending on a branch. The next deep scan "
            "re-derives this area from the current code — do not treat these as live "
            "constraints and do not \"fix\" code back to them._",
            "",
        ]
        for x in overridden:
            o = x.get("override") or {}
            state = ("staged on `" + o.get("branch", "?") + "`"
                     if x.get("status") == "override_staged" else "ratified")
            lines.append(f"- **{x.get('id', '?')}** — {x.get('invariant', '')}  ")
            lines.append(f"  _{state} · {o.get('reason', '')} · authorized by "
                         f"{o.get('authorized_by', '?')}_")
        lines.append("")
```

Also update the `if not (domain or derived or unenforced):` guard to include `overridden` (so a blueprint whose only laws are overridden still renders the file):

```python
    if not (domain or derived or unenforced or overridden):
        return None
```

In `main()`, right after `bp = json.loads(blueprint_path.read_text())`, stamp branch-staged acks so a sync render on the PR branch annotates immediately (ratified stamps are already persisted by Task 7):

```python
    # Branch-staged overrides: acked entries on THIS branch annotate the render
    # without mutating the stored blueprint (ratification persists the stamp).
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import overrides as _ov
        _act = _ov.active(project_root)
        for _inv in bp.get("domain_invariants") or []:
            _e = _act.get(_inv.get("id")) if isinstance(_inv, dict) else None
            if _e and not _inv.get("status"):
                _inv["status"] = "override_staged"
                _inv["override"] = {"reason": _e.get("reason", ""),
                                    "authorized_by": _e.get("authorized_by", ""),
                                    "branch": _e.get("branch", "")}
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_renderer_overrides.py -q` then the renderer's existing suite: `python3 -m pytest tests/ -q -k renderer`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/renderer.py tests/test_renderer_overrides.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): product-laws.md renders overridden/staged laws as no-longer-enforced

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Workflow texts — sync fold-in step + deep-scan tombstones

**Files:**
- Modify: `archie/assets/workflow/sync/SKILL.md` (canonical; steps listed at lines 17/27/46/95/105/136/161/185)
- Modify: `archie/assets/workflow/deep-scan/steps/step-5d-product.md`, `archie/assets/workflow/deep-scan/steps/step-6-rule-synthesis.md`
- Test: `tests/test_workflow_override_text.py` (content assertions — these are prompt files; the test pins the load-bearing phrases so a future edit can't silently drop them)

**Interfaces:**
- Consumes: `sync.py override-ratify` CLI (Task 7); `.archie/overrides.json` shape (Task 1).
- Produces: sync workflow ratifies + stages amendment claims; deep-scan agents receive tombstone instructions.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflow_override_text.py
from pathlib import Path

_WF = Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow"


def test_sync_skill_has_override_fold_step():
    text = (_WF / "sync" / "SKILL.md").read_text()
    assert "override-ratify" in text
    assert "overrides.json" in text
    assert "staged" in text          # acks fold into the staged-amendment flow


def test_deep_scan_product_and_rules_steps_have_tombstones():
    for step in ("step-5d-product.md", "step-6-rule-synthesis.md"):
        text = (_WF / "deep-scan" / "steps" / step).read_text()
        assert "overrides" in text.lower(), step
        assert "do not re-derive" in text.lower() or "do not carry" in text.lower(), step
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_workflow_override_text.py -q`
Expected: FAIL — none of the phrases present.

- [ ] **Step 3: Write the text additions**

**(a)** In `archie/assets/workflow/sync/SKILL.md`, insert between `### Step 2 — Record` section and `### Step 3 — Get the scoped targets`:

```markdown
### Step 2b — Fold override acknowledgments (and ratify merged ones)

Run `python3 .archie/sync.py override-ratify .` first — it is a no-op unless an
override entry merged in from another branch is pending. When it fires it retires
the rule from `rules.json`, stamps the blueprint invariant `overridden`, and
archives the entry to `overrides_history.jsonl`; your Step 5 render then updates
the docs automatically.

Then read `.archie/overrides.json`. For each entry with `status: "acked"` whose
`branch` is the CURRENT branch and which has no staged claim yet, record the break
through the normal Step 2 flow as a staged contract amendment: a `rule` claim
titled `override: <rule_id>`, rationale = the entry's `reason`, evidence_files =
the files the violating change touched. Advisory claims always stage — this is the
existing "user accepts a broken rule" path; the ack is its trigger. Never delete or
edit an override entry by hand.
```

**(b)** Append to `archie/assets/workflow/deep-scan/steps/step-5d-product.md`:

```markdown
## Override tombstones (read FIRST)

Read `.archie/overrides.json` and `.archie/overrides_history.jsonl` if present.
Any invariant id that appears there was DELIBERATELY overridden by the user and
(if ratified) merged. Do not re-derive that invariant, do not carry it forward
from the previous blueprint, and do not build derived laws on top of it. Re-derive
the affected area from what the current code actually does — if the code now
enforces a different guarantee, derive THAT one (cite-or-omit as always).
```

**(c)** Append to `archie/assets/workflow/deep-scan/steps/step-6-rule-synthesis.md`:

```markdown
## Override tombstones

Before synthesizing rules, read `.archie/overrides.json` and
`.archie/overrides_history.jsonl` if present. Do not synthesize an enforcement
rule for any rule/invariant id recorded there — the user deliberately overrode it
and the contract change was (or is being) ratified. Rules for the area come only
from what the current code exhibits.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_workflow_override_text.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/assets/workflow/sync/SKILL.md archie/assets/workflow/deep-scan/steps/step-5d-product.md archie/assets/workflow/deep-scan/steps/step-6-rule-synthesis.md tests/test_workflow_override_text.py
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "feat(override): sync workflow folds acks + ratifies; deep scan honors tombstones

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Package sync + registration + full green

**Files:**
- Modify: `npm-package/bin/archie.mjs` (script array at ~line 425)
- Copy: every canonical file Tasks 1–9 touched → `npm-package/assets/`
- Test: `python3 scripts/verify_sync.py` + full suite

- [ ] **Step 1: Register the new script**

In the `for (const script of [...])` array in `npm-package/bin/archie.mjs`, add `"overrides.py"`. Do not remove or reorder existing entries.

- [ ] **Step 2: Sync the mirror by driving off the checker**

```bash
python3 scripts/verify_sync.py
```

For EACH stale/missing file it names, `cp` the canonical to the mirror (never hand-edit an asset). Expected set: `overrides.py` (new), `sync.py`, `align_check.py`, `delivery_review.py`, `sync_review.py`, `renderer.py`, `hook_scripts/pre-validate.sh`, `workflow/sync/SKILL.md`, `workflow/deep-scan/steps/step-5d-product.md`, `workflow/deep-scan/steps/step-6-rule-synthesis.md` — copy exactly what the checker flags, no more, no less. Re-run until:

Expected: `SYNC CHECK PASSED — 59 scripts, workflow + assets all in sync.` (count = previous 58 + overrides.py; trust the checker's number).

- [ ] **Step 3: Full suite**

```bash
python3 -m pytest tests/test_overrides.py tests/test_override_subcommands.py \
  tests/test_pre_validate_overrides.py tests/test_align_check_overrides.py \
  tests/test_renderer_overrides.py tests/test_workflow_override_text.py \
  tests/test_delivery_review.py tests/test_sync_review.py tests/test_asset_sync.py -q
python3 -m pytest tests/ -q --continue-on-collection-errors 2>&1 | tail -3
```

Expected: targeted subset all PASS; broad suite shows ONLY the 3 known pre-existing failures (`churn_track`, `stop_nudges`, `codex_prefix`) + ~19 tomllib collection errors (Python 3.9, pre-existing). Any OTHER failure: check whether it failed at base before touching it; report honestly.

- [ ] **Step 4: Commit**

```bash
git add npm-package/
git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit -m "chore(override): package sync + register overrides.py

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Execution order & review notes

Tasks 1→2→3→4 remove the hardlock (ship-worthy on their own); 5→6 add surfacing; 7→8→9 complete ratification/evolution; 10 packages. Task order is dependency order — do not parallelize 5/6 before 1, or 8 before 7.

**Reviewer guidance (all tasks):** npm-mirror drift is deferred-by-design to Task 10 — do not flag it. Tasks 3–6 modify existing control flow — read the real function bodies first; the plan's line anchors WILL have drifted. The security-sensitive task is 3 (a bash hook that must fail toward blocking: a corrupt overrides.json must never suppress a rule it doesn't name — degrade to "no overrides", not "no enforcement").
