from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .skills import SkillRegistry


class SelfImprover:
    def __init__(self, root: Path, skills: SkillRegistry) -> None:
        self.root = root
        self.skills = skills
        self.log_path = root / "logs" / "self_improve.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def review(self, prompt: str, selected_skills: list[str], success: bool, outcome: str) -> list[str]:
        notes: list[str] = []
        note = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "prompt": prompt,
            "selected_skills": selected_skills,
            "success": success,
            "outcome": outcome[:300],
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(note, ensure_ascii=True) + "\n")

        repeated = self._find_repeated_combo(selected_skills)
        if repeated:
            skill_id = f"combo_{'_'.join(repeated)}"
            if skill_id not in self.skills.skills:
                payload = {
                    "skill_id": skill_id,
                    "name": "Composite " + " + ".join(repeated),
                    "description": "Auto-created composite skill from repeated successful usage.",
                    "inputs": ["prompt"],
                    "tags": ["composite", "auto-improved"] + repeated,
                    "keywords": repeated,
                    "logic": {"type": "composite", "skills": repeated},
                    "enabled": True,
                    "version": 1,
                }
                self.skills.create_or_update_user_skill(payload)
                notes.append(f"Created composite skill: {skill_id}")

        if not success:
            notes.append("Task failed or was incomplete; no automatic runtime edits applied.")
        elif selected_skills:
            notes.append("Recorded successful skill path for future retrieval and composition.")
        return notes

    def promote_reasoning_skill(self, payload: dict[str, object] | None) -> list[str]:
        if not payload:
            return []
        existing = self.skills.skills.get(str(payload["skill_id"]))
        skill = self.skills.create_or_update_user_skill(payload)
        if existing:
            return [f"Improved reusable skill: {skill.skill_id}"]
        return [f"Created reusable skill: {skill.skill_id}"]

    def _find_repeated_combo(self, selected_skills: list[str]) -> list[str]:
        if len(selected_skills) < 2:
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines() if self.log_path.exists() else []
        combos: Counter[tuple[str, ...]] = Counter()
        for line in lines[-50:]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            combo = tuple(payload.get("selected_skills", []))
            if len(combo) >= 2 and payload.get("success"):
                combos[combo] += 1
        current = tuple(selected_skills)
        if combos[current] >= 2:
            return list(current)
        return []
