#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m | tr '[:upper:]' '[:lower:]')"

echo "[Codex] Preparing portable startup..."

if [[ "$OS" == "darwin" ]]; then
  exec "$ROOT/startup/macos/codex-portable.command" "$@"
fi

if [[ "$ARCH" == *"arm"* || "$ARCH" == "aarch64" ]]; then
  exec "$ROOT/startup/linux-arm/codex-portable.sh" "$@"
fi

exec "$ROOT/startup/linux/codex-portable.sh" "$@"
