#!/usr/bin/env python3
"""Archie standalone blueprint merger — merges subagent JSON outputs.

Run: python3 merge.py /path/to/repo output1.json [output2.json ...]
  Or: echo '{"components": ...}' | python3 merge.py /path/to/repo -

Reads subagent JSON outputs (files or stdin), merges into single blueprint,
saves to .archie/blueprint.json.

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def deep_merge(base: dict, overlay: dict) -> dict:
    """Merge overlay into base. Lists are concatenated, dicts are recursed."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # Deduplicate by 'name' field if items are dicts
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
                # Prefer non-empty values
                result[key] = value
        else:
            result[key] = value
    return result


def merge_outputs(outputs: list[dict], repo_name: str = "") -> dict:
    """Merge multiple subagent outputs into a single blueprint."""
    if not outputs:
        return {}

    merged = {}
    for output in outputs:
        merged = deep_merge(merged, output)

    # Fill meta
    meta = merged.setdefault("meta", {})
    if not meta.get("repository"):
        meta["repository"] = repo_name or Path.cwd().name
    if not meta.get("analyzed_at"):
        meta["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    if not meta.get("schema_version"):
        meta["schema_version"] = "2.0.0"

    return merged


def extract_json_from_text(text: str) -> dict | None:
    """Extract a JSON object from text that may contain markdown or other content."""
    # Try parsing the whole thing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    import re
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first { and matching to last }
    start = text.find('{')
    if start >= 0:
        # Find the matching closing brace
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 merge.py /path/to/repo [file1.json file2.json ...]", file=sys.stderr)
        print("  Or:  echo '{...}' | python3 merge.py /path/to/repo -", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    input_files = sys.argv[2:] if len(sys.argv) > 2 else []

    outputs: list[dict] = []

    if not input_files or input_files == ["-"]:
        # Read from stdin
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
        # Check if there's an existing blueprint to use as base
        bp_path = root / ".archie" / "blueprint.json"
        if bp_path.exists():
            print("No new outputs. Keeping existing blueprint.", file=sys.stderr)
            sys.exit(0)
        print("Error: no valid outputs to merge", file=sys.stderr)
        sys.exit(1)

    merged = merge_outputs(outputs, repo_name=root.name)

    # Save
    archie_dir = root / ".archie"
    archie_dir.mkdir(exist_ok=True)
    bp_path = archie_dir / "blueprint.json"
    bp_path.write_text(json.dumps(merged, indent=2))

    components = merged.get("components", {})
    comp_count = len(components.get("components", [])) if isinstance(components, dict) else 0
    rules_count = len(merged.get("architecture_rules", {}).get("file_placement_rules", []))
    print(f"Blueprint saved: {comp_count} components, {rules_count} placement rules", file=sys.stderr)
