#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Check for node
if ! command -v node &>/dev/null; then
  echo "Error: Node.js is not installed."
  exit 1
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

# Create .env from example if missing
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your API keys there."
fi

# Create data directories
mkdir -p data public/thumbnails output

echo ""
echo "  PinLaunch — AI Landing Page Builder"
echo "  Starting at http://localhost:3000"
echo ""

exec npm run dev
