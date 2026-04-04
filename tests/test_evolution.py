"""Tests for SkillEvolver — capture_skill, fix_skill, apply_suggestions."""

import json

import pytest

from chrysalis.core.skill import EvolutionType
from chrysalis.core.store import SkillStore
from chrysalis.evolution.evolver import SkillEvolver


@pytest.fixture
def store(tmp_path):
    db = SkillStore(db_path=tmp_path / "test_evo.db")
    yield db
    db.close()


@pytest.fixture
def evolver(store):
    return SkillEvolver(store)


SKILL_MD_TEMPLATE = """\
---
name: {name}
description: {description}
tags: []
version: 1
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
origin: imported
---

## Instructions

{content}
"""


class TestCaptureSkill:
    def test_capture_creates_skill(self, evolver, store):
        skill = evolver.capture_skill(
            name="New Skill",
            description="A newly captured skill",
            content="## How to do it\n\nStep 1.",
        )
        assert skill is not None
        assert skill.meta.name == "New Skill"
        assert skill.meta.origin == EvolutionType.CAPTURED
        assert skill.meta.version == 1

    def test_captured_skill_persisted(self, evolver, store):
        skill = evolver.capture_skill(
            name="Persist Skill",
            description="Should be in DB",
            content="Content here.",
        )
        fetched = store.get_skill(skill.id)
        assert fetched is not None
        assert fetched.meta.name == "Persist Skill"

    def test_capture_with_tags(self, evolver, store):
        skill = evolver.capture_skill(
            name="Tagged Skill",
            description="Has tags",
            content="Content.",
            tags=["python", "testing"],
        )
        fetched = store.get_skill(skill.id)
        assert fetched.meta.tags == ["python", "testing"]

    def test_capture_records_evolution_history(self, evolver, store):
        evolver.capture_skill(
            name="History Skill",
            description="Track me",
            content="Steps.",
            reason="Extracted from exec #5",
        )
        stats = store.get_stats()
        assert stats["total_evolutions"] == 1

    def test_capture_reason_stored(self, evolver, store):
        evolver.capture_skill(
            name="Reason Skill",
            description="desc",
            content="content",
            reason="Because it worked great",
        )
        # Verify via stats (evolution row created)
        stats = store.get_stats()
        assert stats["total_evolutions"] >= 1


class TestFixSkill:
    def _seed_skill(self, store, name="Original Skill", content="Old content."):
        from chrysalis.core.skill import Skill, SkillMeta, _make_id
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        skill = Skill(
            id=_make_id(name, 1),
            meta=SkillMeta(
                name=name,
                description="Original description",
                version=1,
                created_at=now,
                updated_at=now,
                origin=EvolutionType.IMPORTED,
            ),
            content=content,
        )
        store.save_skill(skill)
        return skill

    def test_fix_creates_new_version(self, evolver, store):
        old = self._seed_skill(store)
        new_skill = evolver.fix_skill(old.id, "Improved content.", reason="Bug fix")

        assert new_skill is not None
        assert new_skill.meta.version == 2
        assert new_skill.content == "Improved content."

    def test_fix_deactivates_old_version(self, evolver, store):
        old = self._seed_skill(store)
        evolver.fix_skill(old.id, "New content.")

        active = store.list_skills(active_only=True)
        active_ids = [s.id for s in active]
        assert old.id not in active_ids

    def test_fix_preserves_lineage(self, evolver, store):
        old = self._seed_skill(store)
        new_skill = evolver.fix_skill(old.id, "Fixed content.")

        assert new_skill.meta.parent_id == old.id
        assert new_skill.meta.origin == EvolutionType.FIX

    def test_fix_nonexistent_returns_none(self, evolver):
        result = evolver.fix_skill("nonexistent__v1", "content")
        assert result is None

    def test_fix_records_evolution_history(self, evolver, store):
        old = self._seed_skill(store)
        evolver.fix_skill(old.id, "Fixed.", reason="Needed fixing")
        stats = store.get_stats()
        assert stats["total_evolutions"] == 1

    def test_fix_new_id_increments_version(self, evolver, store):
        old = self._seed_skill(store, name="My Skill")
        new_skill = evolver.fix_skill(old.id, "New content.")
        assert new_skill.id == "my-skill__v2"


class TestApplySuggestions:
    def test_capture_suggestion(self, evolver, store):
        new_content = SKILL_MD_TEMPLATE.format(
            name="Auto Captured",
            description="Captured automatically",
            content="Run the script.",
        )
        suggestions = json.dumps([
            {
                "type": "capture",
                "skill_id": None,
                "skill_name": "Auto Captured",
                "reason": "Recurring pattern",
                "new_content": new_content,
            }
        ])

        results = evolver.apply_suggestions(suggestions)
        assert len(results) == 1
        assert results[0]["status"] == "captured"
        assert results[0]["skill_name"] == "Auto Captured"

    def test_fix_suggestion(self, evolver, store):
        from chrysalis.core.skill import Skill, SkillMeta, _make_id
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        skill = Skill(
            id="fix-target__v1",
            meta=SkillMeta(
                name="Fix Target",
                description="Needs fixing",
                version=1,
                created_at=now,
                updated_at=now,
                origin=EvolutionType.IMPORTED,
            ),
            content="Old broken content.",
        )
        store.save_skill(skill)

        new_content = SKILL_MD_TEMPLATE.format(
            name="Fix Target",
            description="Fixed version",
            content="New improved content.",
        )
        suggestions = json.dumps([
            {
                "type": "fix",
                "skill_id": "fix-target__v1",
                "skill_name": "Fix Target",
                "reason": "Was broken",
                "new_content": new_content,
            }
        ])

        results = evolver.apply_suggestions(suggestions)
        assert len(results) == 1
        assert results[0]["status"] == "fixed"

    def test_invalid_json_returns_error(self, evolver):
        results = evolver.apply_suggestions("not valid json {")
        assert len(results) == 1
        assert "error" in results[0]

    def test_non_array_json_returns_error(self, evolver):
        results = evolver.apply_suggestions('{"type": "capture"}')
        assert len(results) == 1
        assert "error" in results[0]

    def test_empty_array_returns_empty(self, evolver):
        results = evolver.apply_suggestions("[]")
        assert results == []

    def test_missing_new_content_skipped(self, evolver):
        suggestions = json.dumps([
            {
                "type": "capture",
                "skill_id": None,
                "skill_name": "Incomplete",
                "reason": "no content",
                "new_content": "",
            }
        ])
        results = evolver.apply_suggestions(suggestions)
        assert results[0]["status"] == "skipped"

    def test_unknown_type_returns_error(self, evolver):
        suggestions = json.dumps([
            {
                "type": "unknown",
                "skill_name": "Bad Type",
                "reason": "test",
                "new_content": "some content",
            }
        ])
        results = evolver.apply_suggestions(suggestions)
        assert results[0]["status"] == "error"

    def test_fix_without_skill_id_returns_error(self, evolver):
        suggestions = json.dumps([
            {
                "type": "fix",
                "skill_id": None,
                "skill_name": "No ID",
                "reason": "test",
                "new_content": "content",
            }
        ])
        results = evolver.apply_suggestions(suggestions)
        assert results[0]["status"] == "error"

    def test_multiple_suggestions_processed(self, evolver, store):
        content1 = SKILL_MD_TEMPLATE.format(
            name="Skill Alpha", description="Alpha desc", content="Alpha steps."
        )
        content2 = SKILL_MD_TEMPLATE.format(
            name="Skill Beta", description="Beta desc", content="Beta steps."
        )
        suggestions = json.dumps([
            {"type": "capture", "skill_id": None, "skill_name": "Skill Alpha",
             "reason": "pattern A", "new_content": content1},
            {"type": "capture", "skill_id": None, "skill_name": "Skill Beta",
             "reason": "pattern B", "new_content": content2},
        ])

        results = evolver.apply_suggestions(suggestions)
        assert len(results) == 2
        assert all(r["status"] == "captured" for r in results)

    def test_capture_raw_content_fallback(self, evolver, store):
        # When new_content is not valid SKILL.md, it should fall back gracefully
        suggestions = json.dumps([
            {
                "type": "capture",
                "skill_id": None,
                "skill_name": "Raw Skill",
                "reason": "raw content fallback",
                "new_content": "No frontmatter, just raw instructions here.",
            }
        ])
        results = evolver.apply_suggestions(suggestions)
        assert results[0]["status"] == "captured"
        assert results[0]["skill_name"] == "Raw Skill"
