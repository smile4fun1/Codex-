#!/usr/bin/env bash
set -euo pipefail

DIR="${1:-$HOME/Codex-}"
REPO_URL="https://github.com/smile4fun1/Codex-/archive/refs/heads/main.tar.gz"

echo "[Codex] Installing into: $DIR"
mkdir -p "$DIR"
cd "$DIR"

curl -fsSL "$REPO_URL" | tar -xz --strip-components=1
chmod +x startup/bootstrap-all.sh startup/linux-arm/*.sh startup/linux/*.sh startup/macos/*.sh 2>/dev/null || true

./startup/bootstrap-all.sh

