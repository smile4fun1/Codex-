from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

from agent.augmentation import AugmentationLayer


ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(os.environ.get("CODEX_WORKSPACE_ROOT") or str(ROOT)).resolve()
VENV_DIR = ROOT / ".venv"
STARTUP_DIR = ROOT / "startup"
PORTABLE_CODEX_HOME = ROOT
LEGACY_PORTABLE_CODEX_HOME = ROOT / ".codex-portable"


def is_admin() -> bool:
    if os.name != "nt":
        geteuid = getattr(os, "geteuid", None)
        return bool(geteuid and geteuid() == 0)
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(args: list[str]) -> bool:
    if os.name != "nt":
        return False
    if is_admin():
        return False
    script = str((ROOT / "main.py").resolve())
    forwarded = " ".join([f'"{arg}"' for arg in args])
    command = (
        f'Start-Process -FilePath "{sys.executable}" '
        f'-ArgumentList \'"{script}" {forwarded}\' -Verb RunAs'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=False,
    )
    return True


def ensure_venv() -> None:
    if os.name != "nt":
        return
    if not VENV_DIR.exists():
        try:
            venv.EnvBuilder(with_pip=True).create(VENV_DIR)
        except Exception:
            return


def ensure_portable_codex_home() -> None:
    migrate_legacy_portable_home()

    PORTABLE_CODEX_HOME.mkdir(parents=True, exist_ok=True)
    for name in ["log", "memories", "rules", "sessions", "skills", "tmp"]:
        (PORTABLE_CODEX_HOME / name).mkdir(parents=True, exist_ok=True)

    seed = os.environ.get("CODEX_PORTABLE_SEED", "").strip().lower() in {"1", "true", "yes"}
    if seed:
        source_home = Path.home() / ".codex"
        if source_home.exists():
            for filename in ["auth.json", "config.toml", "version.json", "models_cache.json"]:
                src = source_home / filename
                dst = PORTABLE_CODEX_HOME / filename
                if src.exists() and not dst.exists():
                    dst.write_bytes(src.read_bytes())
            src_rules = source_home / "rules" / "default.rules"
            dst_rules = PORTABLE_CODEX_HOME / "rules" / "default.rules"
            if src_rules.exists() and not dst_rules.exists():
                dst_rules.write_bytes(src_rules.read_bytes())


def migrate_legacy_portable_home() -> None:
    if not LEGACY_PORTABLE_CODEX_HOME.exists():
        return

    for name in ["log", "memories", "rules", "sessions", "skills", "tmp"]:
        src_dir = LEGACY_PORTABLE_CODEX_HOME / name
        dst_dir = PORTABLE_CODEX_HOME / name
        if src_dir.exists():
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

    for pattern in [
        "auth.json",
        "config.toml",
        "version.json",
        "models_cache.json",
        "history.jsonl",
        "cap_sid",
        ".personality_migration",
        "sandbox.log",
        "logs_*.sqlite*",
        "state_*.sqlite*",
    ]:
        for src in LEGACY_PORTABLE_CODEX_HOME.glob(pattern):
            dst = PORTABLE_CODEX_HOME / src.name
            if not dst.exists():
                if src.is_file():
                    shutil.copy2(src, dst)

    for name in [".sandbox", ".sandbox-bin"]:
        src_dir = LEGACY_PORTABLE_CODEX_HOME / name
        dst_dir = PORTABLE_CODEX_HOME / name
        if src_dir.exists() and not dst_dir.exists():
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)


def split_wrapper_args(argv: list[str]) -> tuple[bool, list[str]]:
    forwarded: list[str] = []
    skip_elevation = False
    for arg in argv:
        if arg == "--skip-elevation":
            skip_elevation = True
        else:
            forwarded.append(arg)
    return skip_elevation, forwarded


def infer_prompt(args: list[str]) -> str | None:
    if not args:
        return None
    if "exec" in args:
        index = args.index("exec")
        tail = [arg for arg in args[index + 1 :] if not arg.startswith("-")]
        return tail[-1] if tail else None
    non_flags = [arg for arg in args if not arg.startswith("-")]
    if non_flags and non_flags[0] not in {"exec", "review", "resume", "fork", "login", "logout", "mcp", "features", "sandbox", "debug", "apply", "cloud", "help"}:
        return non_flags[-1]
    return None


def build_codex_command(args: list[str]) -> list[str]:
    command = resolve_codex_runtime()
    command.extend(["-c", "personality=pragmatic"])
    command.extend(args)

    if "exec" in args and "--skip-git-repo-check" not in args and not (WORKSPACE_ROOT / ".git").exists():
        insert_at = command.index("exec") + 1
        command.insert(insert_at, "--skip-git-repo-check")
    return command


def resolve_codex_runtime() -> list[str]:
    bundled = resolve_bundled_runtime()
    if bundled:
        return bundled

    if os.name != "nt":
        system = shutil.which("codex")
        if system:
            return [system]

        bootstrapped = try_bootstrap_runtime()
        if bootstrapped:
            return bootstrapped

        raise FileNotFoundError(
            "No Codex runtime found. Install Node.js + npm and run startup/bootstrap-all.sh to bootstrap this machine."
        )

    appdata = os.environ.get("APPDATA", "")
    preferred = Path(appdata) / "npm" / "codex.cmd"
    if preferred.exists():
        return [str(preferred)]

    result = subprocess.run(
        ["where.exe", "codex.cmd"],
        capture_output=True,
        text=True,
        check=False,
    )
    matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    matches = [match for match in matches if Path(match).resolve() != (ROOT / "Codex.cmd").resolve()]
    if matches:
        return [matches[0]]

    bootstrapped = try_bootstrap_runtime()
    if bootstrapped:
        return bootstrapped

    raise FileNotFoundError("No Codex runtime found. Run startup scripts in the startup folder to bootstrap this machine.")


def resolve_bundled_runtime() -> list[str] | None:
    if os.name == "nt":
        node = STARTUP_DIR / "runtime" / "windows" / "node.exe"
        entry = STARTUP_DIR / "runtime" / "windows" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if node.exists() and entry.exists():
            return [str(node), str(entry)]
    else:
        runtime_name = detect_unix_runtime_name()
        runtime_dir = STARTUP_DIR / "runtime" / runtime_name
        entry = runtime_dir / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if entry.exists():
            node = runtime_dir / "bin" / "node"
            if node.exists():
                return [str(node), str(entry)]
            system_node = shutil.which("node")
            if system_node:
                return [system_node, str(entry)]
    return None


def try_bootstrap_runtime() -> list[str] | None:
    if os.name == "nt":
        node = subprocess.run(["where.exe", "node"], capture_output=True, text=True, check=False)
        npm = subprocess.run(["where.exe", "npm.cmd"], capture_output=True, text=True, check=False)
        if node.returncode != 0 or npm.returncode != 0:
            return None
        runtime_dir = STARTUP_DIR / "runtime" / "windows"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["npm.cmd", "install", "@openai/codex", "--prefix", str(runtime_dir)],
            cwd=str(ROOT),
            check=False,
        )
        return resolve_bundled_runtime()
    runtime_name = detect_unix_runtime_name()
    runtime_dir = STARTUP_DIR / "runtime" / runtime_name
    runtime_dir.mkdir(parents=True, exist_ok=True)
    node = subprocess.run(["bash", "-lc", "command -v node"], capture_output=True, text=True, check=False)
    npm = subprocess.run(["bash", "-lc", "command -v npm"], capture_output=True, text=True, check=False)
    if node.returncode != 0 or npm.returncode != 0:
        return None
    subprocess.run(
        ["bash", "-lc", f"npm install @openai/codex --prefix '{runtime_dir}'"],
        cwd=str(ROOT),
        check=False,
    )
    return resolve_bundled_runtime()


def detect_unix_runtime_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return "macos"
    if "arm" in machine or "aarch64" in machine:
        return "linux-arm"
    return "linux"


def main() -> int:
    ensure_venv()
    ensure_portable_codex_home()
    skip_elevation, forwarded = split_wrapper_args(sys.argv[1:])

    if os.name == "nt" and not skip_elevation and relaunch_as_admin(forwarded):
        print("Relaunched as admin.")
        return 0

    prompt = infer_prompt(forwarded)
    augmentation = AugmentationLayer(ROOT, WORKSPACE_ROOT)
    augmentation.refresh_agents_file(prompt)

    command = build_codex_command(forwarded)
    env = os.environ.copy()
    env["CODEX_HOME"] = str(PORTABLE_CODEX_HOME)
    env["HOME"] = str(PORTABLE_CODEX_HOME)
    proc = subprocess.run(command, cwd=str(WORKSPACE_ROOT), env=env, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
