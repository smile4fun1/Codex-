from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .safety import SafetyLayer
from .skills import Skill, SkillRegistry


@dataclass
class Plan:
    mode: str
    summary: str
    steps: list[str]
    reasoning: str = ""
    skills: list[Skill] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    needs_confirmation: bool = False
    risks: list[str] = field(default_factory=list)


class Planner:
    def __init__(self, skills: SkillRegistry, safety: SafetyLayer) -> None:
        self.skills = skills
        self.safety = safety

    def build_plan(self, prompt: str, memory_hits: list[dict[str, Any]]) -> Plan:
        mode = self._detect_mode(prompt)
        selected = self.skills.select(prompt)
        context = self._infer_context(prompt)
        lowered = prompt.lower()
        safety = self.safety.assess_text(prompt)
        risks = list(safety.reasons)
        needs_confirmation = safety.needs_confirmation
        reasoning = ""

        if memory_hits:
            context["memory_hits"] = memory_hits[:3]

        if ("scan" in lowered or "summarize" in lowered or "analyze" in lowered or "analyse" in lowered) and ("folder" in lowered or "directory" in lowered):
            selected = [skill for skill in selected if skill.skill_id in {"project_analysis", "system_inspection"}]

        if mode == "hybrid" and not selected:
            for skill_id in ["system_inspection", "project_analysis"]:
                skill = self.skills.skills.get(skill_id)
                if skill:
                    selected.append(skill)

        impactful_skill_ids = {"shell_execution", "dependency_install", "file_ops", "code_generation"}
        selected_ids = {skill.skill_id for skill in selected}
        if mode in {"execution", "hybrid"} and selected_ids & impactful_skill_ids:
            needs_confirmation = True
            if "impactful execution requested" not in risks:
                risks.append("impactful execution requested")
        else:
            needs_confirmation = False
            risks = [risk for risk in risks if risk != "impactful execution requested"]

        if mode == "conversation":
            steps = ["Interpret request conversationally and answer directly."]
            if memory_hits:
                steps.append("Use relevant prior high-signal memory if it improves the answer.")
            return Plan(
                mode=mode,
                summary="conversation",
                steps=steps,
                reasoning="",
                skills=[],
                context=context,
                needs_confirmation=False,
                risks=risks,
            )

        if mode == "hybrid":
            reasoning = "This needs a quick recommendation layer before acting so the execution path stays useful and minimal."

        steps = ["Interpret request and select matching skills."]
        if selected:
            steps.append("Execute the minimum useful actions in a controlled order.")
        else:
            steps.append("No reliable local skill match found; use hybrid reasoning as the fallback path.")
        if memory_hits:
            steps.append("Use relevant prior high-signal memory if it improves the answer.")
        if risks:
            steps.append("Pause for confirmation before impactful or risky actions.")

        summary = " / ".join([skill.skill_id for skill in selected]) if selected else "fallback"
        return Plan(
            mode=mode,
            summary=summary,
            steps=steps,
            reasoning=reasoning,
            skills=selected,
            context=context,
            needs_confirmation=needs_confirmation,
            risks=risks,
        )

    @staticmethod
    def _detect_mode(prompt: str) -> str:
        lowered = prompt.lower()
        hybrid_signals = [
            "optimize ",
            "improve my ",
            "audit ",
            "review my setup",
            "dev setup",
            "workflow setup",
        ]
        execution_signals = [
            "run ",
            "execute ",
            "install ",
            "create ",
            "write ",
            "read ",
            "delete ",
            "remove ",
            "inspect ",
            "analy",
            "scan ",
            "summarize ",
            "folder",
            "directory",
            "list files",
            "show file",
            "open ",
            "generate ",
            "build ",
            "edit ",
        ]
        reasoning_signals = [
            "compare ",
            "strategy",
            "checklist",
            "plan for",
            "approach",
            "design",
            "tradeoff",
        ]
        if any(signal in lowered for signal in hybrid_signals):
            return "hybrid"
        if any(signal in lowered for signal in execution_signals):
            return "execution"
        if any(signal in lowered for signal in reasoning_signals):
            return "conversation"
        return "conversation"

    def _infer_context(self, prompt: str) -> dict[str, Any]:
        lowered = prompt.lower()
        context: dict[str, Any] = {}

        if "inspect" in lowered or "status" in lowered or "capabilities" in lowered:
            context["path"] = None
        if "analy" in lowered and "project" in lowered:
            context["path"] = None
        if "scan this folder" in lowered or "scan this directory" in lowered or "summarize this folder" in lowered:
            context["path"] = None
        if "install " in lowered:
            context["package"] = prompt.split("install", 1)[1].strip(" :")
            if "winget" in lowered:
                context["manager"] = "winget"
            elif "npm" in lowered:
                context["manager"] = "npm"
            else:
                context["manager"] = "pip"
        if "read " in lowered and "." in prompt:
            context["mode"] = "read"
            context["path"] = prompt.split("read", 1)[1].strip(" :")
        if "write " in lowered and "." in prompt:
            context["mode"] = "write"
            context["path"] = prompt.split("write", 1)[1].strip(" :")
        if "generate" in lowered and "." in prompt:
            context["path"] = prompt.split()[-1]
            context["instruction"] = prompt
        if "run " in lowered or "execute " in lowered:
            for token in ["run", "execute"]:
                if token in lowered:
                    context["command"] = prompt.split(token, 1)[1].strip(" :")
                    break
        return context
