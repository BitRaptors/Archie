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
import re
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
    return _git(root, "symbolic-ref", "--short", "HEAD") or "HEAD"


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
    """Move a ruling from the active file to the append-only history log.

    Ordered history-first: a crash between the two writes must never erase
    the ruling from BOTH places. Appending to overrides_history.jsonl first
    means the worst case of an interrupted archive is a duplicate history
    record (harmless, append-only) with the entry still active — never a
    ruling that vanishes from both files.
    """
    rec = dict(entry)
    rec["status"] = status
    rec["archived_at"] = now or _now()
    h = Path(root) / ".archie" / HISTORY
    h.parent.mkdir(parents=True, exist_ok=True)
    with h.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    data = load(root)
    data["overrides"] = [e for e in data["overrides"]
                         if not (e.get("rule_id") == entry.get("rule_id")
                                 and e.get("branch") == entry.get("branch"))]
    save(root, data)


def finding_matches(finding: dict, rule_id: str) -> bool:
    """Join a review finding to a rule id: invariant findings carry the id in
    their finding id (f_inv_<rule>), problem statement, or assumptions.

    Boundary-matched, not substring: a raw `rule_id in text` check lets a
    crafted short rule_id (e.g. "e") absorb nearly every finding and zero the
    PR's break count. The finding-id check is exact equality against the
    `f_inv_<rule_id>` shape; statement/assumptions checks require rule_id to
    appear as a whole word (so "inv-003" never matches inside "inv-0031")."""
    if not rule_id:
        return False
    if str(finding.get("id", "")) == f"f_inv_{rule_id}":
        return True
    pattern = rf"\b{re.escape(rule_id)}\b"
    if re.search(pattern, str(finding.get("problem_statement", ""))):
        return True
    return any(re.search(pattern, str(a)) for a in (finding.get("assumptions") or []))


_ID_RX = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+\b")


def rule_aliases(root, rule_id: str) -> set:
    """Ids of the domain laws a rules.json rule is grounded in.

    Deep scans generate SHORT rule ids (inv-003) that differ from the blueprint
    invariant ids (inv-subscribe-workflow-003) the invariant-specialist findings
    reference — without this, an acked override never matched its own violation
    (it counted as a break AND the ack rendered stale; SubscriberAgent PR #17).
    The rule's `forced_by` field cites the source law by id; extract those ids
    (plus explicit source_invariant/invariant_id fields when present)."""
    try:
        data = json.loads((Path(root) / ".archie" / "rules.json").read_text())
        items = data.get("rules", data) if isinstance(data, dict) else data
        for r in items:
            if isinstance(r, dict) and r.get("id") == rule_id:
                srcs = " ".join(str(r.get(k, "")) for k in
                                ("forced_by", "source_invariant", "invariant_id"))
                return {m for m in _ID_RX.findall(srcs) if m != rule_id}
    except Exception:
        pass
    return set()


def partition(findings: list, active_map: dict, root=None) -> tuple:
    """Split findings by ruling: (unacked, acked, stale).

    unacked — findings with no matching override (count as breaks).
    acked   — [(entry, [matching findings])] (surfaced, not counted).
    stale   — override entries with NO matching finding this run (the violation
              is no longer observed — flag for removal before merge).

    When `root` is given, each ack also matches findings that reference the
    invariant ids its rule is grounded in (see rule_aliases)."""
    alias_of: dict = {}
    for rid in active_map:
        alias_of[rid] = rid
        if root is not None:
            for a in rule_aliases(root, rid):
                alias_of.setdefault(a, rid)
    unacked = []
    by_rule: dict = {}
    for f in findings:
        rid = next((alias_of[a] for a in alias_of if finding_matches(f, a)), None)
        if rid is None:
            unacked.append(f)
        else:
            by_rule.setdefault(rid, []).append(f)
    acked = [(active_map[r], fs) for r, fs in by_rule.items()]
    stale = [e for r, e in active_map.items() if r not in by_rule]
    return unacked, acked, stale
