#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to launch portable Codex on macOS."; exit 1; }

RUNTIME_DIR="$ROOT/startup/runtime/macos"
CODEX_ENTRY="$RUNTIME_DIR/node_modules/@openai/codex/bin/codex.js"
if [[ ! -f "$CODEX_ENTRY" ]]; then
  echo "[Codex] Bootstrapping runtime (macOS)..."
  "$ROOT/startup/macos/bootstrap-runtime.sh"
fi

exec python3 "$ROOT/main.py" "$@"
