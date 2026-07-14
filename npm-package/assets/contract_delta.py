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
        inv_ids = e.get("invariant_ids")
        if not law or inv_ids is None:
            # Legacy entry (pre-snapshot): the rule is still in rules.json, so read it.
            # A snapshotted entry MUST NOT fall back — override-ack removed the rule,
            # and rule_aliases() would silently return nothing.
            if by_id is None:
                by_id = _rules(root)
            if not law:
                law = str((by_id.get(rid) or {}).get("description", ""))
            if inv_ids is None:
                inv_ids = sorted(_ov.rule_aliases(root, rid))
        out.append({
            "rule_id": rid,
            "law": law,
            "reason": str(e.get("reason", "")),
            "authorized_by": str(e.get("authorized_by", "")),
            "date": str(e.get("created_at", ""))[:10],
            "invariant_ids": sorted(inv_ids),
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
    # keyed_diff emits REMOVE / UPDATE / ADD (uppercase). Never trust the casing.
    op = str(item.get("diff_op", "")).lower()
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
