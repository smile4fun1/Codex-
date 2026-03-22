from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TaskRecord:
    timestamp: str
    prompt: str
    plan: list[str]
    outcome: str
    success: bool
    skills: list[str]
    tags: list[str]
    summary: str


class MemoryManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.memory_dir = root / "memory"
        self.history_dir = self.memory_dir / "history"
        self.profile_path = self.memory_dir / "profile.json"
        self.tasks_path = self.memory_dir / "tasks.json"
        self.knowledge_path = self.memory_dir / "knowledge.md"
        self._ensure_files()

    def _ensure_files(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        if not self.profile_path.exists():
            self._write_json(
                self.profile_path,
                {
                    "assistant_name": "Codex",
                    "user_preferences": {
                        "style": "fast, no fluff, structured, execution-focused",
                        "confirm_destructive": True,
                        "assistant_identity": "Codex",
                        "tone": "calm, direct, technically sharp, efficient, slightly informal",
                    },
                    "tags": ["local", "windows", "execution"],
                },
            )
        if not self.tasks_path.exists():
            self._write_json(self.tasks_path, {"tasks": []})
        if not self.knowledge_path.exists():
            self.knowledge_path.write_text(
                "# Knowledge\n\n- Prefer concise plans, explicit risks, and confirmed execution for impactful actions.\n",
                encoding="utf-8",
            )

    def load_profile(self) -> dict[str, Any]:
        return self._read_json(self.profile_path, {})

    def load_tasks(self) -> dict[str, Any]:
        return self._read_json(self.tasks_path, {"tasks": []})

    def save_task(self, record: TaskRecord) -> None:
        payload = self.load_tasks()
        tasks = payload.setdefault("tasks", [])
        tasks.append(asdict(record))
        payload["tasks"] = tasks[-100:]
        self._write_json(self.tasks_path, payload)

        history_file = self.history_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")

        self._append_knowledge(record)

    def retrieve(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = {part.lower() for part in query.split() if len(part) > 2}
        items = self.load_tasks().get("tasks", [])
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            haystack = " ".join(
                [
                    item.get("prompt", ""),
                    item.get("summary", ""),
                    " ".join(item.get("tags", [])),
                    " ".join(item.get("skills", [])),
                ]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def _append_knowledge(self, record: TaskRecord) -> None:
        existing = self.knowledge_path.read_text(encoding="utf-8")
        line = f"- {record.timestamp}: {record.summary} [tags: {', '.join(record.tags[:5])}]"
        lines = [entry for entry in existing.splitlines() if entry.strip()]
        if line not in lines:
            lines.append(line)
        trimmed = lines[:1] + lines[-40:]
        self.knowledge_path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")

    @staticmethod
    def summarize(prompt: str, outcome: str, tags: list[str]) -> str:
        prompt_snippet = " ".join(prompt.strip().split())[:80]
        outcome_snippet = " ".join(outcome.strip().split())[:100]
        return f"{prompt_snippet} -> {outcome_snippet} ({', '.join(tags[:4])})"

    @staticmethod
    def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
