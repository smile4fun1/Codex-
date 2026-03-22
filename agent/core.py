from __future__ import annotations

import ctypes
import json
import os
from datetime import datetime
from pathlib import Path

from .executor import ExecutionEngine
from .memory import MemoryManager, TaskRecord
from .planner import Plan, Planner
from .reasoning import CodexReasoningEngine
from .safety import SafetyLayer
from .self_improve import SelfImprover
from .skills import SkillRegistry


class CodexWrapperAgent:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.safety = SafetyLayer()
        self.memory = MemoryManager(root)
        self.reasoning = CodexReasoningEngine()
        self.executor = ExecutionEngine(root, self.safety, self._confirm)
        self.skills = SkillRegistry(root, self.executor, self.reasoning)
        self.planner = Planner(self.skills, self.safety)
        self.self_improve = SelfImprover(root, self.skills)
        self.profile = self.memory.load_profile()

    def run_cli(self) -> None:
        print("Codex ready. Commands: /memory /skills /status /improve /exit")
        while True:
            try:
                user_input = input("codex> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return

            if not user_input:
                continue
            if user_input in {"/exit", "/quit"}:
                print("Exiting.")
                return

            response = self.handle_input(user_input)
            if response:
                print(response)

    def handle_input(self, user_input: str) -> str:
        if user_input.startswith("/"):
            return self._handle_command(user_input)

        memory_hits = self.memory.retrieve(user_input)
        plan = self.planner.build_plan(user_input, memory_hits)
        if plan.mode == "conversation":
            outcome = self._respond_conversationally(user_input, memory_hits)
            self._record(user_input, plan, outcome, True)
            return outcome

        if plan.mode == "hybrid":
            print(self.reasoning.explain_hybrid(user_input))
        print(self._render_plan(plan))

        if plan.needs_confirmation and not self._confirm("Plan contains risky actions or content. Continue?"):
            return "Cancelled."

        if not plan.skills:
            result = self.reasoning.solve(user_input, memory_hits)
            notes = self.self_improve.promote_reasoning_skill(result.skill_payload)
            outcome = result.output
            if notes:
                outcome = outcome + "\n\n[Skill Extraction]\n" + "\n".join(notes)
            self._record(user_input, plan, outcome, True)
            return outcome

        outputs = []
        success = True
        for skill in plan.skills:
            result = self.skills.execute(skill, user_input, dict(plan.context))
            outputs.append(f"[{skill.name}]\n{result['output']}")
            success = success and result.get("ok", False)

        outcome = "\n\n".join(outputs)
        if plan.mode == "hybrid":
            outcome = outcome + "\n\n" + self.reasoning.synthesize_hybrid(user_input, outputs)
        outcome = self._enhance_outcome(user_input, outcome)
        improve_notes = self.self_improve.review(user_input, [skill.skill_id for skill in plan.skills], success, outcome)
        if improve_notes:
            outcome = outcome + "\n\n[Self-Improve]\n" + "\n".join(improve_notes)
        self._record(user_input, plan, outcome, success)
        return outcome

    def _handle_command(self, command: str) -> str:
        if command == "/memory":
            tasks = self.memory.load_tasks().get("tasks", [])[-5:]
            return json.dumps(tasks, indent=2)
        if command == "/skills":
            payload = [
                {
                    "skill_id": skill.skill_id,
                    "name": skill.name,
                    "tags": skill.tags,
                    "logic": skill.logic,
                    "version": skill.version,
                }
                for skill in self.skills.list_skills()
            ]
            return json.dumps(payload, indent=2)
        if command == "/status":
            status = {
                "agent": self.profile.get("user_preferences", {}).get("assistant_identity", "Codex"),
                "cwd": os.getcwd(),
                "admin": self._is_admin(),
                "memory_tasks": len(self.memory.load_tasks().get("tasks", [])),
                "skills": len(self.skills.skills),
            }
            return json.dumps(status, indent=2)
        if command == "/improve":
            notes = self.self_improve.review("manual improve trigger", [], True, "manual review")
            return "\n".join(notes) if notes else "No new improvement generated."
        return "Unknown command."

    def _render_plan(self, plan: Plan) -> str:
        lines = ["PLAN:"]
        lines.extend([f"{index}. {step}" for index, step in enumerate(plan.steps, start=1)])
        if plan.skills:
            lines.append(f"Skills: {', '.join(skill.skill_id for skill in plan.skills)}")
        if plan.risks:
            lines.append(f"Risks: {'; '.join(plan.risks)}")
        return "\n".join(lines)

    def _respond_conversationally(self, prompt: str, memory_hits: list[dict[str, str]]) -> str:
        lowered = prompt.lower().strip()
        if lowered == "yo":
            return "yo, what's up"
        if lowered == "what":
            return "Say what you want done and I’ll take it from there."
        if lowered in {"hi", "hello", "hey"} or lowered.startswith("hello ") or lowered.startswith("hi ") or lowered.startswith("hey "):
            return "Hi."
        if "who are you" in lowered:
            return "Codex (portable wrapper)."
        if "what can you do" in lowered or "capabilities" in lowered:
            return (
                "I can reason through problems, inspect the system, work with files, run commands, install dependencies, analyze projects, generate code, and turn repeated work into reusable skills."
            )
        if any(token in lowered for token in ["compare", "checklist", "strategy", "approach", "tradeoff", "design"]):
            result = self.reasoning.solve(prompt, memory_hits)
            notes = self.self_improve.promote_reasoning_skill(result.skill_payload)
            if notes:
                return result.output + "\n\n[Skill Extraction]\n" + "\n".join(notes)
            return result.output
        if "set up node" in lowered or "setup node" in lowered:
            return (
                "Install the Node.js LTS build, then verify with `node -v` and `npm -v`.\n\n"
                "Fast path:\n"
                "- Install Node LTS from nodejs.org\n"
                "- Reopen the terminal\n"
                "- Check the versions\n\n"
                "Worth doing:\n"
                "- If you switch versions often, use a version manager instead of a single global install.\n"
                "- The usual Windows issue is multiple Node installs fighting over PATH."
            )
        if lowered.startswith("what is this file"):
            return "Send the file path. I’ll tell you what it does, what matters in it, and whether anything looks off."
        if memory_hits:
            latest = memory_hits[0]
            return latest.get("summary", "")
        return "Go on."

    def _enhance_outcome(self, prompt: str, outcome: str) -> str:
        lowered = prompt.lower()
        if ("analyze this folder" in lowered or "analyse this folder" in lowered or "scan this folder" in lowered) and "quick improvements:" not in outcome.lower():
            improvements = []
            lowered_outcome = outcome.lower()
            if '"git": false' in lowered_outcome:
                improvements.append("- No Git repo detected. If this is going to grow, put it under version control now.")
            if '"tests": false' in lowered_outcome:
                improvements.append("- No tests detected. Even one smoke test would improve confidence fast.")
            if '"node": false' in lowered_outcome and '"python": true' in lowered_outcome:
                improvements.append("- This looks Python-first. Keep it that way unless you actually need Node tooling.")
            if improvements:
                return outcome + "\n\nQuick improvements:\n" + "\n".join(improvements)
        return outcome

    def _record(self, prompt: str, plan: Plan, outcome: str, success: bool) -> None:
        tags = sorted(set((plan.context.get("command", "") + " " + " ".join(skill.tags[0] for skill in plan.skills)).split()))
        record = TaskRecord(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            prompt=prompt,
            plan=plan.steps,
            outcome=outcome[:5000],
            success=success,
            skills=[skill.skill_id for skill in plan.skills],
            tags=tags[:8],
            summary=self.memory.summarize(prompt, outcome, tags[:4]),
        )
        self.memory.save_task(record)

    @staticmethod
    def _confirm(message: str) -> bool:
        answer = input(f"{message} [y/N]: ").strip().lower()
        return answer in {"y", "yes"}

    @staticmethod
    def _is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False


CodexAgent = CodexWrapperAgent
