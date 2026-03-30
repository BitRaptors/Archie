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
            if isinstance(block, dict) and block.get("type") == "text":
                content_parts.append(block["text"])
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
