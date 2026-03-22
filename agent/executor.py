from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .safety import SafetyLayer


class ExecutionEngine:
    def __init__(self, root: Path, safety: SafetyLayer, confirm: Callable[[str], bool]) -> None:
        self.root = root
        self.safety = safety
        self.confirm = confirm

    def run_shell(self, command: str, cwd: str | None = None) -> dict[str, Any]:
        decision = self.safety.assess_command(command)
        if decision.needs_confirmation and not self.confirm(
            f"Command flagged ({'; '.join(decision.reasons)}). Execute anyway?"
        ):
            return {"ok": False, "output": "Command cancelled by user.", "meta": {"command": command}}

        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "ok": proc.returncode == 0,
            "output": output.strip(),
            "meta": {"command": command, "returncode": proc.returncode},
        }

    def read_file(self, path: str) -> dict[str, Any]:
        file_path = Path(path).expanduser().resolve()
        content = file_path.read_text(encoding="utf-8", errors="replace")
        safety = self.safety.assess_text(content, source=f"file:{file_path.name}")
        note = ""
        if safety.reasons:
            note = f"Safety note: {'; '.join(safety.reasons)}\n"
        return {"ok": True, "output": note + content[:12000], "meta": {"path": str(file_path)}}

    def write_file(self, path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        file_path = Path(path).expanduser().resolve()
        destructive = file_path.exists() and overwrite
        if destructive and not self.confirm(f"Overwrite existing file {file_path}?"):
            return {"ok": False, "output": "Write cancelled by user.", "meta": {"path": str(file_path)}}
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if file_path.exists() and not overwrite:
            return {"ok": False, "output": "File exists; set overwrite to true.", "meta": {"path": str(file_path)}}
        file_path.write_text(content, encoding="utf-8")
        return {"ok": True, "output": f"Wrote {file_path}", "meta": {"path": str(file_path)}}

    def inspect_system(self) -> dict[str, Any]:
        tools = {}
        for name in ["python", "py", "git", "rg", "node", "npm", "code", "powershell"]:
            tools[name] = shutil.which(name)
        repo_root = self._detect_repo_root(Path.cwd())
        payload = {
            "os": platform.platform(),
            "hostname": platform.node(),
            "python": platform.python_version(),
            "admin": self._is_admin(),
            "cwd": str(Path.cwd()),
            "repo_root": str(repo_root) if repo_root else None,
            "tools": tools,
            "env_preview": sorted(list(os.environ.keys()))[:20],
        }
        return {"ok": True, "output": json.dumps(payload, indent=2), "meta": payload}

    def install_dependency(self, package: str, manager: str = "pip") -> dict[str, Any]:
        command = {
            "pip": f"python -m pip install {package}",
            "winget": f"winget install --id {package} --accept-package-agreements --accept-source-agreements",
            "npm": f"npm install -g {package}",
        }.get(manager)
        if not command:
            return {"ok": False, "output": f"Unsupported manager: {manager}", "meta": {"package": package}}
        return self.run_shell(command)

    def analyze_project(self, path: str | None = None) -> dict[str, Any]:
        target = Path(path or Path.cwd()).resolve()
        summary = {
            "path": str(target),
            "exists": target.exists(),
            "files": [],
            "indicators": {},
        }
        if not target.exists():
            return {"ok": False, "output": json.dumps(summary, indent=2), "meta": summary}

        summary["files"] = [str(item.name) for item in list(target.iterdir())[:25]]
        indicators = {
            "git": (target / ".git").exists(),
            "python": any(target.glob("*.py")) or (target / "pyproject.toml").exists(),
            "node": (target / "package.json").exists(),
            "tests": any(target.glob("test*")) or (target / "tests").exists(),
        }
        summary["indicators"] = indicators
        return {"ok": True, "output": json.dumps(summary, indent=2), "meta": summary}

    def generate_code(self, path: str, instruction: str) -> dict[str, Any]:
        file_path = Path(path).expanduser().resolve()
        if file_path.exists() and not self.confirm(f"Update generated code in {file_path}?"):
            return {"ok": False, "output": "Generation cancelled by user.", "meta": {"path": str(file_path)}}
        content = (
            '"""Generated by Codex."""\n\n'
            f"# Instruction: {instruction}\n"
            "def main() -> None:\n"
            '    print("Replace this scaffold with task-specific logic.")\n'
        )
        return self.write_file(str(file_path), content, overwrite=True)

    @staticmethod
    def _detect_repo_root(start: Path) -> Path | None:
        current = start
        while True:
            if (current / ".git").exists():
                return current
            if current.parent == current:
                return None
            current = current.parent

    @staticmethod
    def _is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
