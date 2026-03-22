#!/usr/bin/env bash
set -euo pipefail

DIR="${1:-$HOME/Codex-}"
REPO_URL="https://github.com/smile4fun1/Codex-/archive/refs/heads/main.tar.gz"
BIN_DIR="${HOME}/.local/bin"
SHELL_RC=""

if [[ -n "${ZDOTDIR:-}" && -f "${ZDOTDIR}/.zshrc" ]]; then
  SHELL_RC="${ZDOTDIR}/.zshrc"
elif [[ -f "${HOME}/.zshrc" ]]; then
  SHELL_RC="${HOME}/.zshrc"
elif [[ -f "${HOME}/.bashrc" ]]; then
  SHELL_RC="${HOME}/.bashrc"
elif [[ -f "${HOME}/.bash_profile" ]]; then
  SHELL_RC="${HOME}/.bash_profile"
fi

echo "[Codex] Installing into: $DIR"
mkdir -p "$DIR"
cd "$DIR"

curl -fsSL "$REPO_URL" | tar -xz --strip-components=1
chmod +x codex 2>/dev/null || true
chmod +x startup/bootstrap-all.sh startup/linux-arm/*.sh startup/linux/*.sh startup/macos/*.sh 2>/dev/null || true
chmod +x startup/macos/*.command 2>/dev/null || true

echo "[Codex] Registering 'codex' command..."
mkdir -p "$BIN_DIR"
ln -sfn "$DIR/codex" "$BIN_DIR/codex"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    if [[ -n "$SHELL_RC" ]]; then
      if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_RC"; then
        printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$SHELL_RC"
      fi
      export PATH="$HOME/.local/bin:$PATH"
      echo "[Codex] Added $BIN_DIR to PATH via $SHELL_RC. Open a new terminal and run: codex"
    else
      echo "[Codex] Add $BIN_DIR to PATH, then run: codex"
    fi
    ;;
esac

./startup/bootstrap-all.sh
