# Startup

Portable startup assets for the Codex wrapper.

What this folder does:
- starts the local wrapper cleanly from Windows, macOS, Linux, and Linux ARM
- prefers a bundled Codex runtime when present
- falls back to a system Codex install if available
- can bootstrap a local runtime when `node` and `npm` exist
- uses an app-local portable Codex home so auth/config/sessions can travel with the drive
- picks the runtime target from the detected OS and CPU architecture immediately on launch

Windows today:
- `..\Windows-Startup.cmd`
- `..\Codex.cmd`
- `..\Codex.ps1`
- `bootstrap-all.cmd`
- `bootstrap-all.ps1`
- `windows\CodexPortable.cmd`
- `windows\CodexPortable.ps1`

Unix-style targets:
- `..\Linux-Startup.sh`
- `..\macOS-Startup.command`
- `bootstrap-all.sh`
- `macos\codex-portable.command`
- `linux\codex-portable.sh`
- `linux-arm\codex-portable.sh`

Bundled runtime:
- `runtime\windows\...` contains a portable Windows Codex runtime copied from the current machine
- `runtime\macos`, `runtime\linux`, and `runtime\linux-arm` are bootstrap targets for local installs on those systems

Notes:
- Runtime target selection is:
  - Windows -> `runtime\windows`
  - macOS -> `runtime\macos`
  - Linux x64 -> `runtime\linux`
  - Linux ARM -> `runtime\linux-arm`
- On every platform, the startup scripts try bundled runtime first, then system `codex`, then local bootstrap via `npm` if `node` and `npm` are available.
- The wrapper stores memory, profile, and skill data in the app folder, but launches Codex from the detected system root.
- Portable Codex state lives at the app root itself. A legacy `.codex-portable` tree is migrated forward on launch if present.
- If the app root is a Git repo and `git` is available, tracked memory and user-skill changes are auto-committed there after runs. In this public repo, ignore rules keep live user data local by default.
- `bootstrap-all.*` is the simplest entrypoint if you want one launcher that prepares and starts portable Codex on that platform.
