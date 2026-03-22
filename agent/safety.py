from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


INJECTION_PATTERNS = [
    r"ignore (all|previous|prior) instructions",
    r"reveal (your|the) (system|developer) prompt",
    r"override (safety|policy|guardrails)",
    r"run this exactly",
]

DESTRUCTIVE_PATTERNS = [
    r"\brm\b",
    r"\bdel\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breg delete\b",
    r"\btaskkill\b",
    r"\bsc delete\b",
]

EXFIL_PATTERNS = [
    r"password",
    r"token",
    r"api[_ -]?key",
    r"credential",
    r"secret",
    r"ssh",
]


@dataclass
class SafetyDecision:
    allow: bool
    needs_confirmation: bool
    reasons: list[str] = field(default_factory=list)
    risk_level: str = "low"


class SafetyLayer:
    def assess_text(self, text: str, source: str = "user") -> SafetyDecision:
        reasons: list[str] = []
        risk_level = "low"
        lowered = text.lower()

        if self._matches(INJECTION_PATTERNS, lowered):
            reasons.append(f"prompt-injection pattern detected in {source} content")
            risk_level = "high"

        if self._matches(EXFIL_PATTERNS, lowered):
            reasons.append("sensitive credential or secret access may be involved")
            risk_level = "high"

        if self._matches(DESTRUCTIVE_PATTERNS, lowered):
            reasons.append("destructive operation detected")
            risk_level = "high"

        return SafetyDecision(
            allow=True,
            needs_confirmation=bool(reasons),
            reasons=reasons,
            risk_level=risk_level,
        )

    def assess_command(self, command: str) -> SafetyDecision:
        decision = self.assess_text(command, source="command")
        lowered = command.lower()
        if any(flag in lowered for flag in ["curl ", "invoke-webrequest", "scp ", "ftp "]):
            decision.reasons.append("network transfer or download detected")
            decision.needs_confirmation = True
            if decision.risk_level == "low":
                decision.risk_level = "medium"
        return decision

    def summarize_risks(self, items: Iterable[str]) -> list[str]:
        reasons: list[str] = []
        for item in items:
            decision = self.assess_text(item)
            reasons.extend(decision.reasons)
        return sorted(set(reasons))

    @staticmethod
    def _matches(patterns: list[str], text: str) -> bool:
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
