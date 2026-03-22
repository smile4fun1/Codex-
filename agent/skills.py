from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .executor import ExecutionEngine
from .reasoning import CodexReasoningEngine


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    inputs: list[str]
    tags: list[str]
    keywords: list[str]
    logic: dict[str, Any]
    enabled: bool = True
    version: int = 1


class SkillRegistry:
    def __init__(self, root: Path, executor: ExecutionEngine, reasoning: CodexReasoningEngine) -> None:
        self.root = root
        self.skills_root = root / "skills"
        self.system_dir = self.skills_root / "system"
        self.user_dir = self.skills_root / "user"
        self.registry_path = self.skills_root / "registry.json"
        self.executor = executor
        self.reasoning = reasoning
        self._ensure_registry()
        self.skills = self._load_skills()

    def _ensure_registry(self) -> None:
        self.system_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_skills()
        if not self.registry_path.exists():
            payload = {"system": sorted([path.name for path in self.system_dir.glob("*.json")]), "user": []}
            self.registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _ensure_default_skills(self) -> None:
        defaults = {
            "file_ops.json": {
                "skill_id": "file_ops",
                "name": "File Operations",
                "description": "Read, write, inspect, and organize files safely.",
                "inputs": ["path", "mode", "content"],
                "tags": ["files", "filesystem", "read", "write"],
                "keywords": ["file", "read", "write", "folder", "directory", "save"],
                "logic": {"type": "builtin", "handler": "file_ops"},
                "enabled": True,
                "version": 1,
            },
            "shell_execution.json": {
                "skill_id": "shell_execution",
                "name": "Shell Execution",
                "description": "Execute shell commands with structured safety checks.",
                "inputs": ["command", "cwd"],
                "tags": ["shell", "command", "process"],
                "keywords": ["run", "execute", "shell", "command", "powershell", "cmd"],
                "logic": {"type": "builtin", "handler": "shell_execution"},
                "enabled": True,
                "version": 1,
            },
            "system_inspection.json": {
                "skill_id": "system_inspection",
                "name": "System Inspection",
                "description": "Inspect the OS, tools, environment, repo context, and execution capability.",
                "inputs": ["scope"],
                "tags": ["system", "status", "environment"],
                "keywords": ["inspect", "system", "status", "capabilities", "environment"],
                "logic": {"type": "builtin", "handler": "system_inspection"},
                "enabled": True,
                "version": 1,
            },
            "dependency_install.json": {
                "skill_id": "dependency_install",
                "name": "Dependency Install",
                "description": "Install project or system dependencies through supported package managers.",
                "inputs": ["package", "manager"],
                "tags": ["install", "dependency", "package"],
                "keywords": ["install", "dependency", "package", "pip", "winget", "npm"],
                "logic": {"type": "builtin", "handler": "dependency_install"},
                "enabled": True,
                "version": 1,
            },
            "project_analysis.json": {
                "skill_id": "project_analysis",
                "name": "Project Analysis",
                "description": "Inspect a repository or directory and summarize its structure and signals.",
                "inputs": ["path"],
                "tags": ["project", "repo", "analysis"],
                "keywords": ["project", "repo", "analyze", "analysis", "codebase"],
                "logic": {"type": "builtin", "handler": "project_analysis"},
                "enabled": True,
                "version": 1,
            },
            "code_generation.json": {
                "skill_id": "code_generation",
                "name": "Code Generation",
                "description": "Generate or update source files based on explicit instructions.",
                "inputs": ["path", "instruction"],
                "tags": ["code", "generate", "scaffold"],
                "keywords": ["generate", "create code", "scaffold", "write code"],
                "logic": {"type": "builtin", "handler": "code_generation"},
                "enabled": True,
                "version": 1,
            },
        }
        for filename, payload in defaults.items():
            path = self.system_dir / filename
            if not path.exists():
                path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_skills(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        for directory in [self.system_dir, self.user_dir]:
            for path in directory.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    skill = Skill(**payload)
                    skills[skill.skill_id] = skill
                except Exception:
                    continue
        return skills

    def list_skills(self) -> list[Skill]:
        return sorted(self.skills.values(), key=lambda item: item.skill_id)

    def select(self, prompt: str, limit: int = 3) -> list[Skill]:
        prompt_lower = prompt.lower()
        aliases = {
            "project_analysis": ["scan", "folder", "directory", "summarize", "analyze", "inspect"],
            "system_inspection": ["system", "status", "capabilities", "environment", "tools"],
            "shell_execution": ["run", "execute", "command", "powershell", "cmd"],
        }
        scored: list[tuple[int, Skill]] = []
        for skill in self.skills.values():
            if not skill.enabled:
                continue
            score = sum(3 for word in skill.keywords if word in prompt_lower)
            score += sum(1 for tag in skill.tags if tag in prompt_lower)
            score += sum(2 for alias in aliases.get(skill.skill_id, []) if alias in prompt_lower)
            if score:
                scored.append((score, skill))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [skill for _, skill in scored[:limit]]

    def execute(self, skill: Skill, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        logic_type = skill.logic.get("type")
        if logic_type == "builtin":
            handler = skill.logic.get("handler")
            return self._run_builtin(handler, prompt, context)
        if logic_type == "virtual":
            return self.reasoning.execute_virtual_skill(skill.__dict__, prompt)
        if logic_type == "composite":
            outputs = []
            ok = True
            for child_id in skill.logic.get("skills", []):
                child = self.skills.get(child_id)
                if not child:
                    continue
                result = self.execute(child, prompt, context)
                outputs.append(f"[{child.skill_id}]\n{result['output']}")
                ok = ok and result.get("ok", False)
            return {"ok": ok, "output": "\n\n".join(outputs), "meta": {"composite": skill.skill_id}}
        return {"ok": False, "output": f"Unsupported skill logic for {skill.skill_id}", "meta": {}}

    def create_or_update_user_skill(self, payload: dict[str, Any]) -> Skill:
        existing = self.skills.get(payload["skill_id"])
        payload["version"] = int(payload.get("version", existing.version + 1 if existing else 1))
        path = self.user_dir / f"{payload['skill_id']}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        user_entries = set(registry.get("user", []))
        user_entries.add(path.name)
        registry["user"] = sorted(user_entries)
        self.registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        skill = Skill(**payload)
        self.skills[skill.skill_id] = skill
        return skill

    def _run_builtin(self, handler: str, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        if handler == "system_inspection":
            return self.executor.inspect_system()
        if handler == "project_analysis":
            return self.executor.analyze_project(context.get("path"))
        if handler == "shell_execution":
            command = context.get("command") or self._extract_after_keyword(prompt, ["run", "execute", "command"])
            if not command:
                return {"ok": False, "output": "No command detected.", "meta": {}}
            return self.executor.run_shell(command, cwd=context.get("cwd"))
        if handler == "file_ops":
            if context.get("mode") == "read" and context.get("path"):
                return self.executor.read_file(context["path"])
            if context.get("mode") == "write" and context.get("path"):
                return self.executor.write_file(str(context["path"]), context.get("content", ""), overwrite=context.get("overwrite", False))
            return {"ok": False, "output": "File skill requires a path and mode.", "meta": {}}
        if handler == "dependency_install":
            package = context.get("package")
            if not package:
                return {"ok": False, "output": "No package specified.", "meta": {}}
            return self.executor.install_dependency(package, manager=context.get("manager", "pip"))
        if handler == "code_generation":
            path = context.get("path")
            if not path:
                return {"ok": False, "output": "No output path specified.", "meta": {}}
            return self.executor.generate_code(str(path), context.get("instruction", prompt))
        return {"ok": False, "output": f"Unknown builtin handler: {handler}", "meta": {}}

    @staticmethod
    def _extract_after_keyword(text: str, keywords: list[str]) -> str:
        lowered = text.lower()
        for keyword in keywords:
            index = lowered.find(keyword)
            if index >= 0:
                return text[index + len(keyword):].strip(" :")
        return ""
