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

# Defensive .gitignore inside the mirror — root .gitignore covers node_modules/
# and dist/ but not *.tsbuildinfo, which `npm ci && vite build` would generate
# locally if run inside the mirror for testing.
cat > "$DST/.gitignore" <<EOF
node_modules/
dist/
*.tsbuildinfo
EOF

echo "Synced share/viewer/ → npm-package/assets/viewer/"
