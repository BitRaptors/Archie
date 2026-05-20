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
ARCHIE_ASSETS = ROOT / "archie" / "assets"
ASSETS = ROOT / "npm-package" / "assets"
COMMANDS = ROOT / ".claude" / "commands"
ARCHIE_MJS = ROOT / "npm-package" / "bin" / "archie.mjs"

SKIP_FILES = {"__init__.py", "__pycache__"}


def get_archie_mjs_lists() -> tuple[set[str], set[str]]:
    """Parse archie.mjs to extract the script and command copy lists."""
    text = ARCHIE_MJS.read_text()

    # Extract script list: for (const script of ["scanner.py", ...]) {
    m = re.search(r'const script of \[(.*?)\]', text, re.DOTALL)
    scripts = set(re.findall(r'"([^"]+\.py)"', m.group(1))) if m else set()
    if "INSTALL_HOOKS_SCRIPT" in text:
        scripts.add("install_hooks.py")

    # Extract command list: for (const cmd of ["archie-init.md", ...]) {
    m = re.search(r'const cmd of \[(.*?)\]', text, re.DOTALL)
    commands = set(re.findall(r'"([^"]+\.md)"', m.group(1))) if m else set()

    return scripts, commands


def check_viewer_source_mirror(errors: list[str]) -> None:
    """Verify share/viewer/ build inputs are mirrored into npm-package/assets/viewer/.

    The mirror is what npx @bitraptors/archie copies into a target's .archie/viewer/
    so it can build at install time. Drift here means npx users get a stale React app.
    """
    src = ROOT / "share" / "viewer"
    dst = ROOT / "npm-package" / "assets" / "viewer"
    if not src.is_dir():
        return
    if not dst.is_dir():
        errors.append("npm-package/assets/viewer/ missing — run scripts/sync_viewer_assets.sh")
        return

    expected_files = [
        "package.json", "package-lock.json", "vite.config.ts",
        "tsconfig.json", "tailwind.config.js", "postcss.config.js", "index.html",
    ]
    for name in expected_files:
        s = src / name
        d = dst / name
        if s.exists() and not d.exists():
            errors.append(f"npm-package/assets/viewer/{name} missing (exists in share/viewer/)")
        elif s.exists() and d.exists() and s.read_bytes() != d.read_bytes():
            errors.append(
                f"share/viewer/{name} != npm-package/assets/viewer/{name} "
                "— run scripts/sync_viewer_assets.sh"
            )

    for subdir in ("src", "public"):
        s_dir = src / subdir
        d_dir = dst / subdir
        if not s_dir.is_dir():
            continue
        s_files = sorted(p.relative_to(src).as_posix() for p in s_dir.rglob("*") if p.is_file())
        d_files = (
            sorted(p.relative_to(dst).as_posix() for p in d_dir.rglob("*") if p.is_file())
            if d_dir.is_dir() else []
        )
        only_src = set(s_files) - set(d_files)
        only_dst = set(d_files) - set(s_files)
        if only_src:
            errors.append(
                f"share/viewer/{subdir}/ has files missing from asset mirror: "
                f"{','.join(sorted(only_src))}"
            )
        if only_dst:
            errors.append(
                f"asset mirror npm-package/assets/viewer/{subdir}/ has stale files: "
                f"{','.join(sorted(only_dst))}"
            )
        for rel in sorted(set(s_files) & set(d_files)):
            if (src / rel).read_bytes() != (dst / rel).read_bytes():
                errors.append(
                    f"share/viewer/{rel} != npm-package/assets/viewer/{rel} "
                    "— run scripts/sync_viewer_assets.sh"
                )


def check_archie_asset_mirrors(errors: list[str]) -> None:
    """Verify connector-backend canonical assets stay aligned with source truth."""
    canonical_skills = ROOT / ".claude" / "skills" / "archie-deep-scan"
    backend_skills = ARCHIE_ASSETS / "skills" / "archie-deep-scan"
    if canonical_skills.is_dir() and not backend_skills.is_dir():
        errors.append("archie/assets/skills/archie-deep-scan/ missing")
    elif canonical_skills.is_dir() and backend_skills.is_dir():
        canon = sorted(p.relative_to(canonical_skills).as_posix() for p in canonical_skills.rglob("*.md"))
        backend = sorted(p.relative_to(backend_skills).as_posix() for p in backend_skills.rglob("*.md"))
        if set(canon) != set(backend):
            only_canon = sorted(set(canon) - set(backend))
            only_backend = sorted(set(backend) - set(canon))
            if only_canon:
                errors.append(
                    "archie/assets/skills/archie-deep-scan/ missing files: "
                    + ",".join(only_canon)
                )
            if only_backend:
                errors.append(
                    "archie/assets/skills/archie-deep-scan/ has stale files: "
                    + ",".join(only_backend)
                )
        for rel in sorted(set(canon) & set(backend)):
            if (canonical_skills / rel).read_bytes() != (backend_skills / rel).read_bytes():
                errors.append(
                    "OUT OF SYNC: .claude/skills/archie-deep-scan/"
                    f"{rel} != archie/assets/skills/archie-deep-scan/{rel}"
                )

    share_viewer = ROOT / "share" / "viewer"
    backend_viewer = ARCHIE_ASSETS / "viewer"
    if share_viewer.is_dir() and not backend_viewer.is_dir():
        errors.append("archie/assets/viewer/ missing — copy the share/viewer source")
    elif share_viewer.is_dir() and backend_viewer.is_dir():
        expected_files = [
            "package.json", "package-lock.json", "vite.config.ts",
            "tsconfig.json", "tailwind.config.js", "postcss.config.js", "index.html",
        ]
        for name in expected_files:
            s = share_viewer / name
            d = backend_viewer / name
            if s.exists() and not d.exists():
                errors.append(f"archie/assets/viewer/{name} missing (exists in share/viewer/)")
            elif s.exists() and d.exists() and s.read_bytes() != d.read_bytes():
                errors.append(
                    f"share/viewer/{name} != archie/assets/viewer/{name} "
                    "— refresh the backend asset mirror"
                )

        for subdir in ("src", "public"):
            s_dir = share_viewer / subdir
            d_dir = backend_viewer / subdir
            if not s_dir.is_dir():
                continue
            s_files = sorted(p.relative_to(share_viewer).as_posix() for p in s_dir.rglob("*") if p.is_file())
            d_files = (
                sorted(p.relative_to(backend_viewer).as_posix() for p in d_dir.rglob("*") if p.is_file())
                if d_dir.is_dir() else []
            )
            only_src = set(s_files) - set(d_files)
            only_dst = set(d_files) - set(s_files)
            if only_src:
                errors.append(
                    "share/viewer/ files missing from archie/assets/viewer/: "
                    + ",".join(sorted(only_src))
                )
            if only_dst:
                errors.append(
                    "archie/assets/viewer/ has stale files: "
                    + ",".join(sorted(only_dst))
                )
            for rel in sorted(set(s_files) & set(d_files)):
                if (share_viewer / rel).read_bytes() != (backend_viewer / rel).read_bytes():
                    errors.append(
                        f"share/viewer/{rel} != archie/assets/viewer/{rel} "
                        "— refresh the backend asset mirror"
                    )

    for name in ("platform_rules.json",):
        canonical = STANDALONE / name
        backend = ARCHIE_ASSETS / name
        if canonical.exists() and not backend.exists():
            errors.append(f"archie/assets/{name} missing")
        elif canonical.exists() and backend.exists() and canonical.read_bytes() != backend.read_bytes():
            errors.append(f"OUT OF SYNC: archie/standalone/{name} != archie/assets/{name}")

    for name in ("archieignore.default", "archiebulk.default"):
        backend = ARCHIE_ASSETS / name
        asset = ASSETS / name
        if asset.exists() and not backend.exists():
            errors.append(f"archie/assets/{name} missing")
        elif asset.exists() and backend.exists() and asset.read_bytes() != backend.read_bytes():
            errors.append(f"OUT OF SYNC: archie/assets/{name} != npm-package/assets/{name}")

    backend_prompts = ARCHIE_ASSETS / "prompts"
    asset_prompts = ASSETS / "prompts"
    if backend_prompts.is_dir() and not asset_prompts.is_dir():
        errors.append("npm-package/assets/prompts/ missing")
    elif backend_prompts.is_dir() and asset_prompts.is_dir():
        backend_files = sorted(
            p.relative_to(backend_prompts).as_posix()
            for p in backend_prompts.rglob("*")
            if p.is_file() and p.name != ".DS_Store"
        )
        asset_files = sorted(
            p.relative_to(asset_prompts).as_posix()
            for p in asset_prompts.rglob("*")
            if p.is_file() and p.name != ".DS_Store"
        )
        only_backend = set(backend_files) - set(asset_files)
        only_asset = set(asset_files) - set(backend_files)
        if only_backend:
            errors.append(
                "npm-package/assets/prompts/ missing files: " + ",".join(sorted(only_backend))
            )
        if only_asset:
            errors.append(
                "npm-package/assets/prompts/ has stale files: " + ",".join(sorted(only_asset))
            )
        for rel in sorted(set(backend_files) & set(asset_files)):
            if (backend_prompts / rel).read_bytes() != (asset_prompts / rel).read_bytes():
                errors.append(
                    f"OUT OF SYNC: archie/assets/prompts/{rel} != npm-package/assets/prompts/{rel}"
                )


def check_install_pkg_mirror(errors: list[str]) -> None:
    """Verify npm-package/assets/_install_pkg mirrors the canonical installer code."""
    mirrors = {
        "install.py": ROOT / "archie" / "install.py",
        "manifest.py": ROOT / "archie" / "manifest.py",
        "manifest_data.py": ROOT / "archie" / "manifest_data.py",
        "connectors/__init__.py": ROOT / "archie" / "connectors" / "__init__.py",
        "connectors/base.py": ROOT / "archie" / "connectors" / "base.py",
        "connectors/claude.py": ROOT / "archie" / "connectors" / "claude.py",
        "connectors/codex.py": ROOT / "archie" / "connectors" / "codex.py",
    }
    install_pkg = ASSETS / "_install_pkg"
    if not install_pkg.is_dir():
        errors.append("npm-package/assets/_install_pkg/ missing")
        return
    init_py = install_pkg / "__init__.py"
    if not init_py.exists():
        errors.append("npm-package/assets/_install_pkg/__init__.py missing")
    elif init_py.read_text() != "":
        errors.append("npm-package/assets/_install_pkg/__init__.py must stay empty")
    for rel, src in mirrors.items():
        dst = install_pkg / rel
        if not dst.exists():
            errors.append(f"npm-package/assets/_install_pkg/{rel} missing")
        elif src.read_bytes() != dst.read_bytes():
            errors.append(f"OUT OF SYNC: {src.relative_to(ROOT)} != npm-package/assets/_install_pkg/{rel}")


def main():
    errors = []

    # 1. Get what archie.mjs thinks it should copy
    mjs_scripts, mjs_commands = get_archie_mjs_lists()

    # 2. Get actual files
    standalone_pys = {f.name for f in STANDALONE.glob("*.py") if f.name not in SKIP_FILES}
    asset_pys = {f.name for f in ASSETS.glob("*.py")}

    # Command markdown files — top-level (archie-*.md) plus _shared/ fragments
    # that get copied into .claude/commands/. The archie-deep-scan/ substeps
    # live under .claude/skills/ now (see SKILLS below) so Claude Code doesn't
    # surface them as slash commands.
    def _collect_command_mds(base: Path) -> set[str]:
        out: set[str] = set()
        for p in base.glob("archie-*.md"):
            if p.is_file():
                out.add(p.name)
        for sub in ("_shared",):
            sub_dir = base / sub
            if sub_dir.is_dir():
                for p in sub_dir.rglob("*.md"):
                    out.add(str(p.relative_to(base)))
        return out

    asset_mds = _collect_command_mds(ASSETS)
    command_mds = _collect_command_mds(COMMANDS)

    # Skill markdown files — the archie-deep-scan/ substeps. Canonical lives
    # in .claude/skills/, mirrored into npm-package/assets/skills/.
    SKILLS = ROOT / ".claude" / "skills"
    ASSET_SKILLS = ASSETS / "skills"
    def _collect_skill_mds(base: Path) -> set[str]:
        out: set[str] = set()
        deep_scan_dir = base / "archie-deep-scan"
        if deep_scan_dir.is_dir():
            for p in deep_scan_dir.rglob("*.md"):
                out.add(str(p.relative_to(base)))
        return out

    asset_skill_mds = _collect_skill_mds(ASSET_SKILLS)
    skill_mds = _collect_skill_mds(SKILLS)
    for name in sorted(skill_mds - asset_skill_mds):
        errors.append(f"MISSING ASSET: .claude/skills/{name} has no copy in npm-package/assets/skills/")
    for name in sorted(asset_skill_mds - skill_mds):
        errors.append(f"ORPHAN ASSET: npm-package/assets/skills/{name} has no canonical in .claude/skills/")
    for name in sorted(skill_mds & asset_skill_mds):
        if (SKILLS / name).read_text() != (ASSET_SKILLS / name).read_text():
            errors.append(f"OUT OF SYNC: skills/{name} differs between .claude/skills/ and npm-package/assets/skills/")

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
    # (but exclude _shared/ fragments, which are copied recursively — not
    # listed individually in the installer command list)
    asset_mds_commands_only = {
        name for name in asset_mds
        if not name.startswith("_shared/")
    }
    if mjs_commands:
        for name in sorted(asset_mds_commands_only - mjs_commands):
            errors.append(f"NOT IN INSTALLER: npm-package/assets/{name} exists but not in archie.mjs command list")
        for name in sorted(mjs_commands - asset_mds_commands_only):
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

    # 8. Check: share/viewer/ build inputs are mirrored into npm-package/assets/viewer/
    check_viewer_source_mirror(errors)
    check_archie_asset_mirrors(errors)
    check_install_pkg_mirror(errors)

    # Report
    if errors:
        print(f"SYNC CHECK FAILED — {len(errors)} issue(s):\n")
        for e in errors:
            print(f"  {e}")
        print()
        sys.exit(1)
    else:
        print(f"SYNC CHECK PASSED — {len(standalone_pys)} scripts, {len(command_mds)} commands, all in sync.")
        sys.exit(0)


if __name__ == "__main__":
    main()
