#!/bin/zsh

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm not found. Install Node.js first."
  read -r "?Press Enter to close..."
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "[INFO] Installing npm dependencies..."
  npm install
fi

echo "[INFO] Starting Politics Studio..."
npm run dev
