#!/usr/bin/env python3
"""Archie intent layer — AI-generated per-folder CLAUDE.md via bottom-up DAG.

Analyzes source code folder-by-folder (leaves first, then parents with child context)
to generate architectural descriptions: purpose, patterns, anti-patterns, code examples.

Subcommands:
  prepare        — Build folder DAG and processing plan
  next-ready     — Given done folders, return folders ready to process
  suggest-batches — Group ready folders into efficient subagent batches
  prompt         — Generate intent layer prompt for folder(s)
  merge          — Create/patch CLAUDE.md files with generated content

Run:
  python3 intent_layer.py prepare /path/to/repo
  python3 intent_layer.py next-ready /path/to/repo [done1 done2 ...]
  python3 intent_layer.py suggest-batches /path/to/repo [ready1 ready2 ...]
  python3 intent_layer.py prompt /path/to/repo --folder src/lib
  python3 intent_layer.py prompt /path/to/repo --folders src/api/routes,src/api/middleware
  python3 intent_layer.py merge /path/to/repo

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import _load_json  # noqa: E402


def _get_components(blueprint: dict) -> list[dict]:
    """Extract component list from blueprint."""
    raw = blueprint.get("components", {})
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("components", [])
    return []


def _find_component_for_dir(directory: str, components: list[dict]) -> dict | None:
    """Find the best matching component for a directory."""
    best = None
    best_len = -1
    for comp in components:
        loc = (comp.get("location") or comp.get("path") or "").rstrip("/")
        if not loc:
            continue
        if directory == loc or directory.startswith(loc + "/"):
            if len(loc) > best_len:
                best = comp
                best_len = len(loc)
    return best


# ---------------------------------------------------------------------------
# Enrichment-level skip lists
# ---------------------------------------------------------------------------

# Directories to skip during enrichment (generated/data/config-only folders)
_SKIP_ENRICHMENT_DIRS = {
    "output", "data", "dist", "build", ".build", "DerivedData",
    "public", "static", "assets",
    "migrations", "fixtures", "seeds", "__snapshots__",
    "coverage", ".nyc_output",
}

# Extensions to skip when reading file content
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".lock", ".map", ".min.js", ".min.css",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib",
    ".zip", ".tar", ".gz", ".br",
    ".pdf", ".doc", ".docx",
    ".db", ".sqlite", ".sqlite3",
}

MAX_FILE_SIZE = 15_000  # chars — safety valve for monster files only


def _is_source_file(file_path: str) -> bool:
    """Check if a file should be read for enrichment."""
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    _, _, ext = name.rpartition(".")
    if ext and f".{ext}" in _SKIP_EXTENSIONS:
        return False
    return True


def _should_skip_dir(directory: str) -> bool:
    """Check if any path segment matches the enrichment skip list."""
    parts = directory.split("/")
    return any(part in _SKIP_ENRICHMENT_DIRS for part in parts)


# ---------------------------------------------------------------------------
# prepare — build folder DAG
# ---------------------------------------------------------------------------

def cmd_prepare(root: Path):
    """Build folder DAG for bottom-up enrichment."""
    scan = _load_json(root / ".archie" / "scan.json")
    files = scan.get("file_tree", [])

    # Collect directories that have source files
    dir_files: dict[str, list[str]] = defaultdict(list)
    for f in files:
        p = f.get("path", "")
        if "/" in p:
            parent = str(Path(p).parent)
        else:
            continue  # skip root files
        dir_files[parent].append(p)

    # Filter: skip only enrichment-irrelevant directories (build, dist, etc.)
    # Any folder with at least 1 source file qualifies — wherever we code, we
    # need a CLAUDE.md.  Safety valve: depth > 8 with exactly 1 file is noise.
    qualifying = []
    for d, flist in sorted(dir_files.items()):
        if not flist:
            continue
        if _should_skip_dir(d):
            continue
        depth = d.count("/") + 1
        if depth > 8 and len(flist) == 1:
            continue
        qualifying.append(d)

    qualifying_set = set(qualifying)

    # Structural qualification: intermediate directories that have qualifying
    # children but no direct source files still deserve a CLAUDE.md that
    # describes the purpose and responsibility of that layer.
    # Use a work-queue so newly promoted ancestors are also processed.
    promote_queue = list(qualifying)
    while promote_queue:
        d = promote_queue.pop()
        p = Path(d).parent
        while str(p) != "." and str(p) != p.root:
            ancestor = str(p)
            if ancestor in qualifying_set:
                break  # already qualified
            if _should_skip_dir(ancestor):
                break
            # This ancestor has qualifying descendants — promote it
            qualifying.append(ancestor)
            qualifying_set.add(ancestor)
            promote_queue.append(ancestor)
            if ancestor not in dir_files:
                dir_files[ancestor] = []  # structural folder, no direct files
            p = p.parent

    # Calculate folder content sizes from file system
    folder_sizes: dict[str, int] = {}
    for d in qualifying:
        total = 0
        for fp in dir_files[d]:
            if _is_source_file(fp):
                try:
                    total += min((root / fp).stat().st_size, MAX_FILE_SIZE)
                except OSError:
                    pass
        folder_sizes[d] = total

    # Build parent→children map: find closest qualifying ancestor for each folder
    folder_children: dict[str, list[str]] = {d: [] for d in qualifying}
    for d in qualifying:
        # Walk up the path to find the closest qualifying ancestor
        p = Path(d).parent
        while str(p) != "." and str(p) != p.root:
            ancestor = str(p)
            if ancestor in qualifying_set:
                folder_children[ancestor].append(d)
                break
            p = p.parent

    leaves = sorted(d for d in qualifying if not folder_children[d])
    # Roots: folders whose closest qualifying ancestor doesn't exist
    roots = []
    for d in qualifying:
        p = Path(d).parent
        is_root = True
        while str(p) != "." and str(p) != p.root:
            if str(p) in qualifying_set:
                is_root = False
                break
            p = p.parent
        if is_root:
            roots.append(d)
    roots = sorted(roots)

    # Mark structural folders (no direct source files, only qualifying children)
    structural_set = {d for d in qualifying if not dir_files.get(d)}

    plan = {
        "version": 2,
        "folders": {
            d: {
                "children": sorted(folder_children[d]),
                "depth": d.count("/") + 1,
                "size_chars": folder_sizes.get(d, 0),
                **({"structural": True} if d in structural_set else {}),
            }
            for d in qualifying
        },
        "leaves": leaves,
        "roots": roots,
    }

    # Save
    archie_dir = root / ".archie"
    archie_dir.mkdir(exist_ok=True)
    out_path = archie_dir / "enrich_batches.json"
    out_path.write_text(json.dumps(plan, indent=2))

    print(f"Enrichment DAG: {len(qualifying)} folders, {len(leaves)} leaves, {len(roots)} roots", file=sys.stderr)
    print(f"Saved to: {out_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# State tracking — persistent done list
# ---------------------------------------------------------------------------

_STATE_FILE = "enrich_state.json"


def _load_state(root: Path) -> dict:
    """Load enrichment state (done folders, wave count)."""
    state_path = root / ".archie" / _STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"done": [], "wave": 0}


def _save_state(root: Path, state: dict):
    """Save state atomically — write to temp file then rename."""
    archie_dir = root / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    state_path = archie_dir / _STATE_FILE
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, state_path)


def cmd_mark_done(root: Path, folders: list[str]):
    """Mark folders as done in persistent state."""
    state = _load_state(root)
    done_set = set(state.get("done", []))
    added = 0
    for f in folders:
        if f not in done_set:
            done_set.add(f)
            added += 1
    state["done"] = sorted(done_set)
    state["wave"] = state.get("wave", 0) + 1
    _save_state(root, state)
    print(f"Marked {added} folders done (total: {len(done_set)}, wave {state['wave']})", file=sys.stderr)


def cmd_reset_state(root: Path):
    """Reset enrichment state for a fresh run."""
    state_path = root / ".archie" / _STATE_FILE
    if state_path.exists():
        state_path.unlink()
    print("Enrichment state reset", file=sys.stderr)


# ---------------------------------------------------------------------------
# next-ready — DAG scheduler
# ---------------------------------------------------------------------------

def cmd_next_ready(root: Path, done_folders: list[str]):
    """Given completed folders, return folders whose children are ALL done.

    If no done_folders are passed as CLI args, reads from persistent state file.
    """
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    folders = plan.get("folders", {})

    # Use persistent state if no explicit done list
    if not done_folders:
        state = _load_state(root)
        done_folders = state.get("done", [])

    done_set = set(done_folders)

    ready = []
    for folder, info in folders.items():
        if folder in done_set:
            continue
        children = info.get("children", [])
        if all(c in done_set for c in children):
            ready.append(folder)

    print(json.dumps(sorted(ready)))


# ---------------------------------------------------------------------------
# suggest-batches — group ready folders for parallel subagent calls
# ---------------------------------------------------------------------------

BATCH_TOKEN_BUDGET = 100_000  # ~400KB chars, conservative for 200K Sonnet context
CHARS_PER_TOKEN = 4
MAX_FOLDERS_PER_BATCH = 5


def cmd_suggest_batches(root: Path, ready_folders: list[str]):
    """Group ready folders into efficient batches for parallel subagent calls."""
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    folders_info = plan.get("folders", {})

    # Group by parent directory (siblings batch well together)
    by_parent: dict[str, list[str]] = defaultdict(list)
    for f in ready_folders:
        parent = str(Path(f).parent)
        by_parent[parent].append(f)

    batches = []
    for parent, siblings in sorted(by_parent.items()):
        current_batch: list[str] = []
        current_size = 0
        for folder in sorted(siblings):
            folder_size = folders_info.get(folder, {}).get("size_chars", 0)
            at_budget = (current_size + folder_size) / CHARS_PER_TOKEN > BATCH_TOKEN_BUDGET
            at_max = len(current_batch) >= MAX_FOLDERS_PER_BATCH
            if current_batch and (at_budget or at_max):
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append(folder)
            current_size += folder_size
        if current_batch:
            batches.append(current_batch)

    result = [{"id": f"w{i}", "folders": b} for i, b in enumerate(batches)]
    print(json.dumps(result))


# ---------------------------------------------------------------------------
# prompt — generate enrichment prompt for folder(s)
# ---------------------------------------------------------------------------

def _read_file_content(root: Path, rel_path: str) -> str:
    """Read a source file. Truncates only if over MAX_FILE_SIZE."""
    try:
        full = root / rel_path
        if not full.exists() or not full.is_file():
            return ""
        text = full.read_text(errors="replace")
        if len(text) > MAX_FILE_SIZE:
            text = text[:MAX_FILE_SIZE] + "\n... (truncated)"
        return text
    except (OSError, UnicodeDecodeError):
        return ""


def _inject_child_summaries(prompt_parts: list[str], folder: str, child_summaries_dir: str, plan: dict):
    """Inject rich child summaries into the prompt for a folder."""
    child_dir = Path(child_summaries_dir)
    if not child_dir.is_dir():
        return

    # Get this folder's children from the DAG
    folder_info = plan.get("folders", {}).get(folder, {})
    child_folders = set(folder_info.get("children", []))
    if not child_folders:
        return

    # Scan enrichment files for matching children
    for child_file in sorted(child_dir.iterdir()):
        if not child_file.name.endswith(".json"):
            continue
        try:
            child_data = json.loads(child_file.read_text())
            for child_path, child_info in child_data.items():
                if child_path not in child_folders:
                    continue
                prompt_parts.append(f"### Child: `{child_path}`")
                if child_info.get("purpose"):
                    prompt_parts.append(f"**Purpose:** {child_info['purpose']}")
                patterns = child_info.get("patterns", [])
                if patterns:
                    names = [p["name"] for p in patterns if isinstance(p, dict) and p.get("name")]
                    if names:
                        prompt_parts.append(f"**Patterns:** {', '.join(names)}")
                decisions = child_info.get("decisions", [])
                if decisions:
                    decs = [d["decision"] for d in decisions if isinstance(d, dict) and d.get("decision")]
                    if decs:
                        prompt_parts.append(f"**Decisions:** {'; '.join(decs)}")
                anti = child_info.get("anti_patterns", [])
                if anti:
                    prompt_parts.append(f"**Anti-patterns:** {'; '.join(anti[:5])}")
                guides = child_info.get("key_file_guides", [])
                if guides:
                    files = [g["file"] for g in guides if isinstance(g, dict) and g.get("file")]
                    if files:
                        prompt_parts.append(f"**Key files:** {', '.join(files)}")
                prompt_parts.append("")
        except (json.JSONDecodeError, OSError):
            pass


def cmd_prompt(root: Path, folders: list[str], child_summaries_dir: str | None = None):
    """Generate enrichment prompt for one or more folders, output to stdout."""
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    blueprint = _load_json(root / ".archie" / "blueprint.json")
    scan = _load_json(root / ".archie" / "scan.json")
    components = _get_components(blueprint)

    # Build file index
    files_by_dir: dict[str, list[str]] = defaultdict(list)
    for f in scan.get("file_tree", []):
        p = f.get("path", "")
        if "/" in p:
            parent = str(Path(p).parent)
            files_by_dir[parent].append(p)

    # Build prompt
    prompt_parts = []
    prompt_parts.append("## Folder Architecture Description")
    prompt_parts.append("")
    prompt_parts.append("Describe each folder's architecture so an AI coding agent can write correct code here without reading every file first.")
    prompt_parts.append("Answer: What is this folder? What does it contain? How is code structured here? What patterns must new code follow? What would break if done wrong?")
    prompt_parts.append("")
    prompt_parts.append("Be specific: reference actual function names, actual file names, actual patterns you see in the code.")
    prompt_parts.append("")
    prompt_parts.append("For each folder, return a JSON object with these fields:")
    prompt_parts.append("- purpose: 1-2 sentence summary — what this folder does, its role in the system, its primary constraint")
    prompt_parts.append("- contains: 1-2 sentences — what kinds of things are in here and how they relate (e.g. '5 screen ViewModels following MVVM, each paired with a Fragment', 'API DTOs for the weather service, all implementing Serializable')")
    prompt_parts.append("- patterns: list of {name, description, example} — architectural patterns that MUST be followed when adding code here. Each mechanically verifiable by a code reviewer.")
    prompt_parts.append("- key_file_guides: list of {file, role, watch_for} — per-file role and foot-guns")
    prompt_parts.append("- anti_patterns: list of strings — constraints: things that would break the architecture if done here")
    prompt_parts.append("- common_task: {task, steps} — how to add/modify code that fits this folder's patterns")
    prompt_parts.append("- code_examples: list of {scenario, code} — REQUIRED, 1-3 copy-pasteable code snippets showing the PATTERN this folder uses. Use actual imports from this codebase.")
    prompt_parts.append("- decisions: list of {decision, rationale} — why the code is structured this way")
    prompt_parts.append("- key_imports: list of strings — the public API of this folder: imports that other folders use from here")
    prompt_parts.append("")
    prompt_parts.append("## Line Budget")
    prompt_parts.append("")
    prompt_parts.append("~200 lines per folder. Density over completeness. One precise sentence beats three vague ones.")
    prompt_parts.append("Line costs: purpose=1, contains=2, each pattern=2, each key_file row=1, each step=1, each code_example=5+lines, each list item=1.")
    prompt_parts.append("Prioritize: purpose > contains > patterns > key_files > code_examples > common_task > anti_patterns > decisions.")
    prompt_parts.append("Omit any field where you have nothing code-grounded to say — empty arrays are fine.")
    prompt_parts.append("")
    prompt_parts.append("## Rules")
    prompt_parts.append("")
    prompt_parts.append("1. Derive patterns from ACTUAL code — not generic best practices")
    prompt_parts.append("2. Every pattern must be mechanically verifiable by a code reviewer")
    prompt_parts.append("3. Reference ONLY files provided below. If you cannot ground a claim in code you see, skip it")
    prompt_parts.append("4. If child folder summaries are provided, add cross-cutting insights — don't repeat what children cover")
    prompt_parts.append("5. For code_examples: use the actual import paths and naming conventions from this codebase")
    prompt_parts.append("6. For key_imports: list only the exports that other parts of the codebase actually consume")
    prompt_parts.append("")
    prompt_parts.append("### Structural (no-code) folders")
    prompt_parts.append("")
    prompt_parts.append("Some folders have no direct source files — they are organisational folders whose children contain the actual code.")
    prompt_parts.append("For these, describe the folder's **role and responsibility in the architecture**: what domain/layer it owns, how its children relate, and what a developer should know before navigating into it.")
    prompt_parts.append("Do NOT just list children. Synthesise: 'sdk is the public API surface for weather data — its sub-packages split by transport (HTTP, gRPC) and domain (forecast, alerts)'.")
    prompt_parts.append("")
    prompt_parts.append("Return a JSON object with folder paths as keys:")
    prompt_parts.append('{"folder/path": {purpose, patterns, key_file_guides, ...}, ...}')
    prompt_parts.append("")
    prompt_parts.append("---")
    prompt_parts.append("")

    # Detect which folders are structural
    plan_folders = plan.get("folders", {})

    for folder in folders:
        is_structural = plan_folders.get(folder, {}).get("structural", False)
        label = f"## Folder: {folder}"
        if is_structural:
            label += "  *(structural — no direct source files)*"
        prompt_parts.append(label)
        prompt_parts.append("")

        # Component context
        comp = _find_component_for_dir(folder, components)
        if comp:
            prompt_parts.append(f"**Component:** {comp.get('name', '')} — {comp.get('responsibility', '')}")
            deps = comp.get("depends_on", [])
            if deps:
                prompt_parts.append(f"**Depends on:** {', '.join(deps)}")
            exposes = comp.get("exposes_to", [])
            if exposes:
                prompt_parts.append(f"**Exposes to:** {', '.join(exposes)}")
            # Key interfaces from blueprint
            interfaces = comp.get("key_interfaces", [])
            if interfaces:
                iface_parts = []
                for iface in interfaces:
                    if isinstance(iface, dict) and iface.get("name"):
                        methods = iface.get("methods", [])
                        desc = iface.get("description", "")
                        entry = f"{iface['name']}"
                        if desc:
                            entry += f": {desc}"
                        if methods:
                            entry += f" — methods: {', '.join(methods)}"
                        iface_parts.append(entry)
                if iface_parts:
                    prompt_parts.append(f"**Key Interfaces:** {'; '.join(iface_parts)}")
            prompt_parts.append("")

        # Import graph context
        import_graph = scan.get("import_graph", {})
        if import_graph:
            imports_from: set[str] = set()
            imported_by: set[str] = set()
            for file_path, imports in import_graph.items():
                file_dir = str(Path(file_path).parent)
                is_in_dir = (file_dir == folder or file_dir.startswith(folder + "/"))
                if is_in_dir:
                    for imp in imports:
                        if "/" in imp or "." in imp:
                            parts = imp.replace(".", "/").split("/")
                            if len(parts) >= 2:
                                imp_dir = "/".join(parts[:2])
                                if not imp_dir.startswith(folder):
                                    imports_from.add(imp_dir)
                else:
                    for imp in imports:
                        if folder in imp.replace(".", "/"):
                            imported_by.add(file_dir)
            if imports_from:
                prompt_parts.append(f"**Imports from:** {', '.join(sorted(imports_from))}")
            if imported_by:
                prompt_parts.append(f"**Imported by:** {', '.join(sorted(imported_by))}")

        # Child summaries — DAG-aware: only inject actual children
        if child_summaries_dir:
            _inject_child_summaries(prompt_parts, folder, child_summaries_dir, plan)

        if is_structural:
            # Structural folder: list children only, no source files to read
            children = plan_folders.get(folder, {}).get("children", [])
            if children:
                prompt_parts.append(f"**Sub-folders:** {', '.join(sorted(children))}")
            prompt_parts.append("")
            prompt_parts.append("*This folder contains no direct source files. Describe its architectural role based on its children's summaries above.*")
            prompt_parts.append("")
        else:
            # Read ALL source files
            folder_files = files_by_dir.get(folder, [])
            source_files = [fp for fp in sorted(folder_files) if _is_source_file(fp)]

            prompt_parts.append(f"**All files:** {', '.join(Path(f).name for f in sorted(folder_files))}")
            prompt_parts.append("")

            for fp in source_files:
                content = _read_file_content(root, fp)
                if content:
                    fname = fp.rsplit("/", 1)[-1] if "/" in fp else fp
                    prompt_parts.append(f"### {fname}")
                    prompt_parts.append(f"```")
                    prompt_parts.append(content)
                    prompt_parts.append("```")
                    prompt_parts.append("")

        prompt_parts.append("---")
        prompt_parts.append("")

    print("\n".join(prompt_parts))


# ---------------------------------------------------------------------------
# merge — patch CLAUDE.md files with enrichment data
# ---------------------------------------------------------------------------

_AI_START = "<!-- archie:ai-start -->"
_AI_END = "<!-- archie:ai-end -->"


def _render_enrichment_section(data: dict) -> str:
    """Render enrichment JSON into markdown sections."""
    lines = []
    lines.append(_AI_START)
    lines.append("")

    # Purpose
    purpose = data.get("purpose", "")
    if purpose:
        lines.append(f"> {purpose}")
        lines.append("")

    # Contains
    contains = data.get("contains", "")
    if contains:
        lines.append(f"**Contains:** {contains}")
        lines.append("")

    # Patterns
    patterns = data.get("patterns", [])
    if patterns:
        lines.append("## Patterns")
        lines.append("")
        for p in patterns:
            if isinstance(p, dict):
                lines.append(f"**{p.get('name', '')}** — {p.get('description', '')}")
                ex = p.get("example", "")
                if ex:
                    lines.append(f"  - Example: `{ex}`")
            elif isinstance(p, str):
                lines.append(f"- {p}")
        lines.append("")

    # Key File Guides
    guides = data.get("key_file_guides", [])
    if guides:
        lines.append("## Key Files")
        lines.append("")
        lines.append("| File | Role | Watch For |")
        lines.append("|------|------|-----------|")
        for g in guides:
            if isinstance(g, dict):
                lines.append(f"| `{g.get('file', '')}` | {g.get('role', '')} | {g.get('watch_for', '')} |")
        lines.append("")

    # Anti-Patterns
    anti = data.get("anti_patterns", [])
    if anti:
        lines.append("## Anti-Patterns")
        lines.append("")
        for a in anti:
            lines.append(f"- {a}")
        lines.append("")

    # Common Task
    task = data.get("common_task", {})
    if isinstance(task, dict) and task.get("task"):
        lines.append("## Common Task")
        lines.append("")
        lines.append(f"**{task['task']}**")
        steps = task.get("steps", [])
        if steps:
            for i, s in enumerate(steps, 1):
                lines.append(f"{i}. {s}")
        lines.append("")

    # Decisions
    decisions = data.get("decisions", [])
    if decisions:
        lines.append("## Decisions")
        lines.append("")
        for dec in decisions:
            if isinstance(dec, dict):
                lines.append(f"- **{dec.get('decision', '')}** — {dec.get('rationale', '')}")
            elif isinstance(dec, str):
                lines.append(f"- {dec}")
        lines.append("")

    # Code Examples
    examples = data.get("code_examples", [])
    if examples:
        lines.append("## Code Examples")
        lines.append("")
        for ex in examples:
            if isinstance(ex, dict):
                lines.append(f"### {ex.get('scenario', '')}")
                lines.append("")
                code = ex.get("code", "")
                if code:
                    lines.append("```")
                    lines.append(code)
                    lines.append("```")
                lines.append("")

    # Key Imports
    imports = data.get("key_imports", [])
    if imports:
        lines.append("## Key Imports")
        lines.append("")
        for imp in imports:
            lines.append(f"- `{imp}`")
        lines.append("")

    lines.append(_AI_END)
    return "\n".join(lines)


def _extract_enrichment_json(text: str) -> dict | None:
    """Extract enrichment JSON from agent output text.

    Handles:
    - Plain JSON
    - JSON inside code fences
    - Claude Code NDJSON conversation envelopes
    - Multiple JSON blocks (one per folder) that need merging
    - Common AI escape issues (\\$, nested quotes)
    """
    def _fix_escapes(s: str) -> str:
        return s.replace("\\$", "$")

    def _try_parse(s: str) -> dict | None:
        for attempt in (s, _fix_escapes(s)):
            try:
                obj = json.loads(attempt)
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    # 1. Try direct parse
    result = _try_parse(text)
    if result is not None:
        return result

    # 2. Try unwrapping NDJSON conversation envelope
    if text.lstrip().startswith(("{\"parentUuid\"", "{\"isSidechain\"")):
        content_parts = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            for block in record.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    content_parts.append(block["text"])
        if content_parts:
            text = "\n".join(content_parts)
            result = _try_parse(text)
            if result is not None:
                return result

    # 3. Extract from code fences — merge multiple blocks
    fences = list(re.finditer(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL))
    if fences:
        merged = {}
        for match in fences:
            block = match.group(1).strip()
            if block.startswith("{"):
                parsed = _try_parse(block)
                if parsed:
                    merged.update(parsed)
        if merged:
            return merged

    # 4. String-aware brace-matching — find all top-level JSON objects and merge
    merged = {}
    i = 0
    limit = len(text)
    attempts = 0
    while i < limit and attempts < 50:
        if text[i] != '{':
            i += 1
            continue
        attempts += 1
        # Walk forward, skip braces inside quoted strings
        depth = 0
        j = i
        in_string = False
        while j < limit:
            ch = text[j]
            if in_string:
                if ch == '\\':
                    j += 2
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
                        parsed = _try_parse(text[i:j + 1])
                        if parsed:
                            if "parentUuid" not in parsed and "isSidechain" not in parsed:
                                merged.update(parsed)
                        break
            j += 1
        i = j + 1 if j < limit else limit

    return merged if merged else None


def cmd_save_enrichment(root: Path, name: str, input_file: str):
    """Extract enrichment JSON from agent output and save to enrichments dir.

    Also marks the extracted folders as done in the state file.
    """
    enrichments_dir = root / ".archie" / "enrichments"
    enrichments_dir.mkdir(parents=True, exist_ok=True)

    text = Path(input_file).read_text() if input_file != "-" else sys.stdin.read()
    data = _extract_enrichment_json(text)

    if not data:
        print(f"Error: could not extract JSON from {input_file}", file=sys.stderr)
        sys.exit(1)

    # Filter: only keep entries that look like folder enrichments (have 'purpose' key)
    clean = {}
    for key, val in data.items():
        if isinstance(val, dict) and ("purpose" in val or "patterns" in val or "contains" in val):
            clean[key] = val

    if not clean:
        # Fallback: keep all dict entries
        clean = {k: v for k, v in data.items() if isinstance(v, dict)}

    out_path = enrichments_dir / f"{name}.json"
    out_path.write_text(json.dumps(clean, indent=2))
    print(f"Saved {len(clean)} folders to {out_path}", file=sys.stderr)

    # Mark these folders as done
    cmd_mark_done(root, list(clean.keys()))

    return clean


def cmd_merge(root: Path):
    """Patch existing CLAUDE.md files with enrichment data."""
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        print("Error: .archie/enrichments/ not found. Run enrichment first.", file=sys.stderr)
        sys.exit(1)

    # Load all enrichment JSONs (use robust extraction in case of raw agent output)
    all_enrichments: dict[str, dict] = {}
    for json_file in sorted(enrichments_dir.iterdir()):
        if not json_file.name.endswith(".json"):
            continue
        try:
            text = json_file.read_text()
            data = _extract_enrichment_json(text)
            if data:
                all_enrichments.update(data)
            else:
                print(f"  Warning: could not extract JSON from {json_file}", file=sys.stderr)
        except OSError as e:
            print(f"  Warning: could not read {json_file}: {e}", file=sys.stderr)

    if not all_enrichments:
        print("No enrichment data found.", file=sys.stderr)
        sys.exit(1)

    patched = 0
    created = 0
    for folder_path, enrichment_data in sorted(all_enrichments.items()):
        claude_md_path = root / folder_path / "CLAUDE.md"
        ai_section = _render_enrichment_section(enrichment_data)

        if claude_md_path.exists():
            content = claude_md_path.read_text()
            # Replace existing AI section or append
            if _AI_START in content and _AI_END in content:
                # Replace between markers
                pattern = re.compile(
                    re.escape(_AI_START) + r".*?" + re.escape(_AI_END),
                    re.DOTALL,
                )
                content = pattern.sub(ai_section, content)
            else:
                # Insert before the footer
                footer = "---\n*Auto-generated by Archie.*"
                if footer in content:
                    content = content.replace(footer, ai_section + "\n\n" + footer)
                else:
                    content = content.rstrip() + "\n\n" + ai_section + "\n"
            claude_md_path.write_text(content)
            patched += 1
        else:
            # Create minimal CLAUDE.md with AI section
            dir_name = folder_path.rsplit("/", 1)[-1] if "/" in folder_path else folder_path
            content = f"# {dir_name}\n\n{ai_section}\n\n---\n*Auto-generated by Archie.*\n"
            claude_md_path.parent.mkdir(parents=True, exist_ok=True)
            claude_md_path.write_text(content)
            created += 1

    print(f"Enrichment merge: {patched} patched, {created} created", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:", file=sys.stderr)
        print("  python3 intent_layer.py prepare /path/to/repo", file=sys.stderr)
        print("  python3 intent_layer.py next-ready /path/to/repo [done1 done2 ...]", file=sys.stderr)
        print("  python3 intent_layer.py suggest-batches /path/to/repo [ready1 ready2 ...]", file=sys.stderr)
        print("  python3 intent_layer.py prompt /path/to/repo --folder <path>", file=sys.stderr)
        print("  python3 intent_layer.py prompt /path/to/repo --folders <p1>,<p2>", file=sys.stderr)
        print("  python3 intent_layer.py save-enrichment /path/to/repo <name> <input.json>", file=sys.stderr)
        print("  python3 intent_layer.py mark-done /path/to/repo <folder1> [folder2 ...]", file=sys.stderr)
        print("  python3 intent_layer.py reset-state /path/to/repo", file=sys.stderr)
        print("  python3 intent_layer.py merge /path/to/repo", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]
    root = Path(sys.argv[2]).resolve()

    if subcmd == "prepare":
        cmd_prepare(root)
    elif subcmd == "next-ready":
        done = sys.argv[3:] if len(sys.argv) > 3 else []
        cmd_next_ready(root, done)
    elif subcmd == "suggest-batches":
        ready = sys.argv[3:] if len(sys.argv) > 3 else []
        cmd_suggest_batches(root, ready)
    elif subcmd == "save-enrichment":
        if len(sys.argv) < 5:
            print("Usage: save-enrichment /path/to/repo <name> <input.json|->", file=sys.stderr)
            sys.exit(1)
        cmd_save_enrichment(root, sys.argv[3], sys.argv[4])
    elif subcmd == "mark-done":
        folders = sys.argv[3:] if len(sys.argv) > 3 else []
        cmd_mark_done(root, folders)
    elif subcmd == "reset-state":
        cmd_reset_state(root)
    elif subcmd == "prompt":
        # Parse --folder, --folders, or positional batch_id
        child_dir = None
        if "--child-summaries" in sys.argv:
            idx = sys.argv.index("--child-summaries")
            if idx + 1 < len(sys.argv):
                child_dir = sys.argv[idx + 1]

        if "--folder" in sys.argv:
            idx = sys.argv.index("--folder")
            if idx + 1 < len(sys.argv):
                cmd_prompt(root, [sys.argv[idx + 1]], child_dir)
            else:
                print("Error: --folder requires a path", file=sys.stderr)
                sys.exit(1)
        elif "--folders" in sys.argv:
            idx = sys.argv.index("--folders")
            if idx + 1 < len(sys.argv):
                folder_list = sys.argv[idx + 1].split(",")
                cmd_prompt(root, folder_list, child_dir)
            else:
                print("Error: --folders requires comma-separated paths", file=sys.stderr)
                sys.exit(1)
        elif len(sys.argv) > 3 and not sys.argv[3].startswith("--"):
            # Legacy batch_id support — look up in suggest-batches output or v1 format
            batch_id = sys.argv[3]
            plan = _load_json(root / ".archie" / "enrich_batches.json")
            # v1 format (depth_levels)
            batch = None
            for dl in plan.get("depth_levels", []):
                for b in dl.get("batches", []):
                    if b["id"] == batch_id:
                        batch = b
                        break
                if batch:
                    break
            if batch:
                cmd_prompt(root, batch["folders"], child_dir)
            else:
                print(f"Error: batch '{batch_id}' not found", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: prompt requires --folder, --folders, or batch_id", file=sys.stderr)
            sys.exit(1)
    elif subcmd == "merge":
        cmd_merge(root)
    else:
        print(f"Error: unknown subcommand '{subcmd}'", file=sys.stderr)
        sys.exit(1)
