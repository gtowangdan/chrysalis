"""SQLite persistence for skills, executions, and evolution history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .skill import EvolutionType, Skill, SkillMeta


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SkillStore:
    """SQLite-backed skill store with version tracking and quality metrics."""

    def __init__(self, db_path: Path | str = "chrysalis.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                version INTEGER DEFAULT 1,
                content TEXT NOT NULL,
                origin TEXT DEFAULT 'imported',
                parent_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                total_used INTEGER DEFAULT 0,
                total_success INTEGER DEFAULT 0,
                total_failure INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_description TEXT NOT NULL,
                skill_ids TEXT DEFAULT '[]',
                recording TEXT NOT NULL,
                outcome TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                evolution_type TEXT NOT NULL,
                parent_id TEXT,
                reason TEXT,
                diff_summary TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_skills_active ON skills(is_active);
            CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
            CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at);
        """)
        self.conn.commit()

    # --- Skill CRUD ---

    def save_skill(self, skill: Skill) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO skills
               (id, name, description, tags, version, content, origin, parent_id,
                created_at, updated_at, total_used, total_success, total_failure, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                skill.id, skill.meta.name, skill.meta.description,
                json.dumps(skill.meta.tags), skill.meta.version, skill.content,
                skill.meta.origin.value, skill.meta.parent_id,
                skill.meta.created_at, skill.meta.updated_at,
                skill.total_used, skill.total_success, skill.total_failure, 1,
            ),
        )
        self.conn.commit()

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        row = self.conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        if not row:
            return None
        return self._row_to_skill(row)

    def list_skills(self, active_only: bool = True) -> list[Skill]:
        q = "SELECT * FROM skills"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY total_used DESC"
        return [self._row_to_skill(r) for r in self.conn.execute(q).fetchall()]

    def search_skills(self, query: str, limit: int = 5) -> list[Skill]:
        """Simple keyword search across name, description, tags, content."""
        words = query.lower().split()
        if not words:
            return []

        all_skills = self.list_skills(active_only=True)
        scored: list[tuple[float, Skill]] = []

        for skill in all_skills:
            text = f"{skill.meta.name} {skill.meta.description} {' '.join(skill.meta.tags)} {skill.content}".lower()
            score = sum(text.count(w) for w in words)
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def deactivate_skill(self, skill_id: str) -> None:
        self.conn.execute("UPDATE skills SET is_active = 0, updated_at = ? WHERE id = ?", (_now(), skill_id))
        self.conn.commit()

    # --- Quality metrics ---

    def record_usage(self, skill_id: str, success: bool) -> None:
        col = "total_success" if success else "total_failure"
        self.conn.execute(
            f"UPDATE skills SET total_used = total_used + 1, {col} = {col} + 1, updated_at = ? WHERE id = ?",
            (_now(), skill_id),
        )
        self.conn.commit()

    # --- Execution recordings ---

    def save_execution(self, task_description: str, skill_ids: list[str],
                       recording: str, outcome: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO executions (task_description, skill_ids, recording, outcome, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_description, json.dumps(skill_ids), recording, outcome, _now()),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore

    def get_execution(self, execution_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def list_recent_executions(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM executions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Evolution history ---

    def save_evolution(self, skill_id: str, evolution_type: EvolutionType,
                       parent_id: Optional[str] = None, reason: str = "",
                       diff_summary: str = "") -> None:
        self.conn.execute(
            "INSERT INTO evolutions (skill_id, evolution_type, parent_id, reason, diff_summary, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (skill_id, evolution_type.value, parent_id, reason, diff_summary, _now()),
        )
        self.conn.commit()

    def get_skill_history(self, skill_name: str) -> list[dict]:
        """Get all versions of a skill by name."""
        rows = self.conn.execute(
            "SELECT * FROM skills WHERE name = ? ORDER BY version DESC", (skill_name,)
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Stats ---

    def get_stats(self) -> dict:
        skills_count = self.conn.execute("SELECT COUNT(*) FROM skills WHERE is_active = 1").fetchone()[0]
        executions_count = self.conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
        evolutions_count = self.conn.execute("SELECT COUNT(*) FROM evolutions").fetchone()[0]
        return {
            "active_skills": skills_count,
            "total_executions": executions_count,
            "total_evolutions": evolutions_count,
        }

    # --- Internal ---

    @staticmethod
    def _row_to_skill(row: sqlite3.Row) -> Skill:
        return Skill(
            id=row["id"],
            meta=SkillMeta(
                name=row["name"],
                description=row["description"],
                tags=json.loads(row["tags"]),
                version=row["version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                parent_id=row["parent_id"],
                origin=EvolutionType(row["origin"]),
            ),
            content=row["content"],
            total_used=row["total_used"],
            total_success=row["total_success"],
            total_failure=row["total_failure"],
        )

    def close(self) -> None:
        self.conn.close()
