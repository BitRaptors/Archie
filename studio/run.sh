#!/usr/bin/env bash
# Archie Studio launcher.
#
# Usage:
#   studio/run.sh                      # open the folder picker in the browser
#   studio/run.sh /path/to/project     # open a project directly
#   studio/run.sh /path --prd docs/specs --port 5848 --no-open
#
# Installs frontend dependencies on first run and rebuilds the SPA whenever
# studio or viewer sources are newer than the last build, then starts server.py.
set -euo pipefail

STUDIO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$STUDIO_DIR/frontend"
DIST="$FRONTEND/dist/index.html"
VIEWER_SRC="$STUDIO_DIR/../npm-package/assets/viewer/src"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found." >&2
  exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "[studio] first run — installing frontend dependencies..."
  (cd "$FRONTEND" && npm install)
fi

# Rebuild when the build is missing or any source/config is newer than it.
needs_build=0
if [ ! -f "$DIST" ]; then
  needs_build=1
elif [ -n "$(find "$FRONTEND/src" "$VIEWER_SRC" "$FRONTEND/index.html" \
      "$FRONTEND/vite.config.ts" "$FRONTEND/tailwind.config.cjs" \
      \( -name '*.ts' -o -name '*.tsx' -o -name '*.css' -o -name '*.html' -o -name '*.cjs' \) \
      -newer "$DIST" -print -quit 2>/dev/null)" ]; then
  needs_build=1
fi

if [ "$needs_build" = "1" ]; then
  echo "[studio] building frontend..."
  (cd "$FRONTEND" && npm run build)
fi

exec python3 "$STUDIO_DIR/server.py" "$@"
