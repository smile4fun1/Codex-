from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path


class GitPersistence:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.git_exe = shutil.which("git")
        self.scopes = ["memories", "skills", "wrapper-memory/tasks.json"]

    def sync(self, reason: str = "wrapper state") -> bool:
        if not self._enabled():
            return False
        if not self._has_identity():
            return False

        changed = self._changed_paths()
        if not changed:
            return False

        add = self._run_git(["add", "-A", "--", *changed])
        if add.returncode != 0:
            return False

        message = f"wrapper: persist {reason} @ {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        commit = self._run_git(["commit", "--quiet", "--only", "-m", message, "--", *changed])
        return commit.returncode == 0

    def _enabled(self) -> bool:
        if os.environ.get("CODEX_DISABLE_GIT_PERSISTENCE", "").strip().lower() in {"1", "true", "yes"}:
            return False
        if not self.git_exe or not (self.root / ".git").exists():
            return False
        if not self._inside_work_tree():
            return False

        config_path = self.root / "config.toml"
        if not config_path.exists():
            return True
        try:
            with config_path.open("rb") as handle:
                config = tomllib.load(handle)
        except Exception:
            return True

        wrapper = config.get("wrapper", {})
        if not isinstance(wrapper, dict):
            return True
        persistence = wrapper.get("git_persistence", {})
        if isinstance(persistence, bool):
            return persistence
        if isinstance(persistence, dict):
            enabled = persistence.get("enabled")
            if enabled is False:
                return False
        return True

    def _inside_work_tree(self) -> bool:
        probe = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return probe.returncode == 0 and probe.stdout.strip() == "true"

    def _has_identity(self) -> bool:
        name = self._run_git(["config", "--get", "user.name"])
        email = self._run_git(["config", "--get", "user.email"])
        return bool(name.stdout.strip() and email.stdout.strip())

    def _changed_paths(self) -> list[str]:
        status = self._run_git(["status", "--porcelain=v1", "--untracked-files=all", "--", *self.scopes])
        if status.returncode != 0:
            return []

        paths: list[str] = []
        for raw in status.stdout.splitlines():
            line = raw.rstrip()
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            normalized = path.replace("\\", "/")
            if normalized not in paths:
                paths.append(normalized)
        return paths

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.git_exe or "git", *args],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            check=False,
        )
