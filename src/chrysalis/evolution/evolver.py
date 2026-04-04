"""Skill evolver — applies evolution suggestions from the host LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ..core.skill import EvolutionType, Skill, SkillMeta, parse_skill_md, _make_id
from ..core.store import SkillStore


class SkillEvolver:
    """Applies evolution suggestions produced by the host LLM.

    The host LLM does the reasoning; this class handles persistence,
    versioning, and lineage tracking.
    """

    def __init__(self, store: SkillStore):
        self.store = store

    def apply_suggestions(self, suggestions_json: str) -> list[dict]:
        """Parse and apply evolution suggestions from the host LLM.

        Args:
            suggestions_json: JSON array from the host LLM, each item has:
                - type: "capture" | "fix"
                - skill_id: existing skill id (for fix) or null (for capture)
                - skill_name: name for the skill
                - reason: why this evolution is needed
                - new_content: full SKILL.md content

        Returns:
            List of results with status for each suggestion.
        """
        try:
            suggestions = json.loads(suggestions_json)
        except json.JSONDecodeError as e:
            return [{"error": f"Invalid JSON: {e}"}]

        if not isinstance(suggestions, list):
            return [{"error": "Expected a JSON array of suggestions"}]

        results = []
        for suggestion in suggestions:
            try:
                result = self._apply_one(suggestion)
                results.append(result)
            except Exception as e:
                results.append({
                    "skill_name": suggestion.get("skill_name", "unknown"),
                    "status": "error",
                    "error": str(e),
                })

        return results

    def capture_skill(self, name: str, description: str, content: str,
                      tags: Optional[list[str]] = None, reason: str = "") -> Skill:
        """Capture a brand new skill from a successful execution pattern."""
        now = datetime.now(timezone.utc).isoformat()
        skill_id = _make_id(name, 1)

        skill = Skill(
            id=skill_id,
            meta=SkillMeta(
                name=name,
                description=description,
                tags=tags or [],
                version=1,
                created_at=now,
                updated_at=now,
                origin=EvolutionType.CAPTURED,
            ),
            content=content,
        )

        self.store.save_skill(skill)
        self.store.save_evolution(
            skill_id=skill_id,
            evolution_type=EvolutionType.CAPTURED,
            reason=reason,
        )

        return skill

    def fix_skill(self, skill_id: str, new_content: str, reason: str = "") -> Optional[Skill]:
        """Fix an existing skill — creates a new version, deactivates the old one."""
        old_skill = self.store.get_skill(skill_id)
        if not old_skill:
            return None

        now = datetime.now(timezone.utc).isoformat()
        new_version = old_skill.meta.version + 1
        new_id = _make_id(old_skill.meta.name, new_version)

        new_skill = Skill(
            id=new_id,
            meta=SkillMeta(
                name=old_skill.meta.name,
                description=old_skill.meta.description,
                tags=old_skill.meta.tags,
                version=new_version,
                created_at=old_skill.meta.created_at,
                updated_at=now,
                parent_id=old_skill.id,
                origin=EvolutionType.FIX,
            ),
            content=new_content,
        )

        # Deactivate old, save new
        self.store.deactivate_skill(old_skill.id)
        self.store.save_skill(new_skill)
        self.store.save_evolution(
            skill_id=new_id,
            evolution_type=EvolutionType.FIX,
            parent_id=old_skill.id,
            reason=reason,
            diff_summary=f"v{old_skill.meta.version} -> v{new_version}",
        )

        return new_skill

    def _apply_one(self, suggestion: dict) -> dict:
        stype = suggestion.get("type", "")
        skill_name = suggestion.get("skill_name", "unknown")
        reason = suggestion.get("reason", "")
        new_content = suggestion.get("new_content", "")

        if not new_content:
            return {"skill_name": skill_name, "status": "skipped", "reason": "no new_content provided"}

        if stype == "capture":
            # Try to parse as SKILL.md; fallback to raw content
            try:
                parsed = parse_skill_md(new_content)
                skill = self.capture_skill(
                    name=parsed.meta.name or skill_name,
                    description=parsed.meta.description,
                    content=parsed.content,
                    tags=parsed.meta.tags,
                    reason=reason,
                )
            except ValueError:
                skill = self.capture_skill(
                    name=skill_name,
                    description=reason,
                    content=new_content,
                    reason=reason,
                )
            return {"skill_name": skill.meta.name, "skill_id": skill.id, "status": "captured"}

        elif stype == "fix":
            skill_id = suggestion.get("skill_id")
            if not skill_id:
                return {"skill_name": skill_name, "status": "error", "reason": "fix requires skill_id"}

            # Extract just the content body if full SKILL.md provided
            try:
                parsed = parse_skill_md(new_content)
                body = parsed.content
            except ValueError:
                body = new_content

            skill = self.fix_skill(skill_id, body, reason=reason)
            if not skill:
                return {"skill_name": skill_name, "status": "error", "reason": f"skill {skill_id} not found"}
            return {"skill_name": skill.meta.name, "skill_id": skill.id, "status": "fixed"}

        else:
            return {"skill_name": skill_name, "status": "error", "reason": f"unknown type: {stype}"}
