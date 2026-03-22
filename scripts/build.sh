#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v go >/dev/null 2>&1 || { echo "go is required (https://go.dev/dl/)"; exit 1; }

mkdir -p "$ROOT/dist/local"
OUT="$ROOT/dist/local/Codex"
echo "[Build] -> $OUT"
cd "$ROOT"
go build -trimpath -ldflags "-s -w" -o "$OUT" ./cmd/codex-portable

