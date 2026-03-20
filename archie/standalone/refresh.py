#!/usr/bin/env python3
"""Archie standalone refresh — compares current state to blueprint, reports changes.

Run: python3 refresh.py /path/to/repo
Output: JSON to stdout with change summary

Zero dependencies beyond Python 3.11+ stdlib.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", ".turbo", ".parcel-cache",
    "vendor", "Pods", ".gradle", ".idea", ".vscode",
    ".archie", ".claude", ".cursor",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".lock", ".sum",
}

ALLOWED_DOTFILES = {".env.example", ".gitignore", ".dockerignore", ".editorconfig"}


def current_hashes(root: Path) -> dict[str, str]:
    """Hash all source files in the repo."""
    hashes = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue
            if fname.startswith(".") and fname not in ALLOWED_DOTFILES:
                continue
            full = Path(dirpath) / fname
            try:
                content = full.read_bytes()
                rel = str(full.relative_to(root))
                hashes[rel] = hashlib.sha256(content).hexdigest()
            except OSError:
                pass
    return hashes


def load_old_hashes(root: Path) -> dict[str, str]:
    """Load file hashes from the last scan or blueprint."""
    # Try scan.json first (most recent)
    scan_path = root / ".archie" / "scan.json"
    if scan_path.exists():
        try:
            data = json.loads(scan_path.read_text())
            return data.get("file_hashes", {})
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to blueprint.json
    bp_path = root / ".archie" / "blueprint.json"
    if bp_path.exists():
        try:
            data = json.loads(bp_path.read_text())
            return data.get("_file_hashes", {})
        except (json.JSONDecodeError, OSError):
            pass

    return {}


def compute_changes(old: dict[str, str], new: dict[str, str]) -> dict:
    """Compare old and new file hashes."""
    old_files = set(old.keys())
    new_files = set(new.keys())

    added = sorted(new_files - old_files)
    deleted = sorted(old_files - new_files)
    modified = sorted(f for f in old_files & new_files if old[f] != new[f])

    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "total_changed": len(added) + len(deleted) + len(modified),
    }


def generate_refresh_prompt(changes: dict, root: Path) -> str:
    """Generate a targeted subagent prompt for changed files."""
    lines = [
        "You are re-analyzing a codebase after changes. Focus ONLY on the changed files.",
        "",
        "## Changes detected",
        "",
    ]

    if changes["added"]:
        lines.append(f"### New files ({len(changes['added'])})")
        for f in changes["added"]:
            lines.append(f"  - {f}")
        lines.append("")

    if changes["deleted"]:
        lines.append(f"### Deleted files ({len(changes['deleted'])})")
        for f in changes["deleted"]:
            lines.append(f"  - {f}")
        lines.append("")

    if changes["modified"]:
        lines.append(f"### Modified files ({len(changes['modified'])})")
        for f in changes["modified"]:
            lines.append(f"  - {f}")
        lines.append("")

    lines.extend([
        "## Task",
        "",
        "Read the changed files (new + modified) and update the relevant blueprint sections.",
        "Return a JSON object with only the sections that need updating.",
        "Focus on:",
        "- New components introduced by added files",
        "- Changed architecture rules or patterns",
        "- New dependencies or framework signals",
        "- Updated file placement rules if directory structure changed",
        "",
        "Existing blueprint is at .archie/blueprint.json — read it for context.",
        "",
        "Return ONLY valid JSON with the updated sections.",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 refresh.py /path/to/repo [--deep]", file=sys.stderr)
        sys.exit(1)

    repo = sys.argv[1]
    deep = "--deep" in sys.argv
    root = Path(repo).resolve()

    if not root.is_dir():
        print(f"Error: {repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Compute changes
    old = load_old_hashes(root)
    new = current_hashes(root)
    changes = compute_changes(old, new)

    # Print summary
    print(f"Changes: {changes['total_changed']} total", file=sys.stderr)
    print(f"  Added:    {len(changes['added'])}", file=sys.stderr)
    print(f"  Deleted:  {len(changes['deleted'])}", file=sys.stderr)
    print(f"  Modified: {len(changes['modified'])}", file=sys.stderr)

    if changes["total_changed"] == 0:
        print("No changes since last scan.", file=sys.stderr)

    # Re-run scanner to update scan.json
    scanner_path = root / ".archie" / "scanner.py"
    if not scanner_path.exists():
        # Try the standalone location
        scanner_path = Path(__file__).parent / "scanner.py"

    if scanner_path.exists():
        import subprocess
        subprocess.run(
            [sys.executable, str(scanner_path), str(root)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Updated .archie/scan.json", file=sys.stderr)

    # Deep mode: generate targeted prompt
    if deep and changes["total_changed"] > 0:
        prompt = generate_refresh_prompt(changes, root)
        prompt_path = root / ".archie" / "refresh_prompt.md"
        prompt_path.write_text(prompt)
        print(f"Saved refresh prompt to .archie/refresh_prompt.md", file=sys.stderr)

    # Output JSON
    json.dump(changes, sys.stdout, indent=2)
