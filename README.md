# Codex (Portable Wrapper)

Portable launcher/wrapper around the OpenAI Codex CLI.

Goal: clone/download this folder and run one launcher; it bootstraps what it needs inside the app folder (no global installs) and then runs Codex using a portable `CODEX_HOME` rooted in the app folder itself.

This public repo ships with empty `skills/` and `memories/` templates only. Real user skills, memories, auth, sessions, and logs stay local and out of git.

If the app lives inside a Git repo and `git` is available, the wrapper can auto-commit tracked memory and user-skill changes back into that repo. In this public repo, the default ignore rules keep live user data out of version control.

After install:
- Open a new terminal and run `codex`
- That command opens this portable instance, not a separate project copy
- Learned Codex skills live in `skills/`
- Codex memories live in `memories/`
- Wrapper-internal state lives in `wrapper-skills/` and `wrapper-memory/`
- `codex /skills-clean` validates the user skill tree and disables duplicate/low-value skills

## Storage rules

- `memories/` is the source of truth for user knowledge only: preferences, learned facts, and compressed relevant context
- `wrapper-memory/` is system state only: scheduled tasks, heartbeat state, execution logs, and internal loop history
- `skills/` is the user-facing Codex skill tree
- `wrapper-skills/` is wrapper metadata and built-in helper registry
- If `memories/`, tracked `skills/`, or `wrapper-memory/tasks.json` are versioned in a Git repo, the wrapper auto-commits changes there after runs and scheduled-task updates

## Scheduled tasks

- Scheduled tasks live in `wrapper-memory/tasks.json`
- Supported schedules:
  - `interval:60`
  - `daily:08:00`
- Task results are written to `wrapper-memory/history/` and `wrapper-memory/execution-log.jsonl`
- If any enabled task exists, the launcher starts a silent heartbeat loop automatically

Task shape:

```json
{
  "id": "unique_id",
  "type": "check",
  "schedule": "interval:60",
  "prompt": "instruction passed to Codex",
  "last_run": null,
  "enabled": true
}
```

## Telegram notifications

Optional in `config.toml`:

```toml
telegram_token = "123456:token"
chat_id = "123456789"
```

If omitted, task output stays in CLI logs only.

## Quickstart (one-liners)

Windows (CMD):
```bat
curl.exe -L https://raw.githubusercontent.com/smile4fun1/Codex-/main/install.ps1 -o "%TEMP%\codex-install.ps1" && powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\codex-install.ps1"
```

Windows (PowerShell):
```powershell
iwr -useb https://raw.githubusercontent.com/smile4fun1/Codex-/main/install.ps1 -OutFile $env:TEMP\codex-install.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File $env:TEMP\codex-install.ps1
```

macOS / Linux (bash/zsh):
```bash
curl -fsSL https://raw.githubusercontent.com/smile4fun1/Codex-/main/install.sh | bash
```

Note:
- Windows installer is tested.
- macOS/Linux path is patched for executable bits and Python-free bootstrap, but not yet runtime-tested on a real Mac from this environment.

## Launch (one-click)

Recommended (GitHub Releases):
- Download the asset for your OS/CPU and run `Codex` / `Codex.exe` from the extracted folder.

Windows:
- Double-click `Windows-Startup.cmd`

Linux / Raspberry Pi:
```bash
cd /path/to/Codex-
chmod +x startup/bootstrap-all.sh startup/linux-arm/*.sh startup/linux/*.sh
chmod +x Linux-Startup.sh
./Linux-Startup.sh
```

macOS:
```bash
cd /path/to/Codex-
chmod +x startup/bootstrap-all.sh startup/macos/*.sh
chmod +x macOS-Startup.command startup/macos/*.command
./macOS-Startup.command
```

## What bootstrap does
- Downloads Node.js LTS into `startup/runtime/<platform>`
- Verifies SHA256 (`SHASUMS256.txt`)
- Installs `@openai/codex` into that local runtime
- Writes `startup/runtime/<platform>/runtime-version.json`
- Launches Codex with portable state rooted in this app folder

## First run notes
- You’ll likely need to authenticate once: `codex login` (or `./startup/bootstrap-all.sh login`).
- Requires internet access (to download Node/Codex and to use Codex).
- Python is optional: if `python3`/`python` is present the wrapper adds extra context; if not, it still launches Codex directly via the bundled Node runtime.
- The clear manual launchers are `Windows-Startup.cmd`, `Linux-Startup.sh`, and `macOS-Startup.command`. The `startup/` folder contains the internal platform scripts they call.

Fresh instance behavior:
- By default this does **not** copy anything from `~/.codex` / `%USERPROFILE%\\.codex`.
- To seed from an existing local Codex install, set `CODEX_PORTABLE_SEED=1`.
