#!/usr/bin/env python3
"""Archie extract_output — robust extraction of agent output for the pipeline.

Replaces inline python3 -c one-liners in the workflow files.
Uses merge.extract_json_from_text to handle conversation envelopes, code fences,
and AI escape issues.

Subcommands:
  rules             <input_file> <output_path>   — extract rules JSON from agent output
  save-duplications <agent_c_file> <project_root>  — write .archie/semantic_duplications.json

Zero dependencies beyond Python 3.9+ stdlib + sibling merge.py.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import extract_json_from_text from sibling merge.py
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))
from merge import extract_json_from_text  # noqa: E402


# ---------------------------------------------------------------------------
# rules — extract rules JSON from agent output
# ---------------------------------------------------------------------------

def _read_rule_ids(path: Path) -> set:
    """Rule ids in a {"rules": [...]} file; empty set on missing/malformed."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    return {r.get("id") for r in data.get("rules", []) if isinstance(r, dict) and r.get("id")}


def cmd_rules(input_file: str, output_path: str):
    """Extract rules JSON from raw agent output, merge with existing rules, save.

    Defensively stamps `source: "deep_scan"` on any new rule emitted without one,
    so downstream tooling and humans can trace lineage even if the model omits
    the field. Existing `source` values (e.g., `adopted`, `scan`, `scan-amended`)
    are never overwritten.

    Adoption gate: on a RERUN (output rules.json already has rules), rules with
    an id not seen before go to proposed_rules.json — the user adopts or rejects
    them in the viewer's Rules card before hooks enforce them. Updates to
    already-active ids still apply directly. Ids sitting in proposed_rules.json
    or ignored_rules.json are not re-proposed. The first scan (empty baseline)
    keeps auto-adopting, otherwise a fresh install would enforce nothing.
    """
    text = Path(input_file).read_text()
    data = extract_json_from_text(text)
    if not data:
        print("ERROR: could not extract rules JSON", file=sys.stderr)
        sys.exit(1)

    new_rules = data.get("rules", [])

    # Stamp source defensively on every new rule that doesn't carry one.
    # Phase 1 contract: rules produced by Step 6 (Sonnet rule synthesis) are
    # `deep_scan`. The model is asked to emit this field but we don't trust it.
    stamped = 0
    for r in new_rules:
        if isinstance(r, dict) and not r.get("source"):
            r["source"] = "deep_scan"
            stamped += 1
    if stamped:
        print(f"  Stamped source=deep_scan on {stamped} rule(s)", file=sys.stderr)

    # Merge with existing rules — preserve user-adopted rules from prior runs
    out = Path(output_path)
    existing_by_id = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text())
            existing_rules = existing.get("rules", [])
            existing_by_id = {r.get("id", ""): r for r in existing_rules if isinstance(r, dict)}
        except (json.JSONDecodeError, OSError):
            existing_by_id = {}

    if existing_by_id:
        # RERUN — route brand-new rules through the proposal queue.
        proposed_path = out.parent / "proposed_rules.json"
        ignored_ids = _read_rule_ids(out.parent / "ignored_rules.json")
        already_proposed = _read_rule_ids(proposed_path)

        active, to_propose = [], []
        for r in new_rules:
            rid = r.get("id") if isinstance(r, dict) else None
            if rid in existing_by_id:
                active.append(r)  # update of an already-active rule
            elif rid in ignored_ids or rid in already_proposed:
                continue  # user already rejected it, or it's awaiting review
            else:
                to_propose.append(r)

        new_by_id = {r.get("id", ""): r for r in active if isinstance(r, dict)}
        preserved = 0
        for rid, rule in existing_by_id.items():
            if rid not in new_by_id:
                active.append(rule)
                preserved += 1
        if preserved:
            print(f"  Preserved {preserved} existing rules not in new set", file=sys.stderr)

        if to_propose:
            try:
                proposed = json.loads(proposed_path.read_text())
            except (OSError, json.JSONDecodeError):
                proposed = {}
            proposed.setdefault("rules", []).extend(to_propose)
            proposed_path.write_text(json.dumps(proposed, indent=2))
            print(f"  {len(to_propose)} NEW rule(s) -> {proposed_path.name} — "
                  f"awaiting adoption (review in /archie-viewer Rules card); "
                  f"hooks will not enforce them until adopted", file=sys.stderr)

        new_rules = active

    data["rules"] = new_rules
    out.write_text(json.dumps(data, indent=2))
    print(f"Saved {len(new_rules)} rules to {output_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# save-duplications — extract Agent C's duplications and write to .archie/
# ---------------------------------------------------------------------------

def cmd_save_duplications(agent_c_file: str, project_root: str):
    """Write Agent C's semantic duplications to .archie/semantic_duplications.json.

    Writes an empty `duplications: []` list when Agent C's output is absent or
    has no duplications — so `/archie-share` always carries a structured field
    and the viewer never has to guess from the markdown scan report.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    duplications: list = []

    src = Path(agent_c_file)
    if src.exists():
        try:
            data = extract_json_from_text(src.read_text())
        except OSError:
            data = None
        if isinstance(data, dict):
            raw = data.get("duplications")
            if isinstance(raw, list):
                duplications = raw

    out_dir = Path(project_root) / ".archie"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "semantic_duplications.json"
    payload = {"duplications": duplications, "scanned_at": now}
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_path} ({len(duplications)} duplications)", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  python3 extract_output.py rules <input_file> <output_path>", file=sys.stderr)
        print("  python3 extract_output.py save-duplications <agent_c_file> <project_root>", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]

    if subcmd == "rules":
        if len(sys.argv) < 4:
            print("Usage: extract_output.py rules <input_file> <output_path>", file=sys.stderr)
            sys.exit(1)
        cmd_rules(sys.argv[2], sys.argv[3])

    elif subcmd == "save-duplications":
        if len(sys.argv) < 4:
            print("Usage: extract_output.py save-duplications <agent_c_file> <project_root>", file=sys.stderr)
            sys.exit(1)
        cmd_save_duplications(sys.argv[2], sys.argv[3])

    else:
        print(f"Unknown subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)
