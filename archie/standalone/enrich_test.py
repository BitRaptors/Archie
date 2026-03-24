#!/usr/bin/env python3
"""Archie enrichment validation — runs without Claude API calls.

Subcommands:
  check    — Verify prompt completeness + skip filtering + DAG consistency
  score    — Score existing enrichment output quality
  children — Verify parent prompts include rich child summaries

Run:
  python3 enrich_test.py check /path/to/repo
  python3 enrich_test.py score /path/to/repo
  python3 enrich_test.py children /path/to/repo

Zero dependencies beyond Python 3.11+ stdlib + enrich.py in same directory.
"""
import io
import json
import sys
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path

# Import from enrich.py (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from enrich import (
    _SKIP_ENRICHMENT_DIRS,
    _is_source_file,
    cmd_prepare,
    cmd_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_prompt(root: Path, folders: list[str], child_summaries: str | None = None) -> str:
    """Capture the stdout output of cmd_prompt."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_prompt(root, folders, child_summaries)
    return buf.getvalue()


def _load_json(path: Path) -> dict | list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Test 1: Prompt completeness
# ---------------------------------------------------------------------------

def test_prompt_includes_all_files(root: Path) -> list[str]:
    """For each folder, verify every source file appears in the prompt."""
    cmd_prepare(root)
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    scan = _load_json(root / ".archie" / "scan.json")

    # Build expected files per folder from scan.json
    expected: dict[str, set[str]] = defaultdict(set)
    for f in scan.get("file_tree", []):
        p = f.get("path", "")
        if "/" in p:
            parent = str(Path(p).parent)
            if _is_source_file(p):
                expected[parent].add(Path(p).name)

    # For each folder in the DAG, generate prompt and check files
    errors = []
    for folder in plan.get("folders", {}):
        prompt = _capture_prompt(root, [folder])
        for fname in expected.get(folder, set()):
            if fname not in prompt:
                errors.append(f"MISSING: {folder}/{fname} not in prompt")
    return errors


# ---------------------------------------------------------------------------
# Test 2: Skip filtering
# ---------------------------------------------------------------------------

def test_skip_dirs_excluded(root: Path) -> list[str]:
    """Verify output/, data/, etc. are not in the DAG."""
    cmd_prepare(root)
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    all_folders = list(plan.get("folders", {}).keys())
    errors = []
    for folder in all_folders:
        parts = folder.split("/")
        for part in parts:
            if part in _SKIP_ENRICHMENT_DIRS:
                errors.append(f"SHOULD BE SKIPPED: {folder} (contains '{part}')")
    return errors


# ---------------------------------------------------------------------------
# Test 3: DAG consistency
# ---------------------------------------------------------------------------

def test_dag_consistency(root: Path) -> list[str]:
    """Verify the DAG is well-formed."""
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    folders = plan.get("folders", {})
    leaves = set(plan.get("leaves", []))
    roots = set(plan.get("roots", []))
    errors = []

    for folder, info in folders.items():
        children = info.get("children", [])

        # Every child must be in the folders map
        for child in children:
            if child not in folders:
                errors.append(f"DANGLING CHILD: {folder} → {child} (not in folders)")

        # Leaves must have no children
        if folder in leaves and children:
            errors.append(f"LEAF HAS CHILDREN: {folder} has {children}")

    # Non-leaf folders must not be in leaves
    for folder, info in folders.items():
        if info.get("children") and folder in leaves:
            errors.append(f"NON-LEAF IN LEAVES: {folder}")

    # Roots must have no qualifying parent in the map
    for r in roots:
        parent = str(Path(r).parent)
        if parent in folders:
            errors.append(f"ROOT HAS PARENT: {r} → parent {parent} is in folders")

    # Every folder must be reachable (either a root or a child of some folder)
    all_children = set()
    for info in folders.values():
        all_children.update(info.get("children", []))
    for folder in folders:
        if folder not in roots and folder not in all_children:
            errors.append(f"ORPHAN: {folder} is neither a root nor a child")

    return errors


# ---------------------------------------------------------------------------
# Test 4: Output quality scoring
# ---------------------------------------------------------------------------

def score_enrichment(root: Path) -> dict:
    """Score enriched CLAUDE.md files. Returns per-folder scores and summary."""
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        return {"error": "No enrichments found"}

    scores = {}
    for json_file in enrichments_dir.iterdir():
        if not json_file.name.endswith(".json"):
            continue
        data = json.loads(json_file.read_text())
        for folder, info in data.items():
            checks = {
                "has_purpose": bool(info.get("purpose")),
                "has_patterns": len(info.get("patterns", [])) > 0,
                "patterns_have_names": all(p.get("name") for p in info.get("patterns", []) if isinstance(p, dict)),
                "patterns_have_examples": any(p.get("example") for p in info.get("patterns", []) if isinstance(p, dict)),
                "has_key_file_guides": len(info.get("key_file_guides", [])) > 0,
                "has_anti_patterns": len(info.get("anti_patterns", [])) > 0,
                "has_common_task": bool(info.get("common_task", {}).get("task")),
                "has_testing": bool(info.get("testing", {}).get("approach")),
                "has_debugging": len(info.get("debugging", [])) > 0,
                "has_decisions": len(info.get("decisions", [])) > 0,
                "has_code_examples": len(info.get("code_examples", [])) > 0,
                "has_key_imports": len(info.get("key_imports", [])) > 0,
            }
            score = sum(checks.values())
            scores[folder] = {"score": f"{score}/12", "checks": checks}

    avg = sum(int(s["score"].split("/")[0]) for s in scores.values()) / max(len(scores), 1)
    return {"average_score": f"{avg:.1f}/12", "folder_count": len(scores), "folders": scores}


# ---------------------------------------------------------------------------
# Test 5: Child summary richness
# ---------------------------------------------------------------------------

def test_child_summaries_rich(root: Path) -> list[str]:
    """Verify parent prompts include child patterns/decisions, not just purpose."""
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        return ["No enrichments found — run enrichment first"]

    plan = _load_json(root / ".archie" / "enrich_batches.json")
    folders = plan.get("folders", {})

    errors = []
    # Check non-leaf folders (those with children)
    for folder, info in folders.items():
        if not info.get("children"):
            continue  # leaf — no children to summarize
        prompt = _capture_prompt(root, [folder], child_summaries=str(enrichments_dir))
        if "**Patterns:**" not in prompt and "**Decisions:**" not in prompt:
            errors.append(f"Folder {folder}: child summaries have no patterns/decisions")
    return errors


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_errors(label: str, errors: list[str]):
    if errors:
        print(f"\n{label}: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"\n{label}: PASS")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:", file=sys.stderr)
        print("  python3 enrich_test.py check /path/to/repo", file=sys.stderr)
        print("  python3 enrich_test.py score /path/to/repo", file=sys.stderr)
        print("  python3 enrich_test.py children /path/to/repo", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]
    root = Path(sys.argv[2]).resolve()

    if subcmd == "check":
        e1 = test_prompt_includes_all_files(root)
        _print_errors("Prompt completeness", e1)
        e2 = test_skip_dirs_excluded(root)
        _print_errors("Skip filtering", e2)
        e3 = test_dag_consistency(root)
        _print_errors("DAG consistency", e3)
        total = len(e1) + len(e2) + len(e3)
        sys.exit(1 if total > 0 else 0)

    elif subcmd == "score":
        result = score_enrichment(root)
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"\nEnrichment quality: {result['average_score']} average across {result['folder_count']} folders\n")
        for folder, data in sorted(result["folders"].items()):
            failed = [k for k, v in data["checks"].items() if not v]
            status = data["score"]
            if failed:
                print(f"  {status}  {folder}  (missing: {', '.join(failed)})")
            else:
                print(f"  {status}  {folder}")

    elif subcmd == "children":
        errors = test_child_summaries_rich(root)
        _print_errors("Child summary richness", errors)
        sys.exit(1 if errors else 0)

    else:
        print(f"Error: unknown subcommand '{subcmd}'", file=sys.stderr)
        sys.exit(1)
