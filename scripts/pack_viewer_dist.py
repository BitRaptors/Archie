#!/usr/bin/env python3
"""Build the share viewer React app and copy dist to npm-package/assets/viewer_dist/."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER_DIR = ROOT / "share" / "viewer"
DIST_DIR = VIEWER_DIR / "dist"
TARGET_DIR = ROOT / "npm-package" / "assets" / "viewer_dist"

def main():
    print("Building share viewer...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(VIEWER_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Build failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Build OK.")

    if not DIST_DIR.is_dir():
        print(f"Error: dist/ not found at {DIST_DIR}", file=sys.stderr)
        sys.exit(1)

    # Clean and copy
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    shutil.copytree(DIST_DIR, TARGET_DIR)
    print(f"Copied dist -> {TARGET_DIR}")

    # Also copy to archie/standalone/viewer_dist for local dev
    local_target = ROOT / "archie" / "standalone" / "viewer_dist"
    if local_target.exists():
        shutil.rmtree(local_target)
    shutil.copytree(DIST_DIR, local_target)
    print(f"Copied dist -> {local_target}")

    print("Done.")

if __name__ == "__main__":
    main()
