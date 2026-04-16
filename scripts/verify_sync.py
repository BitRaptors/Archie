#!/usr/bin/env python3
"""Verify that archie/standalone/, npm-package/assets/, and archie.mjs are in sync.

Run: python3 scripts/verify_sync.py

Checks:
1. Every .py in archie/standalone/ has a copy in npm-package/assets/ (and vice versa)
2. Every .md in .claude/commands/ has a copy in npm-package/assets/ (and vice versa)
3. archie.mjs script list matches the .py files in npm-package/assets/
4. archie.mjs command list matches the .md files in npm-package/assets/
5. File contents match between canonical and asset copies

Exit code 0 = all OK, 1 = mismatches found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STANDALONE = ROOT / "archie" / "standalone"
ASSETS = ROOT / "npm-package" / "assets"
COMMANDS = ROOT / ".claude" / "commands"
SHARED_COMMANDS = COMMANDS / "_shared"
SHARED_ASSETS = ASSETS / "_shared"
ARCHIE_MJS = ROOT / "npm-package" / "bin" / "archie.mjs"

SKIP_FILES = {"__init__.py", "__pycache__"}


def get_archie_mjs_lists() -> tuple[set[str], set[str]]:
    """Parse archie.mjs to extract the script and command copy lists."""
    text = ARCHIE_MJS.read_text()

    # Extract script list: for (const script of ["scanner.py", ...]) {
    m = re.search(r'const script of \[(.*?)\]', text, re.DOTALL)
    scripts = set(re.findall(r'"([^"]+\.py)"', m.group(1))) if m else set()

    # Extract command list: for (const cmd of ["archie-init.md", ...]) {
    m = re.search(r'const cmd of \[(.*?)\]', text, re.DOTALL)
    commands = set(re.findall(r'"([^"]+\.md)"', m.group(1))) if m else set()

    return scripts, commands


def main():
    errors = []

    # 1. Get what archie.mjs thinks it should copy
    mjs_scripts, mjs_commands = get_archie_mjs_lists()

    # 2. Get actual files
    standalone_pys = {f.name for f in STANDALONE.glob("*.py") if f.name not in SKIP_FILES}
    asset_pys = {f.name for f in ASSETS.glob("*.py")}
    asset_mds = {f.name for f in ASSETS.glob("archie-*.md")}
    command_mds = {f.name for f in COMMANDS.glob("archie-*.md")}

    # 3. Check: every standalone .py should have an asset copy
    for name in sorted(standalone_pys - asset_pys):
        errors.append(f"MISSING ASSET: archie/standalone/{name} has no copy in npm-package/assets/")
    for name in sorted(asset_pys - standalone_pys):
        errors.append(f"ORPHAN ASSET: npm-package/assets/{name} has no canonical in archie/standalone/")

    # 3b. Check: data files (platform_rules.json etc.)
    standalone_jsons = {f.name for f in STANDALONE.glob("*.json")}
    asset_jsons = {f.name for f in ASSETS.glob("*.json")}
    for name in sorted(standalone_jsons - asset_jsons):
        errors.append(f"MISSING ASSET: archie/standalone/{name} has no copy in npm-package/assets/")
    for name in sorted(standalone_jsons & asset_jsons):
        if (STANDALONE / name).read_text() != (ASSETS / name).read_text():
            errors.append(f"OUT OF SYNC: {name} differs between archie/standalone/ and npm-package/assets/")

    # 4. Check: every command .md should have an asset copy
    for name in sorted(command_mds - asset_mds):
        errors.append(f"MISSING ASSET: .claude/commands/{name} has no copy in npm-package/assets/")
    for name in sorted(asset_mds - command_mds):
        errors.append(f"ORPHAN ASSET: npm-package/assets/{name} has no canonical in .claude/commands/")

    # 5. Check: archie.mjs script list matches asset .py files
    for name in sorted(asset_pys - mjs_scripts):
        errors.append(f"NOT IN INSTALLER: npm-package/assets/{name} exists but not in archie.mjs script list")
    for name in sorted(mjs_scripts - asset_pys):
        errors.append(f"DEAD REFERENCE: archie.mjs references {name} but it doesn't exist in assets/")

    # 6. Check: archie.mjs command list matches asset .md files
    for name in sorted(asset_mds - mjs_commands):
        errors.append(f"NOT IN INSTALLER: npm-package/assets/{name} exists but not in archie.mjs command list")
    for name in sorted(mjs_commands - asset_mds):
        errors.append(f"DEAD REFERENCE: archie.mjs references {name} but it doesn't exist in assets/")

    # 7. Check: file contents match between canonical and asset
    for name in sorted(standalone_pys & asset_pys):
        canonical = (STANDALONE / name).read_text()
        asset = (ASSETS / name).read_text()
        if canonical != asset:
            errors.append(f"OUT OF SYNC: {name} differs between archie/standalone/ and npm-package/assets/")

    for name in sorted(command_mds & asset_mds):
        canonical = (COMMANDS / name).read_text()
        asset = (ASSETS / name).read_text()
        if canonical != asset:
            errors.append(f"OUT OF SYNC: {name} differs between .claude/commands/ and npm-package/assets/")

    # 8. Check: _shared/*.md fragments mirror between canonical and npm assets.
    #    These are Read at runtime by agent prompts (e.g. semantic_findings_spec.md),
    #    so a drift here ships a broken /archie-scan to npm users.
    shared_canonical = {f.name for f in SHARED_COMMANDS.glob("*.md")} if SHARED_COMMANDS.exists() else set()
    shared_asset = {f.name for f in SHARED_ASSETS.glob("*.md")} if SHARED_ASSETS.exists() else set()
    for name in sorted(shared_canonical - shared_asset):
        errors.append(f"MISSING ASSET: .claude/commands/_shared/{name} has no copy in npm-package/assets/_shared/")
    for name in sorted(shared_asset - shared_canonical):
        errors.append(f"ORPHAN ASSET: npm-package/assets/_shared/{name} has no canonical in .claude/commands/_shared/")
    for name in sorted(shared_canonical & shared_asset):
        if (SHARED_COMMANDS / name).read_text() != (SHARED_ASSETS / name).read_text():
            errors.append(f"OUT OF SYNC: _shared/{name} differs between .claude/commands/_shared/ and npm-package/assets/_shared/")

    # Report
    if errors:
        print(f"SYNC CHECK FAILED — {len(errors)} issue(s):\n")
        for e in errors:
            print(f"  {e}")
        print()
        sys.exit(1)
    else:
        print(f"SYNC CHECK PASSED — {len(standalone_pys)} scripts, {len(command_mds)} commands, {len(shared_canonical)} shared fragments, all in sync.")
        sys.exit(0)


if __name__ == "__main__":
    main()
