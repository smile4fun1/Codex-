from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import time
import tomllib
import venv
from pathlib import Path

from agent.augmentation import AugmentationLayer
from agent.memory import MemoryManager
from wrapper.skills import UserSkillIndex
from wrapper.git_persistence import GitPersistence


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
    MemoryManager(ROOT)
    UserSkillIndex(ROOT).build()


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


def handle_wrapper_command(args: list[str]) -> int | None:
    if not args:
        return None
    if args[0] not in {"/skills-clean", "skills-clean"}:
        return None
    result = UserSkillIndex(ROOT).clean()
    print(f"skills cleaned: {result['total']}")
    for item in result["cleaned"]:
        print(f"- {item['skill_id']}: {', '.join(item['issues'])}")
    return 0


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


def load_wrapper_config() -> dict:
    config_path = ROOT / "config.toml"
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def load_loop_interval() -> int:
    wrapper = load_wrapper_config().get("wrapper", {})
    if isinstance(wrapper, dict):
        return int(wrapper.get("heartbeat_interval", 60) or 60)
    return 60


def load_memory_sync_interval() -> int:
    wrapper = load_wrapper_config().get("wrapper", {})
    if isinstance(wrapper, dict):
        return max(int(wrapper.get("memory_sync_interval", 15) or 15), 5)
    return 15


def should_start_heartbeat_loop() -> bool:
    if os.environ.get("CODEX_WRAPPER_LOOP_ACTIVE") == "1":
        return False
    try:
        tasks_path = ROOT / "wrapper-memory" / "tasks.json"
        if not tasks_path.exists():
            return False
        import json

        payload = json.loads(tasks_path.read_text(encoding="utf-8"))
        tasks = payload.get("tasks", [])
        return any(task.get("enabled", True) for task in tasks if isinstance(task, dict))
    except Exception:
        return False


def heartbeat_loop_running(interval: int) -> bool:
    try:
        import json

        state_path = ROOT / "wrapper-memory" / "loop_state.json"
        if not state_path.exists():
            return False
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        last_heartbeat = payload.get("last_heartbeat")
        if not last_heartbeat:
            return False
        from datetime import datetime

        age = time.time() - datetime.fromisoformat(last_heartbeat).timestamp()
        return age < max(interval * 2, 120)
    except Exception:
        return False


def maybe_start_heartbeat_loop() -> None:
    if not should_start_heartbeat_loop():
        return
    interval = load_loop_interval()
    if heartbeat_loop_running(interval):
        return
    command = [sys.executable, str(ROOT / "wrapper" / "loop.py"), "--interval", str(interval)]
    kwargs: dict[str, object] = {
        "cwd": str(ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": {**os.environ, "CODEX_WRAPPER_LOOP_ACTIVE": "1"},
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def run_codex_with_live_persistence(
    command: list[str],
    env: dict[str, str],
    memory: MemoryManager,
    git_persistence: GitPersistence,
    sessions_root: Path,
) -> int:
    sync_interval = load_memory_sync_interval()
    proc = subprocess.Popen(command, cwd=str(WORKSPACE_ROOT), env=env)

    while True:
        try:
            returncode = proc.wait(timeout=sync_interval)
            break
        except subprocess.TimeoutExpired:
            memory.ingest_codex_sessions(sessions_root)
            git_persistence.sync("live memory checkpoint")

    memory.ingest_codex_sessions(sessions_root)
    git_persistence.sync("memories and skills")
    return returncode


def main() -> int:
    ensure_venv()
    ensure_portable_codex_home()
    memory = MemoryManager(ROOT)
    git_persistence = GitPersistence(ROOT)
    skip_elevation, forwarded = split_wrapper_args(sys.argv[1:])
    wrapper_result = handle_wrapper_command(forwarded)
    if wrapper_result is not None:
        git_persistence.sync("wrapper cleanup")
        return wrapper_result

    if os.name == "nt" and not skip_elevation and relaunch_as_admin(forwarded):
        print("Relaunched as admin.")
        return 0

    sessions_root = PORTABLE_CODEX_HOME / "sessions"
    memory.ingest_codex_sessions(sessions_root)
    prompt = infer_prompt(forwarded)
    augmentation = AugmentationLayer(ROOT, WORKSPACE_ROOT)
    augmentation.refresh_agents_file(prompt)
    maybe_start_heartbeat_loop()

    command = build_codex_command(forwarded)
    env = os.environ.copy()
    env["CODEX_HOME"] = str(PORTABLE_CODEX_HOME)
    env["HOME"] = str(PORTABLE_CODEX_HOME)
    return run_codex_with_live_persistence(command, env, memory, git_persistence, sessions_root)


if __name__ == "__main__":
    raise SystemExit(main())
