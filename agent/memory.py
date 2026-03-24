from __future__ import annotations

import json
import re
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
        self.user_memory_dir = root / "memories"
        self.system_memory_dir = root / "wrapper-memory"
        self.history_dir = self.system_memory_dir / "history"
        self.preferences_path = self.user_memory_dir / "preferences.json"
        self.context_path = self.user_memory_dir / "context.json"
        self.knowledge_path = self.user_memory_dir / "knowledge.md"
        self.tasks_path = self.system_memory_dir / "tasks.json"
        self.loop_state_path = self.system_memory_dir / "loop_state.json"
        self.execution_log_path = self.system_memory_dir / "execution-log.jsonl"
        self.session_state_path = self.system_memory_dir / "session-ingest-state.json"
        self._ensure_files()

    def _ensure_files(self) -> None:
        legacy_memory_dir = self.root / "memory"
        if not self.system_memory_dir.exists() and legacy_memory_dir.exists() and (legacy_memory_dir / "tasks.json").exists():
            legacy_memory_dir.replace(self.system_memory_dir)

        self.user_memory_dir.mkdir(parents=True, exist_ok=True)
        self.system_memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_user_memory()

        if not self.preferences_path.exists():
            self._write_json(
                self.preferences_path,
                {
                    "assistant_name": "Codex",
                    "user_preferences": {
                        "style": "fast, no fluff, structured, execution-focused",
                        "confirm_destructive": True,
                        "assistant_identity": "Codex",
                        "tone": "calm, direct, technically sharp, efficient, slightly informal",
                    },
                    "tags": ["local", "portable", "execution"],
                },
            )
        if not self.context_path.exists():
            self._write_json(self.context_path, {"entries": []})
        if not self.tasks_path.exists():
            self._write_json(self.tasks_path, {"tasks": []})
        if not self.loop_state_path.exists():
            self._write_json(self.loop_state_path, {"last_heartbeat": None, "pid": None})
        if not self.session_state_path.exists():
            self._write_json(self.session_state_path, {"files": {}})
        if not self.knowledge_path.exists():
            self.knowledge_path.write_text(
                "# Knowledge\n\n- Prefer concise plans, explicit risks, and confirmed execution for impactful actions.\n",
                encoding="utf-8",
            )
        self._migrate_legacy_task_records()
        self._prune_context()

    def load_profile(self) -> dict[str, Any]:
        return self._read_json(self.preferences_path, {})

    def load_tasks(self) -> dict[str, Any]:
        payload = self._read_json(self.tasks_path, {"tasks": []})
        tasks = payload.get("tasks", [])
        valid_tasks = [task for task in tasks if self._is_valid_scheduled_task(task)]
        if len(valid_tasks) != len(tasks):
            payload["tasks"] = valid_tasks
            self._write_system_json(self.tasks_path, payload)
        return payload

    def save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        for task in tasks:
            if not self._is_valid_scheduled_task(task):
                raise ValueError(f"Invalid scheduled task payload: {task}")
        self._write_system_json(self.tasks_path, {"tasks": tasks})

    def load_context(self) -> list[dict[str, Any]]:
        payload = self._read_json(self.context_path, {"entries": []})
        entries = payload.get("entries", [])
        return [entry for entry in entries if isinstance(entry, dict) and entry.get("summary")]

    def save_task_result(self, record: TaskRecord, source: str = "manual") -> None:
        payload = asdict(record)
        payload["source"] = source
        history_file = self.history_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        with self.execution_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        if record.success:
            self.remember_context(record.summary, record.tags, source=source)
        self.compress_history_if_needed()

    def remember_context(self, summary: str, tags: list[str], source: str = "manual") -> None:
        if not self._is_high_signal_summary(summary):
            return
        payload = self._read_json(self.context_path, {"entries": []})
        entries = payload.setdefault("entries", [])
        if any(entry.get("summary") == summary for entry in entries):
            return
        entries.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "summary": summary.strip(),
                "tags": sorted({tag for tag in tags if tag}),
                "source": source,
            }
        )
        payload["entries"] = entries[-200:]
        self._write_json(self.context_path, payload)
        self._rewrite_knowledge(payload["entries"])

    def retrieve(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = {part.lower() for part in query.split() if len(part) > 2}
        if not terms:
            return self.load_context()[-limit:]
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in self.load_context():
            haystack = " ".join(
                [
                    item.get("summary", ""),
                    " ".join(item.get("tags", [])),
                    item.get("source", ""),
                ]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def ingest_codex_sessions(self, sessions_root: Path) -> int:
        if not sessions_root.exists():
            return 0

        state = self._read_json(self.session_state_path, {"files": {}})
        known_files = state.setdefault("files", {})
        updated_files: dict[str, dict[str, Any]] = {}
        ingested = 0

        for path in sorted(sessions_root.rglob("*.jsonl")):
            try:
                stat = path.stat()
            except OSError:
                continue

            key = str(path.resolve())
            current_meta = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
            if known_files.get(key) == current_meta:
                updated_files[key] = current_meta
                continue

            ingested += self._ingest_session_file(path)
            updated_files[key] = current_meta

        state["files"] = updated_files
        self._write_system_json(self.session_state_path, state)
        return ingested

    def compress_history_if_needed(self, max_entries: int = 200, keep_recent: int = 120) -> None:
        records = self._load_history_records()
        if len(records) <= max_entries:
            return
        archived = records[:-keep_recent]
        recent = records[-keep_recent:]
        summaries: list[str] = []
        tags: set[str] = set()
        for item in archived:
            summary = item.get("summary", "").strip()
            if summary:
                summaries.append(summary)
            for tag in item.get("tags", []):
                if tag:
                    tags.add(tag)
        if summaries:
            snippet = "; ".join(summaries[:8])
            if len(summaries) > 8:
                snippet += f"; +{len(summaries) - 8} more"
            self.remember_context(f"Compressed task history: {snippet}", sorted(tags)[:8], source="history-compression")
        for path in self.history_dir.glob("*.jsonl"):
            path.unlink(missing_ok=True)
        if recent:
            history_file = self.history_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            with history_file.open("w", encoding="utf-8") as handle:
                for item in recent:
                    handle.write(json.dumps(item, ensure_ascii=True) + "\n")
        self.execution_log_path.write_text("", encoding="utf-8")
        with self.execution_log_path.open("a", encoding="utf-8") as handle:
            for item in recent:
                handle.write(json.dumps(item, ensure_ascii=True) + "\n")

    @staticmethod
    def summarize(prompt: str, outcome: str, tags: list[str]) -> str:
        prompt_snippet = " ".join(prompt.strip().split())[:80]
        outcome_snippet = " ".join(outcome.strip().split())[:100]
        return f"{prompt_snippet} -> {outcome_snippet} ({', '.join(tags[:4])})"

    def _migrate_legacy_user_memory(self) -> None:
        legacy_profile = self.system_memory_dir / "profile.json"
        if legacy_profile.exists():
            if not self.preferences_path.exists():
                self.preferences_path.write_bytes(legacy_profile.read_bytes())
            if self.preferences_path.exists():
                legacy_profile.unlink(missing_ok=True)
        legacy_knowledge = self.system_memory_dir / "knowledge.md"
        if legacy_knowledge.exists():
            if not self.knowledge_path.exists():
                self.knowledge_path.write_bytes(legacy_knowledge.read_bytes())
            if self.knowledge_path.exists():
                legacy_knowledge.unlink(missing_ok=True)

    def _migrate_legacy_task_records(self) -> None:
        payload = self._read_json(self.tasks_path, {"tasks": []})
        tasks = payload.get("tasks", [])
        if not tasks:
            return
        if all(self._is_valid_scheduled_task(task) for task in tasks):
            return
        legacy_records = [task for task in tasks if isinstance(task, dict) and task.get("timestamp") and task.get("prompt")]
        if not legacy_records:
            self._write_system_json(self.tasks_path, {"tasks": []})
            return
        history_file = self.history_dir / "migrated-history.jsonl"
        with history_file.open("a", encoding="utf-8") as handle:
            for item in legacy_records:
                handle.write(json.dumps(item, ensure_ascii=True) + "\n")
                if item.get("success") and item.get("summary"):
                    self.remember_context(item["summary"], item.get("tags", []), source="legacy-task-history")
        self._write_system_json(self.tasks_path, {"tasks": []})

    def _load_history_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.history_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
        return records

    def _rewrite_knowledge(self, entries: list[dict[str, Any]]) -> None:
        lines = ["# Knowledge", ""]
        for entry in entries[-40:]:
            lines.append(f"- {entry.get('summary', '').strip()} [tags: {', '.join(entry.get('tags', [])[:5])}]")
        self.knowledge_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _prune_context(self) -> None:
        payload = self._read_json(self.context_path, {"entries": []})
        entries = [entry for entry in payload.get("entries", []) if self._is_high_signal_summary(entry.get("summary", ""))]
        payload["entries"] = entries[-200:]
        self._write_json(self.context_path, payload)
        self._rewrite_knowledge(payload["entries"])

    @staticmethod
    def _is_high_signal_summary(summary: str) -> bool:
        normalized = " ".join(summary.strip().lower().split())
        if len(normalized) < 30:
            return False
        banned = [
            "i do not have enough confidence",
            "this looks like a conversational request",
            "conversational than actionable",
            "who are you",
            "what can you do",
            "what is this file",
            "say what you want done",
            "hello",
            "hi.",
            "yo, what's up",
            "ask directly",
            "go on.",
            "fuck you",
        ]
        return not any(fragment in normalized for fragment in banned)

    @staticmethod
    def _is_valid_scheduled_task(task: dict[str, Any]) -> bool:
        required = {"id", "type", "schedule", "prompt", "enabled"}
        if not isinstance(task, dict) or not required.issubset(task):
            return False
        if task.get("type") not in {"check", "execute", "draft", "notify"}:
            return False
        schedule = str(task.get("schedule", ""))
        if not (schedule.startswith("interval:") or schedule.startswith("daily:")):
            return False
        return True

    @staticmethod
    def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def _write_system_json(self, path: Path, payload: dict[str, Any]) -> None:
        if path.parent != self.system_memory_dir:
            raise ValueError(f"System state write blocked outside wrapper-memory: {path}")
        self._write_json(path, payload)

    def _ingest_session_file(self, path: Path) -> int:
        ingested = 0
        current_user: str | None = None

        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            user_message = self._extract_user_message(payload)
            if user_message:
                current_user = user_message
                continue

            assistant_message = self._extract_final_answer(payload)
            if not assistant_message or not current_user:
                continue

            summary = self.summarize(current_user, assistant_message, ["codex-session"])
            if self._is_high_signal_summary(summary):
                tags = self._derive_session_tags(current_user, assistant_message)
                self.remember_context(summary, tags, source=f"codex-session:{path.name}")
                ingested += 1
            current_user = None

        return ingested

    @staticmethod
    def _extract_user_message(payload: dict[str, Any]) -> str | None:
        if payload.get("type") == "event_msg":
            event = payload.get("payload", {})
            if event.get("type") == "user_message":
                return str(event.get("message", "")).strip() or None

        if payload.get("type") == "response_item":
            item = payload.get("payload", {})
            if item.get("type") != "message" or item.get("role") != "user":
                return None
            texts = [
                str(part.get("text", "")).strip()
                for part in item.get("content", [])
                if isinstance(part, dict) and part.get("type") == "input_text" and str(part.get("text", "")).strip()
            ]
            return "\n".join(texts).strip() or None
        return None

    @staticmethod
    def _extract_final_answer(payload: dict[str, Any]) -> str | None:
        if payload.get("type") != "response_item":
            return None
        item = payload.get("payload", {})
        if item.get("type") != "message" or item.get("role") != "assistant":
            return None
        if item.get("phase") != "final_answer":
            return None
        texts = [
            str(part.get("text", "")).strip()
            for part in item.get("content", [])
            if isinstance(part, dict) and part.get("type") == "output_text" and str(part.get("text", "")).strip()
        ]
        return "\n".join(texts).strip() or None

    @staticmethod
    def _derive_session_tags(prompt: str, outcome: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9][a-z0-9_-]{2,}", f"{prompt} {outcome}".lower())
        tags = ["codex-session"]
        for token in tokens:
            if token not in tags:
                tags.append(token)
            if len(tags) >= 8:
                break
        return tags
