# Codex (Portable Wrapper)

Portable launcher/wrapper around the OpenAI Codex CLI.

Goal: clone/download this folder and run one launcher; it bootstraps what it needs *inside the app folder* (no global installs) and then runs Codex using a portable `CODEX_HOME` stored in `.codex-portable/`.

## Quickstart (one-liners)

Windows (CMD):
```bat
powershell -NoProfile -ExecutionPolicy Bypass -Command "$repo='smile4fun1/Codex-'; $dest=\"$env:USERPROFILE\\Codex-\"; $zip=\"$env:TEMP\\codex-portable.zip\"; $tmp=\"$env:TEMP\\codex-portable\"; Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue; Invoke-WebRequest -UseBasicParsing \"https://github.com/$repo/archive/refs/heads/main.zip\" -OutFile $zip; Expand-Archive -Force $zip $tmp; $dir=(Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName; if(Test-Path $dest){Remove-Item -Recurse -Force $dest}; Move-Item $dir $dest; & \"$dest\\Codex.cmd\""
```

macOS / Linux (bash/zsh):
```bash
mkdir -p ~/Codex- && cd ~/Codex- && curl -fsSL https://github.com/smile4fun1/Codex-/archive/refs/heads/main.tar.gz | tar -xz --strip-components=1 && chmod +x startup/bootstrap-all.sh startup/linux-arm/*.sh startup/linux/*.sh startup/macos/*.sh 2>/dev/null || true && ./startup/bootstrap-all.sh
```

## Launch (one-click)

Recommended (GitHub Releases):
- Download the asset for your OS/CPU and run `Codex` / `Codex.exe` from the extracted folder.

Windows:
- Double-click `Codex.cmd`

Linux / Raspberry Pi:
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
- Python is optional: if `python3`/`python` is present the wrapper adds extra context; if not, it still launches Codex directly via the bundled Node runtime.

Fresh instance behavior:
- By default this does **not** copy anything from `~/.codex` / `%USERPROFILE%\\.codex`.
- To seed from an existing local Codex install, set `CODEX_PORTABLE_SEED=1`.
