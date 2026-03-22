from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class IndexedSkill:
    skill_id: str
    path: str
    name: str
    description: str
    version: int
    enabled: bool
    inputs: list[str]
    tags: list[str]
    keywords: list[str]
    content_hash: str
    issues: list[str]


class UserSkillIndex:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.skills_dir = root / "skills"
        self.disabled_dir = self.skills_dir / "_disabled"
        self.index_path = self.skills_dir / "index.json"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.disabled_dir.mkdir(parents=True, exist_ok=True)

    def build(self) -> dict[str, object]:
        previous = self._load_index_map()
        entries = [asdict(entry) for entry in self._scan_skills(previous)]
        payload = {"updated_at": datetime.now().isoformat(timespec="seconds"), "skills": entries}
        self.index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    def clean(self) -> dict[str, object]:
        payload = self.build()
        cleaned: list[dict[str, object]] = []
        for entry in payload["skills"]:
            issues = set(entry.get("issues", []))
            if not entry.get("enabled", True):
                issues.add("disabled")
            should_disable = any(
                issue.startswith(prefix)
                for issue in issues
                for prefix in ("duplicate-skill", "missing-inputs", "insufficient-body", "missing-description")
            )
            if not should_disable:
                continue
            skill_dir = self.skills_dir / entry["skill_id"]
            disabled_path = self.disabled_dir / entry["skill_id"]
            if skill_dir.exists():
                disabled_path.parent.mkdir(parents=True, exist_ok=True)
                if disabled_path.exists():
                    shutil.rmtree(disabled_path)
                shutil.move(str(skill_dir), str(disabled_path))
            entry["enabled"] = False
            issues.add("disabled")
            entry["issues"] = sorted(issues)
            cleaned.append({"skill_id": entry["skill_id"], "issues": entry["issues"]})
        self.index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return {"cleaned": cleaned, "total": len(cleaned)}

    def lookup(self, text: str, limit: int = 5) -> list[dict[str, object]]:
        payload = self._load_index()
        lowered = text.lower()
        scored: list[tuple[int, dict[str, object]]] = []
        for entry in payload.get("skills", []):
            if not entry.get("enabled", True):
                continue
            score = sum(2 for item in entry.get("keywords", []) if item in lowered)
            score += sum(1 for item in entry.get("tags", []) if item in lowered)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def _scan_skills(self, previous: dict[str, dict[str, object]]) -> list[IndexedSkill]:
        entries: list[IndexedSkill] = []
        seen_signatures: dict[tuple[str, str], str] = {}
        for skill_dir in sorted(self.skills_dir.iterdir(), key=lambda item: item.name.lower()):
            if not skill_dir.is_dir() or skill_dir.name.startswith(".") or skill_dir.name == "_disabled":
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            frontmatter, body = self._parse_skill(skill_file.read_text(encoding="utf-8", errors="replace"))
            previous_entry = previous.get(skill_dir.name, {})
            description = str(frontmatter.get("description", "")).strip()
            name = str(frontmatter.get("name", skill_dir.name)).strip() or skill_dir.name
            tags = self._normalize_list(previous_entry.get("tags")) or self._tokenize(name + " " + description, limit=8)
            keywords = self._normalize_list(previous_entry.get("keywords")) or self._tokenize(name + " " + description, limit=12)
            inputs = self._normalize_list(previous_entry.get("inputs")) or ["request"]
            content_hash = hashlib.sha256(skill_file.read_bytes()).hexdigest()
            prior_hash = str(previous_entry.get("content_hash", ""))
            prior_version = int(previous_entry.get("version", 1) or 1)
            version = prior_version + 1 if prior_hash and prior_hash != content_hash else prior_version
            enabled = bool(previous_entry.get("enabled", True))
            issues: list[str] = []
            if not description:
                issues.append("missing-description")
            if len(body.strip()) < 80:
                issues.append("insufficient-body")
            if not inputs:
                issues.append("missing-inputs")
            signature = (name.lower(), description.lower())
            duplicate_of = seen_signatures.get(signature)
            if duplicate_of:
                issues.append(f"duplicate-skill:{duplicate_of}")
                enabled = False
            else:
                seen_signatures[signature] = skill_dir.name
            entries.append(
                IndexedSkill(
                    skill_id=skill_dir.name,
                    path=str(Path("skills") / skill_dir.name),
                    name=name,
                    description=description,
                    version=max(version, 1),
                    enabled=enabled,
                    inputs=inputs,
                    tags=tags,
                    keywords=keywords,
                    content_hash=content_hash,
                    issues=sorted(set(issues)),
                )
            )
        return entries

    def _load_index(self) -> dict[str, object]:
        if not self.index_path.exists():
            return {"skills": []}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"skills": []}

    def _load_index_map(self) -> dict[str, dict[str, object]]:
        payload = self._load_index()
        return {
            entry["skill_id"]: entry
            for entry in payload.get("skills", [])
            if isinstance(entry, dict) and entry.get("skill_id")
        }

    @staticmethod
    def _parse_skill(text: str) -> tuple[dict[str, object], str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        frontmatter_text = parts[1]
        body = parts[2].lstrip()
        frontmatter: dict[str, object] = {}
        for line in frontmatter_text.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip().strip("'\"")
        return frontmatter, body

    @staticmethod
    def _normalize_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @staticmethod
    def _tokenize(text: str, limit: int) -> list[str]:
        tokens: list[str] = []
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower()):
            if token not in tokens:
                tokens.append(token)
        return tokens[:limit]

