"""Execution analyzer — produces structured context for the host LLM to generate evolution suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..core.skill import Skill
from ..core.store import SkillStore


class SuggestionType(str, Enum):
    FIX = "fix"  # An existing skill needs repair
    CAPTURE = "capture"  # A new skill should be extracted


@dataclass
class EvolutionSuggestion:
    """A structured suggestion for skill evolution."""

    suggestion_type: SuggestionType
    skill_id: Optional[str]  # None for CAPTURE
    skill_name: str
    reason: str
    context: str  # Relevant execution excerpt


class ExecutionAnalyzer:
    """Analyzes execution recordings and prepares context for the host LLM.

    Key design: Chrysalis does NOT call any LLM itself.
    It prepares structured analysis context that the host agent (Claude/Codex)
    uses to make evolution decisions.
    """

    def __init__(self, store: SkillStore):
        self.store = store

    def build_analysis_prompt(self, execution_id: int) -> Optional[str]:
        """Build a structured prompt for the host LLM to analyze an execution.

        Returns a markdown prompt that the host LLM should process to produce
        evolution suggestions.
        """
        execution = self.store.get_execution(execution_id)
        if not execution:
            return None

        # Get the skills that were used in this execution
        import json
        skill_ids = json.loads(execution["skill_ids"]) if isinstance(execution["skill_ids"], str) else execution["skill_ids"]
        used_skills = [self.store.get_skill(sid) for sid in skill_ids]
        used_skills = [s for s in used_skills if s is not None]

        prompt = self._format_analysis_prompt(execution, used_skills)
        return prompt

    def build_bulk_analysis_prompt(self, limit: int = 5) -> Optional[str]:
        """Build a prompt analyzing recent executions for patterns worth capturing."""
        executions = self.store.list_recent_executions(limit=limit)
        if not executions:
            return None

        existing_skills = self.store.list_skills(active_only=True)

        sections = [
            "# Chrysalis: Execution Pattern Analysis",
            "",
            "Analyze the following recent executions and identify:",
            "1. **Recurring patterns** that should become new skills (CAPTURE)",
            "2. **Existing skills that failed** or gave incomplete guidance (FIX)",
            "3. **Gaps** — tasks where a skill would have helped but none existed",
            "",
            "## Existing Skills",
            "",
        ]

        if existing_skills:
            for s in existing_skills:
                rate = f"{s.success_rate:.0%}" if s.total_used > 0 else "unused"
                sections.append(f"- **{s.meta.name}** ({rate} success, used {s.total_used}x): {s.meta.description}")
        else:
            sections.append("_No skills exist yet._")

        sections.extend(["", "## Recent Executions", ""])

        for ex in executions:
            sections.extend([
                f"### Execution #{ex['id']} — {ex['outcome'].upper()}",
                f"**Task:** {ex['task_description']}",
                f"**Skills used:** {ex['skill_ids']}",
                "",
                "**Recording excerpt:**",
                "```",
                _truncate(ex["recording"], max_chars=2000),
                "```",
                "",
            ])

        sections.extend([
            "## Your Response Format",
            "",
            "Return a JSON array of suggestions:",
            "```json",
            '[{"type": "capture|fix", "skill_id": "existing-id-or-null", "skill_name": "name", "reason": "why"}]',
            "```",
            "",
            "If no evolution is needed, return `[]`.",
        ])

        return "\n".join(sections)

    def record_skill_outcome(self, skill_id: str, success: bool) -> None:
        """Record whether a skill application was successful."""
        self.store.record_usage(skill_id, success)

    def get_underperforming_skills(self, min_uses: int = 3, max_success_rate: float = 0.5) -> list[Skill]:
        """Find skills that have been used enough but perform poorly."""
        all_skills = self.store.list_skills(active_only=True)
        return [
            s for s in all_skills
            if s.total_used >= min_uses and s.success_rate < max_success_rate
        ]

    def _format_analysis_prompt(self, execution: dict, used_skills: list[Skill]) -> str:
        sections = [
            "# Chrysalis: Execution Analysis",
            "",
            f"**Task:** {execution['task_description']}",
            f"**Outcome:** {execution['outcome']}",
            "",
        ]

        if used_skills:
            sections.extend(["## Skills Used", ""])
            for s in used_skills:
                sections.extend([
                    f"### {s.meta.name} (v{s.meta.version})",
                    f"Success rate: {s.success_rate:.0%} over {s.total_used} uses",
                    "",
                    s.content[:1000],
                    "",
                ])

        sections.extend([
            "## Execution Recording",
            "```",
            _truncate(execution["recording"], max_chars=3000),
            "```",
            "",
            "## Your Task",
            "",
            "Based on this execution, respond with a JSON array of suggestions:",
            "```json",
            '[{"type": "capture|fix", "skill_id": "existing-id-or-null", "skill_name": "name", "reason": "why", "new_content": "full SKILL.md content"}]',
            "```",
            "",
            "- **capture**: Extract a new reusable skill from this successful execution",
            "- **fix**: Improve an existing skill that was incomplete or incorrect",
            "",
            "Include the full `new_content` as valid SKILL.md (YAML frontmatter + markdown body).",
            "If no evolution is needed, return `[]`.",
        ])

        return "\n".join(sections)


def _truncate(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n...[truncated]...\n" + text[-half:]
