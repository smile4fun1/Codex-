from __future__ import annotations

import json
import os
import platform
import shutil
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SelectedSkill:
    skill_id: str
    name: str
    description: str
    tags: list[str]
    keywords: list[str]


class AugmentationLayer:
    def __init__(self, app_root: Path, workspace_root: Path) -> None:
        self.app_root = app_root
        self.workspace_root = workspace_root
        self.system_memory_dir = app_root / "wrapper-memory"
        self.user_memory_dir = app_root / "memories"
        self.skills_dir = app_root / "wrapper-skills"
        self.agents_path = workspace_root / "AGENTS.md"
        self.profile_path = self.user_memory_dir / "preferences.json"
        self.context_path = self.user_memory_dir / "context.json"
        self.knowledge_path = self.user_memory_dir / "knowledge.md"
        self.history_dir = self.system_memory_dir / "history"
        self._ensure_files()

    def refresh_agents_file(self, prompt: str | None = None) -> str:
        profile = self._load_json(self.profile_path, {})
        context_entries = self._load_json(self.context_path, {"entries": []}).get("entries", [])
        skills = self._load_skills()
        environment = self._scan_environment()
        memory_hits = self._select_memory(prompt or "", context_entries)
        skill_hits = self._select_skills(prompt or "", skills)
        content = self._render_agents(profile, memory_hits, skill_hits, environment)
        self.agents_path.write_text(content, encoding="utf-8")
        self._log_session_seed(prompt or "", memory_hits, skill_hits)
        return content

    def _ensure_files(self) -> None:
        legacy_memory_dir = self.app_root / "memory"
        legacy_skills_dir = self.app_root / "skills"
        if not self.system_memory_dir.exists() and legacy_memory_dir.exists() and (legacy_memory_dir / "tasks.json").exists():
            legacy_memory_dir.replace(self.system_memory_dir)
        if not self.skills_dir.exists() and legacy_skills_dir.exists() and (legacy_skills_dir / "registry.json").exists():
            legacy_skills_dir.replace(self.skills_dir)

        self.system_memory_dir.mkdir(parents=True, exist_ok=True)
        self.user_memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        legacy_profile = self.system_memory_dir / "profile.json"
        legacy_knowledge = self.system_memory_dir / "knowledge.md"
        if legacy_profile.exists():
            if not self.profile_path.exists():
                self.profile_path.write_bytes(legacy_profile.read_bytes())
            if self.profile_path.exists():
                legacy_profile.unlink(missing_ok=True)
        if legacy_knowledge.exists():
            if not self.knowledge_path.exists():
                self.knowledge_path.write_bytes(legacy_knowledge.read_bytes())
            if self.knowledge_path.exists():
                legacy_knowledge.unlink(missing_ok=True)
        default_profile = {
            "assistant_name": "Codex",
            "user_preferences": {
                "style": "fast, minimal fluff, practical",
                "tone": "calm, direct, technically sharp, slightly informal",
                "assistant_identity": "Codex",
            },
        }
        if not self.profile_path.exists():
            self.profile_path.write_text(json.dumps(default_profile, indent=2), encoding="utf-8")
        else:
            profile = self._load_json(self.profile_path, default_profile)
            profile["assistant_name"] = "Codex"
            prefs = profile.setdefault("user_preferences", {})
            prefs["assistant_identity"] = "Codex"
            prefs.setdefault("style", "fast, minimal fluff, practical")
            prefs.setdefault("tone", "calm, direct, technically sharp, slightly informal")
            self.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        if not self.context_path.exists():
            self.context_path.write_text(json.dumps({"entries": []}, indent=2), encoding="utf-8")
        if not self.knowledge_path.exists():
            self.knowledge_path.write_text(
                "# Knowledge\n\n- Prefer direct, minimal-fluff, technical responses.\n",
                encoding="utf-8",
            )

    def _select_memory(self, prompt: str, entries: list[dict[str, Any]]) -> list[str]:
        banned_fragments = [
            "i do not have enough confidence",
            "this looks like a conversational request",
            "rephrase with a concrete",
            "this is not a chatbot",
            "iâ",
        ]
        knowledge_lines = [
            line[2:].strip()
            for line in self.knowledge_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith("- ")
        ]
        if not prompt.strip():
            recent = [entry.get("summary", "") for entry in entries[-3:]] + knowledge_lines[-2:]
            return [item for item in recent if item and not any(fragment in item.lower() for fragment in banned_fragments)][:2]
        terms = {part.lower() for part in prompt.split() if len(part) > 2}
        if len(terms) < 2:
            return []
        scored: list[tuple[int, str]] = []
        for entry in entries:
            summary = entry.get("summary", "")
            if any(fragment in summary.lower() for fragment in banned_fragments):
                continue
            haystack = " ".join(
                [
                    summary,
                    " ".join(entry.get("tags", [])),
                    entry.get("source", ""),
                ]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score >= 2 and summary:
                scored.append((score, summary))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [summary for _, summary in scored[:3]]

    def _load_skills(self) -> list[SelectedSkill]:
        loaded: list[SelectedSkill] = []
        for directory in [self.skills_dir / "user", self.skills_dir / "system"]:
            if not directory.exists():
                continue
            for path in directory.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    loaded.append(
                        SelectedSkill(
                            skill_id=payload["skill_id"],
                            name=payload["name"],
                            description=payload.get("description", ""),
                            tags=payload.get("tags", []),
                            keywords=payload.get("keywords", []),
                        )
                    )
                except Exception:
                    continue
        return loaded

    def _select_skills(self, prompt: str, skills: list[SelectedSkill]) -> list[SelectedSkill]:
        if not prompt.strip():
            return [skill for skill in skills if skill.skill_id in {"structured_breakdown"}][:2]
        lowered = prompt.lower()
        scored: list[tuple[int, SelectedSkill]] = []
        for skill in skills:
            score = sum(2 for keyword in skill.keywords if keyword in lowered)
            score += sum(1 for tag in skill.tags if tag in lowered)
            if score:
                scored.append((score, skill))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [skill for _, skill in scored[:4]]

    def _render_agents(
        self,
        profile: dict[str, Any],
        memory_hits: list[str],
        skill_hits: list[SelectedSkill],
        environment: dict[str, Any],
    ) -> str:
        preferred_style = profile.get("user_preferences", {}).get("style", "fast, direct, minimal fluff, practical")
        preferred_tone = profile.get("user_preferences", {}).get("tone", "calm, direct, technically sharp, slightly informal")
        lines = [
            "# Codex Portable Wrapper",
            "",
            "You are Codex running inside a portable wrapper.",
            "Keep the normal Codex CLI experience intact.",
            "Respond naturally, directly, and with minimal fluff.",
            "",
            "## Preferences",
            f"- Style: {preferred_style}",
            f"- Tone: {preferred_tone}",
            "- Default behavior: move the task forward with the simplest correct action.",
        ]

        lines.extend(
            [
                "",
                "## Current Environment",
                f"- Workspace: {environment['workspace']}",
                f"- Admin: {'yes' if environment['admin'] else 'no'}",
                f"- Repo: {'yes' if environment['repo'] else 'no'}",
                f"- Python: {environment['python']}",
                f"- Tools: {', '.join(environment['tools']) if environment['tools'] else 'none detected'}",
                f"- Nearby: {', '.join(environment['nearby']) if environment['nearby'] else 'empty'}",
            ]
        )

        if memory_hits:
            lines.extend(["", "## Relevant Memory"])
            lines.extend([f"- {item}" for item in memory_hits])

        if skill_hits:
            lines.extend(["", "## Optional Local Helpers"])
            for skill in skill_hits:
                lines.append(f"- `{skill.skill_id}`: {skill.description}")

        lines.extend(
            [
                "",
                "## Guidance",
                "- Preserve normal Codex slash commands and chat flow.",
                "- Use the optional helper skills only when they clearly help; otherwise just solve the task normally.",
                "- Add short practical improvements when they are obvious and useful.",
                "- If the user opens with a greeting like hi/hello/yo, reply with a quick friendly status of Codex plus the current environment instead of a generic greeting.",
            ]
        )
        return "\n".join(lines) + "\n"

    def _scan_environment(self) -> dict[str, Any]:
        tools = []
        for name in ["codex", "git", "rg", "python", "node", "npm"]:
            if shutil.which(name) or shutil.which(f"{name}.cmd"):
                tools.append(name)
        nearby = []
        try:
            for item in sorted(self.workspace_root.iterdir(), key=lambda path: path.name.lower())[:8]:
                nearby.append(item.name)
        except Exception:
            nearby = []
        return {
            "workspace": str(self.workspace_root),
            "admin": self._is_admin(),
            "repo": (self.workspace_root / ".git").exists(),
            "python": platform.python_version(),
            "tools": tools,
            "nearby": nearby,
            "cwd": os.getcwd(),
        }

    @staticmethod
    def _is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _log_session_seed(self, prompt: str, memory_hits: list[str], skill_hits: list[SelectedSkill]) -> None:
        if not prompt.strip():
            return
        payload = {
            "prompt": prompt,
            "memory_hits": memory_hits,
            "skill_hits": [skill.skill_id for skill in skill_hits],
        }
        path = self.history_dir / "wrapper_sessions.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    @staticmethod
    def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
