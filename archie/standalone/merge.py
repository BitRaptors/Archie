#!/usr/bin/env python3
"""Archie standalone blueprint merger — merges subagent JSON outputs.

Run: python3 merge.py /path/to/repo output1.json [output2.json ...]
  Or: echo '{"components": ...}' | python3 merge.py /path/to/repo -

Reads subagent JSON outputs (files or stdin), merges into single blueprint,
normalizes to StructuredBlueprint schema, saves to .archie/blueprint.json.

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema normalizer — converts any subagent shape to expected schema
# ---------------------------------------------------------------------------

def _detect_convention(text: str) -> str:
    """Detect naming convention from rule text."""
    t = text.lower()
    if "pascalcase" in t or "pascal" in t:
        return "PascalCase"
    if "camelcase" in t or "camel" in t:
        return "camelCase"
    if "snake_case" in t or "snake" in t:
        return "snake_case"
    if "kebab" in t:
        return "kebab-case"
    return ""


def normalize_blueprint(bp: dict, repo_name: str = "") -> dict:
    """Normalize a blueprint dict to match StructuredBlueprint schema.

    Subagents may return flat lists where the schema expects nested dicts.
    This function ensures every section has the correct shape.
    """
    # meta
    meta = bp.get("meta", {})
    if not isinstance(meta, dict):
        meta = {"executive_summary": str(meta)} if meta else {}
    meta.setdefault("repository", repo_name or "")
    meta.setdefault("analyzed_at", datetime.now(timezone.utc).isoformat())
    meta.setdefault("schema_version", "2.0.0")
    bp["meta"] = meta

    # architecture_rules: expect {"file_placement_rules": [...], "naming_conventions": [...]}
    arch = bp.get("architecture_rules", {})
    if isinstance(arch, list):
        # Flat list — could be {rule, rationale} dicts or mixed placement/naming
        placement, naming = [], []
        for r in arch:
            if not isinstance(r, dict):
                continue
            if any(k in r for k in ("location", "naming_pattern", "component_type")):
                placement.append(r)
            elif any(k in r for k in ("scope", "pattern", "convention", "examples")):
                naming.append(r)
            elif "rule" in r:
                # Generic {rule, rationale, enforcement} format from subagent
                rule_text = r.get("rule", "")
                rule_lower = rule_text.lower()
                if any(w in rule_lower for w in ("naming", "case", "pascal", "camel", "snake", "kebab")):
                    # It's a naming convention
                    naming.append({
                        "scope": "files",
                        "pattern": _detect_convention(rule_text),
                        "examples": [],
                        "description": rule_text,
                    })
                else:
                    # Treat as a file placement / general rule
                    placement.append({
                        "description": rule_text,
                        "location": "",
                        "component_type": "",
                        "naming_pattern": "",
                        "example": "",
                    })
            else:
                placement.append(r)
        bp["architecture_rules"] = {"file_placement_rules": placement, "naming_conventions": naming}
    elif isinstance(arch, dict):
        arch.setdefault("file_placement_rules", [])
        arch.setdefault("naming_conventions", [])
        bp["architecture_rules"] = arch
    else:
        bp["architecture_rules"] = {"file_placement_rules": [], "naming_conventions": []}

    # components: expect {"structure_type": "...", "components": [...], "contracts": [...]}
    comps = bp.get("components", {})
    if isinstance(comps, list):
        bp["components"] = {"structure_type": "", "components": comps, "contracts": []}
    elif isinstance(comps, dict):
        if "components" not in comps and any(isinstance(v, str) for v in comps.values()):
            # Single component dict, not the wrapper
            bp["components"] = {"structure_type": "", "components": [comps], "contracts": []}
        else:
            comps.setdefault("structure_type", "")
            comps.setdefault("components", [])
            comps.setdefault("contracts", [])
            bp["components"] = comps
    else:
        bp["components"] = {"structure_type": "", "components": [], "contracts": []}

    # Normalize key_files in components to list[dict]
    for comp in bp["components"]["components"]:
        if not isinstance(comp, dict):
            continue
        kf = comp.get("key_files", [])
        if kf and isinstance(kf[0], str):
            comp["key_files"] = [{"path": f, "purpose": ""} for f in kf]
        # Ensure location field exists (some subagents use "path" instead)
        if not comp.get("location") and comp.get("path"):
            comp["location"] = comp["path"]

    # decisions: expect {"architectural_style": {...}, "key_decisions": [...], ...}
    dec = bp.get("decisions", {})
    if isinstance(dec, list):
        bp["decisions"] = {"architectural_style": {}, "key_decisions": dec, "trade_offs": [], "out_of_scope": []}
    elif isinstance(dec, dict):
        dec.setdefault("architectural_style", {})
        dec.setdefault("key_decisions", [])
        dec.setdefault("trade_offs", [])
        dec.setdefault("out_of_scope", [])
        bp["decisions"] = dec
    else:
        bp["decisions"] = {"architectural_style": {}, "key_decisions": [], "trade_offs": [], "out_of_scope": []}

    # communication: expect {"patterns": [...], "integrations": [...], "pattern_selection_guide": [...]}
    comm = bp.get("communication", {})
    if isinstance(comm, list):
        bp["communication"] = {"patterns": comm, "integrations": [], "pattern_selection_guide": []}
    elif isinstance(comm, dict):
        comm.setdefault("patterns", [])
        comm.setdefault("integrations", [])
        comm.setdefault("pattern_selection_guide", [])
        bp["communication"] = comm
    else:
        bp["communication"] = {"patterns": [], "integrations": [], "pattern_selection_guide": []}

    # quick_reference: expect {"where_to_put_code": {}, "pattern_selection": {}, "error_mapping": []}
    qr = bp.get("quick_reference", {})
    if not isinstance(qr, dict):
        qr = {}
    qr.setdefault("where_to_put_code", {})
    qr.setdefault("pattern_selection", {})
    qr.setdefault("error_mapping", [])
    bp["quick_reference"] = qr

    # technology: expect {"stack": [...], "templates": [...], "project_structure": "", "run_commands": {}}
    tech = bp.get("technology", {})
    if isinstance(tech, list):
        bp["technology"] = {"stack": tech, "templates": [], "project_structure": "", "run_commands": {}}
    elif isinstance(tech, dict):
        tech.setdefault("stack", [])
        tech.setdefault("templates", [])
        tech.setdefault("project_structure", "")
        tech.setdefault("run_commands", {})
        bp["technology"] = tech
    else:
        bp["technology"] = {"stack": [], "templates": [], "project_structure": "", "run_commands": {}}

    # frontend: expect {"framework": "", "rendering_strategy": "", ...}
    fe = bp.get("frontend", {})
    if isinstance(fe, str):
        bp["frontend"] = {"framework": fe}
    elif not isinstance(fe, dict):
        bp["frontend"] = {}
    # Normalize state_management to dict
    sm = bp.get("frontend", {}).get("state_management")
    if isinstance(sm, str):
        bp["frontend"]["state_management"] = {"approach": sm}

    # deployment: expect {"runtime_environment": "", ...}
    dep = bp.get("deployment", {})
    if isinstance(dep, str):
        bp["deployment"] = {"runtime_environment": dep}
    elif isinstance(dep, list):
        bp["deployment"] = {"runtime_environment": ", ".join(str(d) for d in dep)}
    elif not isinstance(dep, dict):
        bp["deployment"] = {}

    # List sections — ensure they're lists
    for key in ("developer_recipes", "pitfalls", "implementation_guidelines", "development_rules"):
        val = bp.get(key, [])
        if not isinstance(val, list):
            bp[key] = [val] if val else []

    # architecture_diagram — ensure string
    diag = bp.get("architecture_diagram", "")
    if not isinstance(diag, str):
        bp["architecture_diagram"] = str(diag) if diag else ""

    return bp


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def deep_merge(base: dict, overlay: dict) -> dict:
    """Merge overlay into base. Lists are concatenated, dicts are recursed."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                existing_names = set()
                for item in result[key]:
                    if isinstance(item, dict) and "name" in item:
                        existing_names.add(item["name"])
                for item in value:
                    if isinstance(item, dict) and "name" in item:
                        if item["name"] not in existing_names:
                            result[key].append(item)
                            existing_names.add(item["name"])
                    elif item not in result[key]:
                        result[key].append(item)
            elif not result[key] and value:
                result[key] = value
        else:
            result[key] = value
    return result


def extract_json_from_text(text: str) -> dict | None:
    """Extract a JSON object from text that may contain markdown or other content."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    break

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 merge.py /path/to/repo [file1.json file2.json ...]", file=sys.stderr)
        print("  Or:  echo '{...}' | python3 merge.py /path/to/repo -", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    input_files = sys.argv[2:] if len(sys.argv) > 2 else []

    outputs: list[dict] = []

    if not input_files or input_files == ["-"]:
        text = sys.stdin.read()
        parsed = extract_json_from_text(text)
        if parsed:
            outputs.append(parsed)
        else:
            print("Error: could not parse JSON from stdin", file=sys.stderr)
            sys.exit(1)
    else:
        for f in input_files:
            try:
                text = Path(f).read_text()
                parsed = extract_json_from_text(text)
                if parsed:
                    outputs.append(parsed)
                    print(f"  Loaded: {f}", file=sys.stderr)
                else:
                    print(f"  Warning: could not parse JSON from {f}", file=sys.stderr)
            except OSError as e:
                print(f"  Warning: could not read {f}: {e}", file=sys.stderr)

    if not outputs:
        bp_path = root / ".archie" / "blueprint.json"
        if bp_path.exists():
            print("No new outputs. Keeping existing blueprint.", file=sys.stderr)
            sys.exit(0)
        print("Error: no valid outputs to merge", file=sys.stderr)
        sys.exit(1)

    # Merge all outputs
    merged = {}
    for output in outputs:
        merged = deep_merge(merged, output)

    # Normalize to StructuredBlueprint schema
    merged = normalize_blueprint(merged, repo_name=root.name)

    # Save
    archie_dir = root / ".archie"
    archie_dir.mkdir(exist_ok=True)
    bp_path = archie_dir / "blueprint.json"
    bp_path.write_text(json.dumps(merged, indent=2))

    comp_count = len(merged.get("components", {}).get("components", []))
    rules_count = len(merged.get("architecture_rules", {}).get("file_placement_rules", []))
    naming_count = len(merged.get("architecture_rules", {}).get("naming_conventions", []))
    print(f"Blueprint saved: {comp_count} components, {rules_count} placement rules, {naming_count} naming conventions", file=sys.stderr)
