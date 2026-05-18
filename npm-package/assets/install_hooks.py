#!/usr/bin/env python3
"""Archie hook installer for Claude Code — backwards-compat entry point.

Modern installs go through ClaudeConnector.install_hook via the Python install
loop (archie/install.py). This script is preserved for legacy callers (older
archie.mjs versions) and for manual debugging. It copies hook scripts from the
canonical archie/assets/hook_scripts/ directory into .claude/hooks/ and merges
hook bindings into .claude/settings.local.json.

Run: python3 install_hooks.py /path/to/repo
Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import shutil
import stat
import sys
from pathlib import Path


def _find_canonical_hook_dir() -> Path:
    """Locate the canonical hook scripts directory across deployment contexts.

    - Source repo: archie/standalone/install_hooks.py → archie/assets/hook_scripts/
    - pip wheel:   same package layout (package_data ships archie/assets/)
    - npm install: <project>/.archie/install_hooks.py + <project>/.archie/hooks/
                   (Python install loop and archie.mjs both write here)
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "assets" / "hook_scripts",  # source repo / pip wheel
        here / "hooks",                            # npm-deployed: .archie/install_hooks.py + .archie/hooks/
    ]
    for c in candidates:
        if c.is_dir():
            return c
    raise FileNotFoundError(
        "Canonical hook scripts directory not found. Searched: "
        + ", ".join(str(c) for c in candidates)
    )


CANONICAL_HOOK_DIR = _find_canonical_hook_dir()

# Map hook filename → (settings.local.json event bucket, matcher).
# Must stay in sync with archie/manifest_data.HOOKS so legacy callers wire the
# same hook surface as the connector-based path.
HOOK_BINDINGS = [
    ("pre-validate.sh",       "PreToolUse",       "Write|Edit|MultiEdit"),
    ("pre-commit-review.sh",  "PreToolUse",       "Bash"),
    ("blueprint-nudge.sh",    "PreToolUse",       "Glob|Grep"),
    ("post-plan-review.sh",   "PostToolUse",      "ExitPlanMode"),
    ("post-lint.sh",          "PostToolUse",      "Write|Edit|MultiEdit"),
    ("pre-turn.sh",           "UserPromptSubmit", ""),
]

ARCHIE_PERMISSIONS = [
    "Bash(python3 .archie/*.py *)", "Bash(python3 .archie/*.py)", "Bash(python3 -c *)",
    "Bash(git *)", "Bash(test *)", "Bash(cp *)", "Bash(ls *)", "Bash(wc *)",
    "Bash(cat *)", "Bash(echo *)", "Bash(for *)", "Bash(mkdir *)", "Bash(date *)",
    "Bash(sort *)", "Bash(head *)",
    "Bash(rm -f /tmp/archie_*)", "Bash(rm -f .archie/health.json)",
    "Write(//tmp/archie_*)", "Read(//tmp/archie_*)",
    "Read(.archie/*)", "Read(.archie/**)",
    "Write(.archie/*)", "Write(.archie/**)",
    "Edit(.archie/*)", "Edit(.archie/**)",
    "Read(**)",
    "Write(**/CLAUDE.md)", "Edit(**/CLAUDE.md)",
    "Agent(*)",
]


def _add_hook(hooks_list: list, matcher: str, command: str) -> None:
    needle = matcher or "*"
    for entry in hooks_list:
        if entry.get("matcher") in (matcher, needle):
            for h in entry.get("hooks", []):
                if h.get("command") == command:
                    return
    hooks_list.append({
        "matcher": needle if matcher == "" else matcher,
        "hooks": [{"type": "command", "command": command}],
    })


def install(project_root: Path) -> None:
    hook_dir = project_root / ".claude" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)

    # Copy hook scripts from the canonical location.
    for script_name, _event, _matcher in HOOK_BINDINGS:
        src = CANONICAL_HOOK_DIR / script_name
        if not src.exists():
            print(f"[install_hooks] missing canonical script: {src}", file=sys.stderr)
            continue
        dest = hook_dir / script_name
        shutil.copyfile(src, dest)
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Merge into .claude/settings.local.json (preserves user content).
    settings_path = project_root / ".claude" / "settings.local.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            settings = {}

    hooks = settings.setdefault("hooks", {})
    for script_name, event_key, matcher in HOOK_BINDINGS:
        bucket = hooks.setdefault(event_key, [])
        _add_hook(bucket, matcher, f".claude/hooks/{script_name}")

    perms = settings.setdefault("permissions", {})
    allow = set(perms.get("allow", []))
    for p in ARCHIE_PERMISSIONS:
        allow.add(p)
    perms["allow"] = sorted(allow)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 install_hooks.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    install(root)
    print(f"Installed Claude hooks under {root}/.claude/", file=sys.stderr)
