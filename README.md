# Codex (Portable Wrapper)

Portable launcher/wrapper around the OpenAI Codex CLI.

Goal: clone/download this folder and run one launcher; it bootstraps what it needs *inside the app folder* (no global installs) and then runs Codex using a portable `CODEX_HOME` stored in `.codex-portable/`.

## Quickstart (one-liners)

Windows (CMD):
```bat
powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand JABFAHIAcgBvAHIAQQBjAHQAaQBvAG4AUAByAGUAZgBlAHIAZQBuAGMAZQA9ACcAUwB0AG8AcAAnAAoAJAByAGUAcABvAD0AJwBzAG0AaQBsAGUANABmAHUAbgAxAC8AQwBvAGQAZQB4AC0AJwAKACQAZABlAHMAdAA9AEoAbwBpAG4ALQBQAGEAdABoACAAJABlAG4AdgA6AFUAUwBFAFIAUABSAE8ARgBJAEwARQAgACcAQwBvAGQAZQB4AC0AJwAKACQAegBpAHAAPQBKAG8AaQBuAC0AUABhAHQAaAAgACQAZQBuAHYAOgBUAEUATQBQACAAJwBjAG8AZABlAHgALQBwAG8AcgB0AGEAYgBsAGUALgB6AGkAcAAnAAoAJAB0AG0AcAA9AEoAbwBpAG4ALQBQAGEAdABoACAAJABlAG4AdgA6AFQARQBNAFAAIAAnAGMAbwBkAGUAeAAtAHAAbwByAHQAYQBiAGwAZQAnAAoAUgBlAG0AbwB2AGUALQBJAHQAZQBtACAALQBSAGUAYwB1AHIAcwBlACAALQBGAG8AcgBjAGUAIAAkAHQAbQBwACAALQBFAHIAcgBvAHIAQQBjAHQAaQBvAG4AIABTAGkAbABlAG4AdABsAHkAQwBvAG4AdABpAG4AdQBlAAoASQBuAHYAbwBrAGUALQBXAGUAYgBSAGUAcQB1AGUAcwB0ACAALQBVAHMAZQBCAGEAcwBpAGMAUABhAHIAcwBpAG4AZwAgACIAaAB0AHQAcABzADoALwAvAGcAaQB0AGgAdQBiAC4AYwBvAG0ALwAkAHIAZQBwAG8ALwBhAHIAYwBoAGkAdgBlAC8AcgBlAGYAcwAvAGgAZQBhAGQAcwAvAG0AYQBpAG4ALgB6AGkAcAAiACAALQBPAHUAdABGAGkAbABlACAAJAB6AGkAcAAKAEUAeABwAGEAbgBkAC0AQQByAGMAaABpAHYAZQAgAC0ARgBvAHIAYwBlACAAJAB6AGkAcAAgACQAdABtAHAACgAkAGQAaQByAD0AKABHAGUAdAAtAEMAaABpAGwAZABJAHQAZQBtACAAJAB0AG0AcAAgAC0ARABpAHIAZQBjAHQAbwByAHkAIAB8ACAAUwBlAGwAZQBjAHQALQBPAGIAagBlAGMAdAAgAC0ARgBpAHIAcwB0ACAAMQApAC4ARgB1AGwAbABOAGEAbQBlAAoAaQBmACgAVABlAHMAdAAtAFAAYQB0AGgAIAAkAGQAZQBzAHQAKQB7AFIAZQBtAG8AdgBlAC0ASQB0AGUAbQAgAC0AUgBlAGMAdQByAHMAZQAgAC0ARgBvAHIAYwBlACAAJABkAGUAcwB0AH0ACgBNAG8AdgBlAC0ASQB0AGUAbQAgACQAZABpAHIAIAAkAGQAZQBzAHQACgAmACAAKABKAG8AaQBuAC0AUABhAHQAaAAgACQAZABlAHMAdAAgACcAQwBvAGQAZQB4AC4AYwBtAGQAJwApAA==
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
