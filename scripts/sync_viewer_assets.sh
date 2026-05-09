#!/usr/bin/env bash
# scripts/sync_viewer_assets.sh
# Mirror share/viewer/ build inputs into npm-package/assets/viewer/.
# node_modules/ and dist/ are excluded — they're built at install time.
set -euo pipefail

SRC="share/viewer"
DST="npm-package/assets/viewer"

rm -rf "$DST"
mkdir -p "$DST"

# Copy source + configs only
for item in src public package.json package-lock.json vite.config.ts \
            tsconfig.json tsconfig.node.json tailwind.config.js \
            postcss.config.js index.html; do
  if [ -e "$SRC/$item" ]; then
    cp -r "$SRC/$item" "$DST/$item"
  fi
done

echo "Synced share/viewer/ → npm-package/assets/viewer/"
