#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$ROOT"/startup/bootstrap-all.sh "$ROOT"/startup/linux/*.sh "$ROOT"/startup/linux-arm/*.sh "$ROOT"/startup/macos/*.sh "$ROOT"/startup/macos/*.command 2>/dev/null || true
exec "$ROOT/startup/bootstrap-all.sh" "$@"
