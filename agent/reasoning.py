from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ReasoningResult:
    output: str
    reusable: bool
    skill_payload: dict[str, Any] | None
    tags: list[str]


class CodexReasoningEngine:
    def solve(self, prompt: str, memory_hits: list[dict[str, Any]] | None = None) -> ReasoningResult:
        memory_hits = memory_hits or []
        lowered = prompt.lower()
        tags = self._extract_tags(lowered)

        if any(word in lowered for word in ["checklist", "plan", "strategy", "approach"]):
            output = self._structured_breakdown(prompt, memory_hits)
            return ReasoningResult(
                output=output,
                reusable=True,
                skill_payload=self._build_skill_payload(
                    skill_id="structured_breakdown",
                    name="Structured Breakdown",
                    description="Produce a concise structured breakdown for planning, strategy, checklist, and approach requests.",
                    keywords=["checklist", "plan", "strategy", "approach", "breakdown"],
                    tags=["reasoning", "planning", "analysis"],
                    steps=[
                        "Identify the user objective.",
                        "Break the problem into concise sections.",
                        "Prioritize risks, sequence, and next actions.",
                        "Respond directly without forcing system execution.",
                    ],
                ),
                tags=tags,
            )

        if any(word in lowered for word in ["compare", "difference", "tradeoff", "pros and cons"]):
            output = self._comparison_response(prompt)
            return ReasoningResult(
                output=output,
                reusable=True,
                skill_payload=self._build_skill_payload(
                    skill_id="comparison_reasoning",
                    name="Comparison Reasoning",
                    description="Compare options, highlight tradeoffs, and recommend a direction when appropriate.",
                    keywords=["compare", "difference", "tradeoff", "pros", "cons"],
                    tags=["reasoning", "comparison", "decision"],
                    steps=[
                        "Identify the options being compared.",
                        "List the practical tradeoffs.",
                        "Give a direct recommendation when justified.",
                    ],
                ),
                tags=tags,
            )

        output = self._general_reasoning(prompt, memory_hits)
        return ReasoningResult(output=output, reusable=False, skill_payload=None, tags=tags)

    def explain_hybrid(self, prompt: str) -> str:
        lowered = prompt.lower()
        if "optimize" in lowered and "dev setup" in lowered:
            return "I’ll inspect the current toolchain first, then turn that into a short set of practical setup improvements."
        return "I’ll reason about the goal briefly, then use the minimum execution needed to ground the answer."

    def synthesize_hybrid(self, prompt: str, execution_outputs: list[str]) -> str:
        lowered = prompt.lower()
        joined = "\n".join(execution_outputs).lower()
        if "optimize" in lowered and "dev setup" in lowered:
            recommendations = []
            if '"git": null' in joined:
                recommendations.append("- Install Git if you want normal repo workflows.")
            if '"rg": null' in joined:
                recommendations.append("- Install ripgrep for faster code search.")
            if '"code": null' in joined:
                recommendations.append("- Install VS Code or wire your preferred editor into PATH.")
            if not recommendations:
                recommendations.extend(
                    [
                        "- Your core dev tools are present; focus on shell aliases, package manager hygiene, and repo bootstrap scripts.",
                        "- Keep a small bootstrap script for Python, Git, Node, and editor extensions so setup stays reproducible.",
                    ]
                )
            return "Recommendation:\n" + "\n".join(recommendations)
        return "Recommendation:\n- The inspected state is enough to guide the next step without adding extra complexity."

    def execute_virtual_skill(self, skill: dict[str, Any], prompt: str) -> dict[str, Any]:
        name = skill.get("name", "Virtual Skill")
        steps = skill.get("logic", {}).get("steps", [])
        lines = [f"{name} applied."]
        if steps:
            lines.append("Execution steps:")
            lines.extend([f"- {step}" for step in steps])
        lines.append(f"Prompt: {prompt}")
        return {"ok": True, "output": "\n".join(lines), "meta": {"virtual_skill": skill.get("skill_id")}}

    def _structured_breakdown(self, prompt: str, memory_hits: list[dict[str, Any]]) -> str:
        context = ""
        if memory_hits:
            context = f"Relevant prior context: {memory_hits[0].get('summary', '')}\n"
        return (
            f"{context}"
            "Objective:\n"
            f"- {prompt.strip()}\n\n"
            "Breakdown:\n"
            "- Define the target outcome clearly.\n"
            "- Identify constraints, risks, and dependencies.\n"
            "- Sequence the work from highest leverage to lowest.\n\n"
            "Recommendation:\n"
            "- Start with the smallest step that reduces uncertainty fastest."
        )

    @staticmethod
    def _comparison_response(prompt: str) -> str:
        return (
            f"Comparison request: {prompt.strip()}\n\n"
            "Approach:\n"
            "- Evaluate complexity, speed, control, and maintenance cost.\n"
            "- Prefer the option that reduces long-term friction for the actual workload.\n"
            "- If the tradeoff is context-dependent, state the deciding factor explicitly."
        )

    @staticmethod
    def _general_reasoning(prompt: str, memory_hits: list[dict[str, Any]]) -> str:
        lead = "This is better handled with reasoning than system execution."
        if memory_hits:
            lead += f" Relevant prior context: {memory_hits[0].get('summary', '')}"
        return f"{lead}\n\nResponse:\n- {prompt.strip()}\n- Clarify the goal, key constraints, and preferred outcome if you want a more tailored answer."

    @staticmethod
    def _extract_tags(lowered: str) -> list[str]:
        raw = re.findall(r"[a-z]{4,}", lowered)
        keep = []
        for token in raw:
            if token not in keep:
                keep.append(token)
        return keep[:8]

    @staticmethod
    def _build_skill_payload(
        skill_id: str,
        name: str,
        description: str,
        keywords: list[str],
        tags: list[str],
        steps: list[str],
    ) -> dict[str, Any]:
        return {
            "skill_id": skill_id,
            "name": name,
            "description": description,
            "inputs": ["prompt"],
            "tags": tags,
            "keywords": keywords,
            "logic": {"type": "virtual", "steps": steps},
            "enabled": True,
            "version": 1,
        }
