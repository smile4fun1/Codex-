from __future__ import annotations

import ctypes
import os
import platform
import shutil
from pathlib import Path


def detect_runtime_profile(app_root: Path, workspace_root: Path) -> dict[str, object]:
    system_name = platform.system()
    machine = platform.machine() or "unknown"
    system_key = system_name.lower()
    machine_key = machine.lower()
    runtime_name = _detect_runtime_name(system_key, machine_key)
    runtime_dir = app_root / "startup" / "runtime" / runtime_name

    bundled_runtime = _bundled_runtime_present(runtime_dir, system_key)
    system_codex = shutil.which("codex") or shutil.which("codex.cmd")
    runtime_mode = "bundled" if bundled_runtime else "system" if system_codex else "bootstrap-needed"

    tools = []
    for name in ["codex", "git", "rg", "python", "node", "npm"]:
        if shutil.which(name) or shutil.which(f"{name}.cmd"):
            tools.append(name)

    nearby = []
    try:
        for item in sorted(workspace_root.iterdir(), key=lambda path: path.name.lower())[:8]:
            nearby.append(item.name)
    except Exception:
        nearby = []

    return {
        "workspace": str(workspace_root),
        "cwd": os.getcwd(),
        "platform": system_name,
        "architecture": machine,
        "runtime_name": runtime_name,
        "runtime_mode": runtime_mode,
        "runtime_dir": str(runtime_dir),
        "admin": is_admin(),
        "repo": (workspace_root / ".git").exists(),
        "python": platform.python_version(),
        "tools": tools,
        "nearby": nearby,
    }


def render_environment_status(environment: dict[str, object]) -> str:
    workspace = str(environment.get("workspace", "?"))
    platform_name = str(environment.get("platform", "?"))
    architecture = str(environment.get("architecture", "?"))
    runtime_mode = str(environment.get("runtime_mode", "?"))
    runtime_name = str(environment.get("runtime_name", "?"))
    admin = "admin" if bool(environment.get("admin")) else "user"
    repo = "repo" if bool(environment.get("repo")) else "no-repo"
    return f"{platform_name} {architecture} | runtime: {runtime_mode}/{runtime_name} | {admin} | {repo} | {workspace}"


def is_admin() -> bool:
    if os.name != "nt":
        geteuid = getattr(os, "geteuid", None)
        return bool(geteuid and geteuid() == 0)
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _detect_runtime_name(system_key: str, machine_key: str) -> str:
    if system_key == "darwin":
        return "macos"
    if system_key == "windows":
        return "windows"
    if "arm" in machine_key or "aarch64" in machine_key:
        return "linux-arm"
    return "linux"


def _bundled_runtime_present(runtime_dir: Path, system_key: str) -> bool:
    if system_key == "windows":
        node = runtime_dir / "node.exe"
    else:
        node = runtime_dir / "bin" / "node"
    entry = runtime_dir / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    return node.exists() and entry.exists()
