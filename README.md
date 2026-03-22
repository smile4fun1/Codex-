# Codex (Portable Wrapper)

Portable launcher/wrapper around the OpenAI Codex CLI.

Goal: clone/download this folder and run one launcher; it bootstraps what it needs *inside the app folder* (no global installs) and then runs Codex using a portable `CODEX_HOME` stored in `.codex-portable/`.

## Launch (one-click)

Windows:
- Double-click `Codex.cmd`

Linux (x64) / Linux ARM (Pi):
```bash
cd /path/to/Codex-
chmod +x startup/bootstrap-all.sh startup/linux-arm/*.sh startup/linux/*.sh
./startup/bootstrap-all.sh
```

macOS:
```bash
cd /path/to/Codex-
chmod +x startup/bootstrap-all.sh startup/macos/*.sh
./startup/bootstrap-all.sh
```

## What bootstrap does
- Downloads Node.js LTS into `startup/runtime/<platform>`
- Verifies SHA256 (`SHASUMS256.txt`)
- Installs `@openai/codex` into that local runtime
- Launches Codex with portable state in `.codex-portable/`

## First run notes
- You’ll likely need to authenticate once: `codex login` (or `./startup/bootstrap-all.sh login`).
- Requires internet access (to download Node/Codex and to use Codex).
- Requires `python3` on macOS/Linux (wrapper is Python).

Fresh instance behavior:
- By default this does **not** copy anything from `~/.codex` / `%USERPROFILE%\\.codex`.
- To seed from an existing local Codex install, set `CODEX_PORTABLE_SEED=1`.
