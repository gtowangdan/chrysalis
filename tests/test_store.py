"""Tests for chrysalis.core.store — SkillStore CRUD with a temp SQLite db."""

import pytest

from chrysalis.core.skill import EvolutionType, Skill, SkillMeta
from chrysalis.core.store import SkillStore


def make_skill(
    name: str = "Test Skill",
    description: str = "A test skill",
    tags: list[str] | None = None,
    version: int = 1,
    content: str = "## Instructions\n\nDo the thing.",
    origin: EvolutionType = EvolutionType.IMPORTED,
) -> Skill:
    from chrysalis.core.skill import _make_id
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    return Skill(
        id=_make_id(name, version),
        meta=SkillMeta(
            name=name,
            description=description,
            tags=tags or [],
            version=version,
            created_at=now,
            updated_at=now,
            origin=origin,
        ),
        content=content,
    )


@pytest.fixture
def store(tmp_path):
    db = SkillStore(db_path=tmp_path / "test.db")
    yield db
    db.close()


class TestSaveAndGet:
    def test_save_and_retrieve(self, store):
        skill = make_skill("Deploy App", "Deploy to production")
        store.save_skill(skill)

        fetched = store.get_skill(skill.id)
        assert fetched is not None
        assert fetched.id == skill.id
        assert fetched.meta.name == "Deploy App"
        assert fetched.meta.description == "Deploy to production"

    def test_get_nonexistent_returns_none(self, store):
        assert store.get_skill("nonexistent__v1") is None

    def test_save_overwrites_on_same_id(self, store):
        skill = make_skill("My Skill")
        store.save_skill(skill)

        skill.meta.description = "Updated description"
        store.save_skill(skill)

        fetched = store.get_skill(skill.id)
        assert fetched.meta.description == "Updated description"

    def test_tags_persisted(self, store):
        skill = make_skill(tags=["python", "deploy"])
        store.save_skill(skill)
        fetched = store.get_skill(skill.id)
        assert fetched.meta.tags == ["python", "deploy"]

    def test_content_persisted(self, store):
        skill = make_skill(content="## Custom Content\n\nSpecial instructions.")
        store.save_skill(skill)
        fetched = store.get_skill(skill.id)
        assert "Custom Content" in fetched.content


class TestListSkills:
    def test_list_active_only(self, store):
        s1 = make_skill("Skill One")
        s2 = make_skill("Skill Two")
        store.save_skill(s1)
        store.save_skill(s2)
        store.deactivate_skill(s1.id)

        active = store.list_skills(active_only=True)
        ids = [s.id for s in active]
        assert s1.id not in ids
        assert s2.id in ids

    def test_list_all_including_inactive(self, store):
        s1 = make_skill("Skill One")
        s2 = make_skill("Skill Two")
        store.save_skill(s1)
        store.save_skill(s2)
        store.deactivate_skill(s1.id)

        all_skills = store.list_skills(active_only=False)
        ids = [s.id for s in all_skills]
        assert s1.id in ids
        assert s2.id in ids

    def test_empty_store_returns_empty_list(self, store):
        assert store.list_skills() == []


class TestSearchSkills:
    def test_keyword_match_in_name(self, store):
        store.save_skill(make_skill("Deploy NextJS", "Deploy to Vercel", content="run vercel"))
        store.save_skill(make_skill("Setup Database", "Postgres config", content="pg_dump"))

        results = store.search_skills("deploy")
        assert len(results) == 1
        assert results[0].meta.name == "Deploy NextJS"

    def test_keyword_match_in_content(self, store):
        store.save_skill(make_skill("My Skill", "does stuff", content="use kubectl to deploy pods"))

        results = store.search_skills("kubectl")
        assert len(results) == 1

    def test_empty_query_returns_empty(self, store):
        store.save_skill(make_skill())
        assert store.search_skills("") == []

    def test_no_match_returns_empty(self, store):
        store.save_skill(make_skill("Python Skill", "python stuff", content="python code"))
        assert store.search_skills("javascript") == []

    def test_limit_respected(self, store):
        for i in range(5):
            store.save_skill(make_skill(f"Deploy Skill {i}", f"deploy {i}", content=f"deploy step {i}"))

        results = store.search_skills("deploy", limit=3)
        assert len(results) <= 3


class TestDeactivate:
    def test_deactivate_skill(self, store):
        skill = make_skill("Active Skill")
        store.save_skill(skill)
        store.deactivate_skill(skill.id)

        fetched = store.get_skill(skill.id)
        # get_skill returns it regardless of active status
        assert fetched is not None

        # But list_skills active_only=True should exclude it
        active = store.list_skills(active_only=True)
        assert all(s.id != skill.id for s in active)


class TestRecordUsage:
    def test_record_success(self, store):
        skill = make_skill()
        store.save_skill(skill)
        store.record_usage(skill.id, success=True)

        fetched = store.get_skill(skill.id)
        assert fetched.total_used == 1
        assert fetched.total_success == 1
        assert fetched.total_failure == 0

    def test_record_failure(self, store):
        skill = make_skill()
        store.save_skill(skill)
        store.record_usage(skill.id, success=False)

        fetched = store.get_skill(skill.id)
        assert fetched.total_used == 1
        assert fetched.total_success == 0
        assert fetched.total_failure == 1

    def test_multiple_usages_accumulated(self, store):
        skill = make_skill()
        store.save_skill(skill)
        store.record_usage(skill.id, success=True)
        store.record_usage(skill.id, success=True)
        store.record_usage(skill.id, success=False)

        fetched = store.get_skill(skill.id)
        assert fetched.total_used == 3
        assert fetched.total_success == 2
        assert fetched.total_failure == 1


class TestSaveExecution:
    def test_save_and_get_execution(self, store):
        eid = store.save_execution(
            task_description="Deploy app to prod",
            skill_ids=["deploy-app__v1"],
            recording="Step 1: ... Step 2: ...",
            outcome="success",
        )
        assert isinstance(eid, int)

        ex = store.get_execution(eid)
        assert ex is not None
        assert ex["task_description"] == "Deploy app to prod"
        assert ex["outcome"] == "success"

    def test_get_nonexistent_execution_returns_none(self, store):
        assert store.get_execution(9999) is None

    def test_list_recent_executions(self, store):
        store.save_execution("Task A", [], "recording A", "success")
        store.save_execution("Task B", [], "recording B", "failure")

        recent = store.list_recent_executions(limit=10)
        assert len(recent) == 2
        descs = [e["task_description"] for e in recent]
        assert "Task A" in descs
        assert "Task B" in descs

    def test_list_recent_executions_limit(self, store):
        for i in range(5):
            store.save_execution(f"Task {i}", [], f"rec {i}", "success")

        recent = store.list_recent_executions(limit=3)
        assert len(recent) == 3


class TestGetStats:
    def test_empty_stats(self, store):
        stats = store.get_stats()
        assert stats["active_skills"] == 0
        assert stats["total_executions"] == 0
        assert stats["total_evolutions"] == 0

    def test_stats_count_skills(self, store):
        store.save_skill(make_skill("Skill A"))
        store.save_skill(make_skill("Skill B"))
        stats = store.get_stats()
        assert stats["active_skills"] == 2

    def test_stats_deactivated_skill_not_counted(self, store):
        skill = make_skill("Skill A")
        store.save_skill(skill)
        store.deactivate_skill(skill.id)
        stats = store.get_stats()
        assert stats["active_skills"] == 0

    def test_stats_count_executions(self, store):
        store.save_execution("task", [], "rec", "success")
        store.save_execution("task2", [], "rec2", "failure")
        stats = store.get_stats()
        assert stats["total_executions"] == 2

    def test_stats_count_evolutions(self, store):
        store.save_evolution("skill__v1", EvolutionType.CAPTURED, reason="test")
        stats = store.get_stats()
        assert stats["total_evolutions"] == 1
