#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to launch portable Codex on Linux."; exit 1; }

RUNTIME_DIR="$ROOT/startup/runtime/linux"
CODEX_ENTRY="$RUNTIME_DIR/node_modules/@openai/codex/bin/codex.js"
if [[ ! -f "$CODEX_ENTRY" ]]; then
  echo "[Codex] Bootstrapping runtime (linux-x64)..."
  "$ROOT/startup/linux/bootstrap-runtime.sh"
fi

exec python3 "$ROOT/main.py" "$@"
