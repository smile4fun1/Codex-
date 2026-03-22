# Startup

Portable startup assets for the Codex wrapper.

What this folder does:
- starts the local wrapper cleanly from Windows, macOS, Linux, and Linux ARM
- prefers a bundled Codex runtime when present
- falls back to a system Codex install if available
- can bootstrap a local runtime when `node` and `npm` exist
- uses an app-local portable Codex home so auth/config/sessions can travel with the drive

Windows today:
- `..\Codex.cmd`
- `..\Codex.ps1`
- `bootstrap-all.cmd`
- `bootstrap-all.ps1`
- `windows\CodexPortable.cmd`
- `windows\CodexPortable.ps1`

Unix-style targets:
- `bootstrap-all.sh`
- `macos\codex-portable.command`
- `linux\codex-portable.sh`
- `linux-arm\codex-portable.sh`

Bundled runtime:
- `runtime\windows\...` contains a portable Windows Codex runtime copied from the current machine
- `runtime\macos`, `runtime\linux`, and `runtime\linux-arm` are bootstrap targets for local installs on those systems

Notes:
- The Windows bundle is ready now.
- On macOS/Linux/Linux ARM, the startup scripts will try bundled runtime first, then system `codex`, then local bootstrap via `npm` if `node` and `npm` are available.
- The wrapper stores memory, profile, and skill data in the app folder, but launches Codex from the detected system root.
- Portable Codex state lives in `.codex-portable` at the app root. On first run it seeds from the current machine's local `.codex` if available.
- `bootstrap-all.*` is the simplest entrypoint if you want one launcher that prepares and starts portable Codex on that platform.
