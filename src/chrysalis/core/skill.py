"""Skill data model and SKILL.md parser/writer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class EvolutionType(str, Enum):
    FIX = "fix"  # 原地修复损坏/过时的技能
    CAPTURED = "captured"  # 从成功执行中提取全新技能
    IMPORTED = "imported"  # 用户手动导入


@dataclass
class SkillMeta:
    """SKILL.md YAML frontmatter."""

    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_id: Optional[str] = None
    origin: EvolutionType = EvolutionType.IMPORTED


@dataclass
class Skill:
    """A skill = metadata + instruction content."""

    id: str  # unique identifier, e.g. "deploy-nextjs__v1"
    meta: SkillMeta
    content: str  # markdown body (the actual instructions)

    # Runtime quality metrics (persisted in SQLite, not in SKILL.md)
    total_used: int = 0
    total_success: int = 0
    total_failure: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_used == 0:
            return 0.0
        return self.total_success / self.total_used


# --- SKILL.md parsing / writing ---

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_skill_md(text: str, skill_id: str = "") -> Skill:
    """Parse a SKILL.md string into a Skill object."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("Invalid SKILL.md: missing YAML frontmatter")

    raw_meta = yaml.safe_load(m.group(1))
    content = text[m.end():].strip()

    # Handle origin enum
    origin_val = raw_meta.pop("origin", "imported")
    try:
        origin = EvolutionType(origin_val)
    except ValueError:
        origin = EvolutionType.IMPORTED

    meta = SkillMeta(
        name=raw_meta.get("name", ""),
        description=raw_meta.get("description", ""),
        tags=raw_meta.get("tags", []),
        version=raw_meta.get("version", 1),
        created_at=raw_meta.get("created_at", ""),
        updated_at=raw_meta.get("updated_at", ""),
        parent_id=raw_meta.get("parent_id"),
        origin=origin,
    )

    return Skill(id=skill_id or _make_id(meta.name, meta.version), meta=meta, content=content)


def render_skill_md(skill: Skill) -> str:
    """Render a Skill object to SKILL.md format."""
    meta_dict = {
        "name": skill.meta.name,
        "description": skill.meta.description,
        "tags": skill.meta.tags,
        "version": skill.meta.version,
        "created_at": skill.meta.created_at,
        "updated_at": skill.meta.updated_at,
        "origin": skill.meta.origin.value,
    }
    if skill.meta.parent_id:
        meta_dict["parent_id"] = skill.meta.parent_id

    frontmatter = yaml.dump(meta_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{frontmatter}---\n\n{skill.content}\n"


def load_skill_from_file(path: Path) -> Skill:
    """Load a Skill from a SKILL.md file."""
    text = path.read_text(encoding="utf-8")
    skill_id = path.parent.name if path.name == "SKILL.md" else path.stem
    return parse_skill_md(text, skill_id=skill_id)


def save_skill_to_file(skill: Skill, directory: Path) -> Path:
    """Save a Skill to directory/SKILL.md."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    path.write_text(render_skill_md(skill), encoding="utf-8")
    return path


def _make_id(name: str, version: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}__v{version}"
