#!/usr/bin/env python3
"""Archie standalone blueprint merger — merges subagent JSON outputs.

Run: python3 merge.py /path/to/repo output1.json [output2.json ...]
  Or: echo '{"components": ...}' | python3 merge.py /path/to/repo -

Reads subagent JSON outputs (files or stdin), deep-merges into a single dict,
saves raw to .archie/blueprint_raw.json. Does NOT normalize field names —
that is handled by a separate AI normalizer step.

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import re
import sys
from pathlib import Path


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

    # Try all possible JSON object boundaries — find the largest valid one
    for start in range(len(text)):
        if text[start] != '{':
            continue
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
        # Only try first few start positions to avoid O(n^2) on large files
        if start > 500:
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

    # Save raw merged output (pre-normalization)
    archie_dir = root / ".archie"
    archie_dir.mkdir(exist_ok=True)
    bp_path_raw = archie_dir / "blueprint_raw.json"
    bp_path_raw.write_text(json.dumps(merged, indent=2))

    # Also save as blueprint.json (will be overwritten by AI normalizer)
    bp_path = archie_dir / "blueprint.json"
    bp_path.write_text(json.dumps(merged, indent=2))

    comp_count = 0
    comps = merged.get("components", {})
    if isinstance(comps, list):
        comp_count = len(comps)
    elif isinstance(comps, dict):
        comp_count = len(comps.get("components", []))

    section_count = len([k for k in merged if merged[k]])
    print(f"Blueprint merged: {section_count} sections, {comp_count} components", file=sys.stderr)
    print(f"Raw saved: {bp_path_raw}", file=sys.stderr)
    print(f"Awaiting AI normalization step.", file=sys.stderr)
