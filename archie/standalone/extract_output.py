#!/usr/bin/env python3
"""Archie extract_output — robust extraction of agent output for the pipeline.

Replaces all inline python3 -c one-liners in archie-init.md and archie-drift.md.
Uses merge.extract_json_from_text to handle conversation envelopes, code fences,
and AI escape issues.

Subcommands:
  rules             <input_file> <output_path>   — extract rules JSON from agent output
  deep-drift        <input_file> <report_path>   — extract deep findings, merge into drift report
  recent-files      <scan_json>                  — print source file paths from scan.json
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

def cmd_rules(input_file: str, output_path: str):
    """Extract rules JSON from raw agent output, merge with existing rules, save."""
    text = Path(input_file).read_text()
    data = extract_json_from_text(text)
    if not data:
        print("ERROR: could not extract rules JSON", file=sys.stderr)
        sys.exit(1)

    new_rules = data.get("rules", [])

    # Merge with existing rules — preserve user-adopted rules from /archie-scan
    out = Path(output_path)
    if out.exists():
        try:
            existing = json.loads(out.read_text())
            existing_rules = existing.get("rules", [])
            # Index existing rules by id
            existing_by_id = {r.get("id", ""): r for r in existing_rules if isinstance(r, dict)}
            # Index new rules by id
            new_by_id = {r.get("id", ""): r for r in new_rules if isinstance(r, dict)}
            # Keep existing rules that aren't replaced by new ones (user-adopted rules)
            # Also keep existing rules that have source="adopted" — these came from /archie-scan
            preserved = 0
            for rid, rule in existing_by_id.items():
                if rid not in new_by_id:
                    new_rules.append(rule)
                    preserved += 1
            if preserved:
                print(f"  Preserved {preserved} existing rules not in new set", file=sys.stderr)
        except (json.JSONDecodeError, OSError):
            pass

    data["rules"] = new_rules
    out.write_text(json.dumps(data, indent=2))
    print(f"Saved {len(new_rules)} rules to {output_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# deep-drift — extract deep findings and merge into drift report
# ---------------------------------------------------------------------------

def cmd_deep_drift(input_file: str, report_path: str):
    """Extract deep architectural findings from agent output, merge into drift report."""
    text = Path(input_file).read_text()
    data = extract_json_from_text(text)

    if not data:
        print("Warning: could not extract deep findings", file=sys.stderr)
        sys.exit(1)

    report_file = Path(report_path)
    if report_file.exists():
        report = json.loads(report_file.read_text())
    else:
        report = {"summary": {"total_findings": 0, "warnings": 0}}

    deep_findings = data.get("deep_findings", [])
    report["deep_findings"] = deep_findings

    s = report["summary"]
    deep_count = len(deep_findings)
    s["deep_findings"] = deep_count
    s["total_findings"] = s.get("total_findings", 0) + deep_count
    s["warnings"] = s.get("warnings", 0) + sum(
        1 for f in deep_findings if f.get("severity") == "warn"
    )

    report_file.write_text(json.dumps(report, indent=2))
    print(f"Added {deep_count} deep findings to {report_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# recent-files — print source file paths from scan.json
# ---------------------------------------------------------------------------

_SOURCE_EXTENSIONS = {
    ".kt", ".java", ".swift", ".ts", ".tsx", ".js", ".jsx",
    ".py", ".go", ".rs", ".rb", ".dart", ".cs", ".cpp", ".c", ".h",
    ".m", ".scala", ".clj", ".ex", ".exs", ".zig", ".lua",
}


def cmd_recent_files(scan_json: str):
    """Print source file paths from scan.json, one per line."""
    data = json.loads(Path(scan_json).read_text())
    file_tree = data.get("file_tree", [])

    count = 0
    for f in file_tree:
        ext = f.get("extension", "")
        if ext in _SOURCE_EXTENSIONS:
            print(f["path"])
            count += 1
            if count >= 100:
                break

    print(f"Listed {count} source files", file=sys.stderr)


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
        print("  python3 extract_output.py deep-drift <input_file> <report_path>", file=sys.stderr)
        print("  python3 extract_output.py recent-files <scan_json>", file=sys.stderr)
        print("  python3 extract_output.py save-duplications <agent_c_file> <project_root>", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]

    if subcmd == "rules":
        if len(sys.argv) < 4:
            print("Usage: extract_output.py rules <input_file> <output_path>", file=sys.stderr)
            sys.exit(1)
        cmd_rules(sys.argv[2], sys.argv[3])

    elif subcmd == "deep-drift":
        if len(sys.argv) < 4:
            print("Usage: extract_output.py deep-drift <input_file> <report_path>", file=sys.stderr)
            sys.exit(1)
        cmd_deep_drift(sys.argv[2], sys.argv[3])

    elif subcmd == "recent-files":
        if len(sys.argv) < 3:
            print("Usage: extract_output.py recent-files <scan_json>", file=sys.stderr)
            sys.exit(1)
        cmd_recent_files(sys.argv[2])

    elif subcmd == "save-duplications":
        if len(sys.argv) < 4:
            print("Usage: extract_output.py save-duplications <agent_c_file> <project_root>", file=sys.stderr)
            sys.exit(1)
        cmd_save_duplications(sys.argv[2], sys.argv[3])

    else:
        print(f"Unknown subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)
