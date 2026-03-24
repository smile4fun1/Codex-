#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

RUNTIME_DIR="$ROOT/startup/runtime/linux-arm"
CODEX_ENTRY="$RUNTIME_DIR/node_modules/@openai/codex/bin/codex.js"
if [[ ! -f "$CODEX_ENTRY" ]]; then
  echo "[Codex] Bootstrapping runtime (linux-arm64)..."
  "$ROOT/startup/linux-arm/bootstrap-runtime.sh"
fi

PORTABLE_HOME="$ROOT"
mkdir -p "$PORTABLE_HOME"/{log,memories,rules,sessions,skills,tmp}

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$ROOT/main.py" "$@"
fi

NODE="$RUNTIME_DIR/bin/node"
if [[ ! -x "$NODE" ]]; then
  echo "python3 not found and bundled node runtime missing at $NODE" >&2
  exit 1
fi

CODEX_HOME="$PORTABLE_HOME" HOME="$PORTABLE_HOME" "$NODE" "$CODEX_ENTRY" -c personality=pragmatic "$@"
