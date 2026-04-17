#!/usr/bin/env python3
"""Archie standalone blueprint merger — merges subagent JSON outputs.

Run: python3 merge.py /path/to/repo output1.json [output2.json ...]
  Or: echo '{"components": ...}' | python3 merge.py /path/to/repo -

Reads subagent JSON outputs (files or stdin), deep-merges into a single dict,
saves raw to .archie/blueprint_raw.json. Does NOT normalize field names —
that is handled by a separate AI normalizer step.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

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


def _fix_json_escapes(text: str) -> str:
    """Fix common invalid JSON escapes produced by AI models."""
    # Fix invalid \$ (not a valid JSON escape)
    text = text.replace("\\$", "$")
    # Fix unescaped control chars inside strings — replace with space
    # (newlines/tabs inside JSON string values that aren't properly escaped)
    return text


def _try_parse_json(text: str) -> dict | None:
    """Try parsing JSON with progressively more lenient fixups."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try fixing common escape issues
    try:
        return json.loads(_fix_json_escapes(text))
    except json.JSONDecodeError:
        pass
    return None


def _unwrap_conversation_envelope(text: str) -> str | None:
    """Extract content from Claude Code agent conversation NDJSON envelope.

    Agent outputs saved by Claude Code are NDJSON where each line is a
    conversation record like {"parentUuid":...,"message":{...},"type":"assistant"}.
    The actual content is in message.content[].text of assistant records.
    """
    # Quick check: does this look like NDJSON with conversation records?
    if not text.lstrip().startswith('{"parentUuid"') and not text.lstrip().startswith('{"isSidechain"'):
        return None

    content_parts = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Only look at assistant messages
        if record.get("type") != "assistant":
            continue
        msg = record.get("message", {})
        for block in msg.get("content", []):
            if isinstance(block, dict):
                if block.get("type") == "text":
                    content_parts.append(block["text"])
                elif "text" in block:
                    content_parts.append(block["text"])
                # Skip tool_use, tool_result, etc. — expected envelope types
            elif isinstance(block, str):
                content_parts.append(block)

    return "\n".join(content_parts) if content_parts else None


def _brace_match_extract(text: str) -> dict | None:
    """Find the first valid JSON object using string-aware brace matching.

    Skips braces inside quoted strings so {"msg": "hello } world"} parses correctly.
    """
    i = 0
    limit = len(text)
    attempts = 0
    while i < limit and attempts < 20:
        if text[i] != '{':
            i += 1
            continue
        attempts += 1
        # Walk forward tracking depth, skipping string contents
        depth = 0
        j = i
        in_string = False
        while j < limit:
            ch = text[j]
            if in_string:
                if ch == '\\':
                    j += 2  # skip escaped char
                    continue
                if ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        result = _try_parse_json(text[i:j + 1])
                        if result is not None:
                            return result
                        break
            j += 1
        i = j + 1 if j < limit else limit
    return None


def extract_json_from_text(text: str) -> dict | None:
    """Extract a JSON object from text that may contain markdown, conversation
    envelopes, or other wrapper content.  Handles:
    - Plain JSON
    - JSON inside ```json code fences
    - Claude Code agent NDJSON conversation envelopes
    - Minor escape issues from AI-generated JSON
    """
    # 1. Try direct parse
    result = _try_parse_json(text)
    if result is not None:
        return result

    # 2. Try unwrapping conversation envelope
    unwrapped = _unwrap_conversation_envelope(text)
    if unwrapped:
        result = _try_parse_json(unwrapped)
        if result is not None:
            return result
        # Envelope unwrapped but content isn't plain JSON — continue with
        # the unwrapped text for code-fence / brace-matching extraction
        text = unwrapped

    # 3. Try extracting from code fences — find JSON blocks inside ```
    fences = list(re.finditer(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL))
    for match in reversed(fences):
        block = match.group(1).strip()
        if block.startswith("{"):
            result = _try_parse_json(block)
            if result is not None:
                return result

    # 4. Brace-matching fallback — string-aware to handle braces inside quotes
    result = _brace_match_extract(text)
    if result is not None:
        return result

    return None


# ---------------------------------------------------------------------------
# Capabilities merging
# ---------------------------------------------------------------------------

def merge_capabilities(blueprint: dict, capabilities_input: list) -> tuple[int, int]:
    """Validate and append capability entries to blueprint['capabilities'].

    Cross-references each entry's uses_components, constrained_by_decisions,
    and related_pitfalls against known names in the blueprint. Unknown refs are
    dropped (the entry is still kept). Returns (accepted_count, dropped_ref_count).
    """
    known_components = {
        c.get("name")
        for c in blueprint.get("components", []) or []
        if isinstance(c, dict) and c.get("name")
    }
    known_decisions = {
        d.get("title")
        for d in (blueprint.get("decisions", {}) or {}).get("key_decisions", []) or []
        if isinstance(d, dict) and d.get("title")
    }
    known_pitfalls = {
        p.get("area")
        for p in blueprint.get("pitfalls", []) or []
        if isinstance(p, dict) and p.get("area")
    }

    accepted = 0
    dropped = 0

    blueprint.setdefault("capabilities", [])

    for entry in capabilities_input or []:
        if not isinstance(entry, dict) or not entry.get("name"):
            dropped += 1
            continue

        filtered_components = []
        for ref in entry.get("uses_components", []) or []:
            if ref in known_components:
                filtered_components.append(ref)
            else:
                dropped += 1

        filtered_decisions = []
        for ref in entry.get("constrained_by_decisions", []) or []:
            if ref in known_decisions:
                filtered_decisions.append(ref)
            else:
                dropped += 1

        filtered_pitfalls = []
        for ref in entry.get("related_pitfalls", []) or []:
            if ref in known_pitfalls:
                filtered_pitfalls.append(ref)
            else:
                dropped += 1

        validated = dict(entry)
        validated["uses_components"] = filtered_components
        validated["constrained_by_decisions"] = filtered_decisions
        validated["related_pitfalls"] = filtered_pitfalls
        blueprint["capabilities"].append(validated)
        accepted += 1

    return accepted, dropped


def _load_capabilities_file(path: str) -> list:
    """Load capabilities JSON from a file path. Returns [] on any error."""
    try:
        text = Path(path).read_text()
    except OSError as e:
        print(f"  Warning: could not read capabilities file {path}: {e}", file=sys.stderr)
        return []

    # Try parsing as a JSON array directly
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Agent may have wrapped array in a dict key
            for v in data.values():
                if isinstance(v, list):
                    return v
        print(f"  Warning: capabilities file {path} did not contain a JSON array", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown/code fences
    result = extract_json_from_text(text)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list):
                return v

    print(f"  Warning: could not parse capabilities JSON from {path}", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 merge.py /path/to/repo [file1.json file2.json ...]", file=sys.stderr)
        print("  Or:  echo '{...}' | python3 merge.py /path/to/repo -", file=sys.stderr)
        print("  Or:  python3 merge.py /path/to/repo --patch incremental.json", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    input_files = sys.argv[2:] if len(sys.argv) > 2 else []

    # --patch mode: merge incremental findings into existing blueprint_raw
    if len(input_files) >= 2 and input_files[0] == "--patch":
        patch_file = input_files[1]
        bp_raw = root / ".archie" / "blueprint_raw.json"
        if not bp_raw.exists():
            print("Error: no existing blueprint_raw.json to patch", file=sys.stderr)
            sys.exit(1)
        try:
            existing = json.loads(bp_raw.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading blueprint_raw.json: {e}", file=sys.stderr)
            sys.exit(1)
        patch_text = Path(patch_file).read_text()
        patch_data = extract_json_from_text(patch_text)
        if not patch_data:
            print("Error: could not extract JSON from patch file", file=sys.stderr)
            sys.exit(1)
        merged = deep_merge(existing, patch_data)
        # Deduplicate components by name (keep latest version)
        comps = merged.get("components", {})
        if isinstance(comps, dict) and "components" in comps:
            seen: dict[str, dict] = {}
            deduped: list[dict] = []
            for c in comps["components"]:
                if not isinstance(c, dict):
                    continue
                name = c.get("name", "")
                if name in seen:
                    # Update existing with new data
                    seen[name].update(c)
                else:
                    seen[name] = c
                    deduped.append(c)
            comps["components"] = deduped
        bp_raw.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
        # Also update blueprint.json
        bp = root / ".archie" / "blueprint.json"
        bp.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
        comp_count = len(merged.get("components", {}).get("components", []) if isinstance(merged.get("components"), dict) else merged.get("components", []))
        print(f"  Patched blueprint_raw.json ({comp_count} components)", file=sys.stderr)
        sys.exit(0)

    outputs: list[dict] = []

    # The last file arg may be a capabilities JSON array (from the Capabilities agent).
    # Detect it by name convention: ends with "capabilities.json" or is exactly
    # /tmp/archie_agent_capabilities.json.  Capabilities are handled separately —
    # they are validated against the merged blueprint, not deep-merged into it.
    capabilities_file: str | None = None
    regular_files = list(input_files)
    if regular_files and not regular_files[-1].startswith("-"):
        candidate = regular_files[-1]
        if "capabilities" in Path(candidate).name:
            capabilities_file = regular_files.pop()

    if not regular_files or regular_files == ["-"]:
        text = sys.stdin.read()
        parsed = extract_json_from_text(text)
        if parsed:
            outputs.append(parsed)
        else:
            print("Error: could not parse JSON from stdin", file=sys.stderr)
            sys.exit(1)
    else:
        for f in regular_files:
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

    # Merge capabilities (validate refs, append to blueprint["capabilities"])
    if capabilities_file:
        caps_input = _load_capabilities_file(capabilities_file)
        accepted, dropped = merge_capabilities(merged, caps_input)
        print(f"Capabilities: {accepted} accepted, {dropped} dropped due to unknown refs")
    else:
        merged.setdefault("capabilities", [])

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
