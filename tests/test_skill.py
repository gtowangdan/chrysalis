"""Tests for chrysalis.core.skill — parse_skill_md, render_skill_md, _make_id."""

import pytest

from chrysalis.core.skill import (
    EvolutionType,
    Skill,
    SkillMeta,
    _make_id,
    parse_skill_md,
    render_skill_md,
)


SAMPLE_MD = """\
---
name: Deploy Next.js
description: How to deploy a Next.js app to Vercel
tags:
  - deploy
  - nextjs
version: 1
created_at: "2024-01-01T00:00:00+00:00"
updated_at: "2024-01-01T00:00:00+00:00"
origin: imported
---

## Steps

1. Run `vercel deploy`
2. Done
"""


class TestMakeId:
    def test_simple_name(self):
        assert _make_id("Deploy Next.js", 1) == "deploy-next-js__v1"

    def test_version_increments(self):
        assert _make_id("my skill", 3) == "my-skill__v3"

    def test_special_chars_stripped(self):
        assert _make_id("Hello World!!!", 2) == "hello-world__v2"

    def test_consecutive_special_chars(self):
        # Multiple special chars collapse to a single dash
        assert _make_id("a  --  b", 1) == "a-b__v1"


class TestParseSkillMd:
    def test_basic_parse(self):
        skill = parse_skill_md(SAMPLE_MD)
        assert skill.meta.name == "Deploy Next.js"
        assert skill.meta.description == "How to deploy a Next.js app to Vercel"
        assert skill.meta.tags == ["deploy", "nextjs"]
        assert skill.meta.version == 1
        assert skill.meta.origin == EvolutionType.IMPORTED

    def test_content_extracted(self):
        skill = parse_skill_md(SAMPLE_MD)
        assert "## Steps" in skill.content
        assert "vercel deploy" in skill.content

    def test_auto_id_generated(self):
        skill = parse_skill_md(SAMPLE_MD)
        assert skill.id == "deploy-next-js__v1"

    def test_explicit_skill_id(self):
        skill = parse_skill_md(SAMPLE_MD, skill_id="custom-id")
        assert skill.id == "custom-id"

    def test_missing_frontmatter_raises(self):
        with pytest.raises(ValueError, match="missing YAML frontmatter"):
            parse_skill_md("No frontmatter here")

    def test_origin_fallback_to_imported(self):
        md = SAMPLE_MD.replace("origin: imported", "origin: unknown_value")
        skill = parse_skill_md(md)
        assert skill.meta.origin == EvolutionType.IMPORTED

    def test_captured_origin(self):
        md = SAMPLE_MD.replace("origin: imported", "origin: captured")
        skill = parse_skill_md(md)
        assert skill.meta.origin == EvolutionType.CAPTURED

    def test_parent_id_none_by_default(self):
        skill = parse_skill_md(SAMPLE_MD)
        assert skill.meta.parent_id is None

    def test_parent_id_parsed(self):
        md = SAMPLE_MD.replace(
            "origin: imported",
            "origin: fix\nparent_id: deploy-next-js__v1",
        )
        skill = parse_skill_md(md)
        assert skill.meta.parent_id == "deploy-next-js__v1"


class TestRenderSkillMd:
    def test_roundtrip(self):
        original = parse_skill_md(SAMPLE_MD)
        rendered = render_skill_md(original)
        reparsed = parse_skill_md(rendered)

        assert reparsed.meta.name == original.meta.name
        assert reparsed.meta.description == original.meta.description
        assert reparsed.meta.tags == original.meta.tags
        assert reparsed.meta.version == original.meta.version
        assert reparsed.meta.origin == original.meta.origin
        assert reparsed.content == original.content

    def test_has_frontmatter_delimiters(self):
        skill = parse_skill_md(SAMPLE_MD)
        rendered = render_skill_md(skill)
        assert rendered.startswith("---\n")
        assert "---\n\n" in rendered

    def test_parent_id_included_when_set(self):
        skill = parse_skill_md(SAMPLE_MD)
        skill.meta.parent_id = "some-parent__v1"
        rendered = render_skill_md(skill)
        assert "parent_id" in rendered
        assert "some-parent__v1" in rendered

    def test_parent_id_omitted_when_none(self):
        skill = parse_skill_md(SAMPLE_MD)
        rendered = render_skill_md(skill)
        assert "parent_id" not in rendered

    def test_success_rate_zero_when_unused(self):
        skill = parse_skill_md(SAMPLE_MD)
        assert skill.success_rate == 0.0

    def test_success_rate_calculated(self):
        skill = parse_skill_md(SAMPLE_MD)
        skill.total_used = 4
        skill.total_success = 3
        assert skill.success_rate == pytest.approx(0.75)
