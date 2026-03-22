#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

RUNTIME_DIR="$ROOT/startup/runtime/linux"
CODEX_ENTRY="$RUNTIME_DIR/node_modules/@openai/codex/bin/codex.js"
RUNTIME_VERSION="$RUNTIME_DIR/runtime-version.json"

download() {
  local url="$1"
  local out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$out"
    return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO "$out" "$url"
    return 0
  fi
  echo "Need curl or wget to download runtime assets." >&2
  return 1
}

ensure_node() {
  if [[ -x "$RUNTIME_DIR/bin/node" && -x "$RUNTIME_DIR/bin/npm" ]]; then
    return 0
  fi

  local machine
  machine="$(uname -m | tr '[:upper:]' '[:lower:]')"
  case "$machine" in
    x86_64|amd64)
      ;;
    *)
      echo "Unsupported Linux architecture for startup/linux: ${machine}" >&2
      echo "Use startup/linux-arm on ARM devices." >&2
      exit 1
      ;;
  esac

  mkdir -p "$RUNTIME_DIR"
  local tmp
  tmp="$(mktemp -d)"
  trap "rm -rf '$tmp'" EXIT

  echo "[Codex] Detecting latest Node.js LTS for linux-x64..."
  local ver
  ver="$(download "https://nodejs.org/dist/index.json" "${tmp}/index.json" && grep -m1 '"lts":"' "${tmp}/index.json" | sed -E 's/.*"version":"([^"]+)".*/\1/')"
  if [[ -z "$ver" ]]; then
    echo "[Codex] Could not determine latest Node.js LTS version." >&2
    exit 1
  fi

  local tarball="node-${ver}-linux-x64.tar.gz"
  local base="https://nodejs.org/dist/${ver}"
  echo "[Codex] Downloading ${tarball}..."
  download "${base}/${tarball}" "${tmp}/${tarball}"
  download "${base}/SHASUMS256.txt" "${tmp}/SHASUMS256.txt"

  if command -v sha256sum >/dev/null 2>&1; then
    local expected actual
    expected="$(grep " ${tarball}\$" "${tmp}/SHASUMS256.txt" | awk '{print $1}')"
    actual="$(sha256sum "${tmp}/${tarball}" | awk '{print $1}')"
    if [[ -z "$expected" || "$expected" != "$actual" ]]; then
      echo "[Codex] SHA256 mismatch for ${tarball}" >&2
      exit 1
    fi
  fi

  echo "[Codex] Extracting Node.js into app runtime..."
  tar -xzf "${tmp}/${tarball}" -C "$tmp"
  local extracted="${tmp}/node-${ver}-linux-x64"
  if [[ ! -d "$extracted" ]]; then
    echo "[Codex] Unexpected archive layout: ${extracted} not found" >&2
    exit 1
  fi

  rm -rf "$RUNTIME_DIR/bin" "$RUNTIME_DIR/include" "$RUNTIME_DIR/lib" "$RUNTIME_DIR/share"
  cp -a "${extracted}/." "$RUNTIME_DIR/"
}

ensure_node

if [[ -f "$CODEX_ENTRY" ]]; then
  echo "[Codex] Codex runtime already present."
  exit 0
fi

echo "[Codex] Installing @openai/codex into app runtime..."
PATH="$RUNTIME_DIR/bin:$PATH" "$RUNTIME_DIR/bin/npm" --prefix "$RUNTIME_DIR" install --no-audit --no-fund @openai/codex
CODEX_VERSION="$(PATH="$RUNTIME_DIR/bin:$PATH" "$RUNTIME_DIR/bin/node" -p "require('$RUNTIME_DIR/node_modules/@openai/codex/package.json').version")"
printf '{\n  "platform": "linux",\n  "node_version": "%s",\n  "codex_version": "%s",\n  "installed_at": "%s"\n}\n' \
  "$("$RUNTIME_DIR/bin/node" -p "process.version")" \
  "$CODEX_VERSION" \
  "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$RUNTIME_VERSION"
