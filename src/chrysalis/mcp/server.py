"""Chrysalis MCP Server — exposes skill evolution tools to host agents."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..core.store import SkillStore
from ..evolution.analyzer import ExecutionAnalyzer
from ..evolution.evolver import SkillEvolver

# --- Initialize ---

_DATA_DIR = Path(os.environ.get("CHRYSALIS_DATA_DIR", Path.home() / ".chrysalis"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DATA_DIR / "chrysalis.db"

_store = SkillStore(_DB_PATH)
_analyzer = ExecutionAnalyzer(_store)
_evolver = SkillEvolver(_store)

mcp = FastMCP(
    "chrysalis",
    instructions=(
        "Chrysalis is your skill self-evolution engine. "
        "Use search_skills before starting tasks to find relevant experience. "
        "After completing tasks, use record_execution to save what happened. "
        "Use analyze_executions to discover evolution opportunities. "
        "Use evolve_skills to apply improvements."
    ),
)


# --- Tools ---


@mcp.tool()
def search_skills(query: str, limit: int = 5) -> str:
    """Search for relevant skills based on the current task.

    Call this BEFORE starting a task to find reusable experience.
    Returns matching skills with their instructions that you should follow.

    Args:
        query: Description of what you're about to do
        limit: Max number of skills to return
    """
    skills = _store.search_skills(query, limit=limit)
    if not skills:
        return json.dumps({"skills": [], "message": "No matching skills found. After completing this task, consider recording the execution so a skill can be captured."})

    result = []
    for s in skills:
        result.append({
            "id": s.id,
            "name": s.meta.name,
            "description": s.meta.description,
            "tags": s.meta.tags,
            "version": s.meta.version,
            "success_rate": f"{s.success_rate:.0%}" if s.total_used > 0 else "new",
            "times_used": s.total_used,
            "instructions": s.content,
        })

    return json.dumps({"skills": result}, ensure_ascii=False)


@mcp.tool()
def record_execution(
    task_description: str,
    recording: str,
    outcome: str,
    skill_ids: str = "[]",
) -> str:
    """Record an execution after completing a task.

    Call this AFTER finishing a task to save the experience for future evolution.

    Args:
        task_description: What the task was
        recording: Key steps taken, commands run, decisions made, errors encountered
        outcome: "success" or "failure" with brief explanation
        skill_ids: JSON array of skill IDs that were used (from search_skills)
    """
    try:
        ids = json.loads(skill_ids) if isinstance(skill_ids, str) else skill_ids
    except json.JSONDecodeError:
        ids = []

    # Record usage outcomes for each skill
    is_success = "success" in outcome.lower()
    for sid in ids:
        _analyzer.record_skill_outcome(sid, is_success)

    eid = _store.save_execution(task_description, ids, recording, outcome)

    return json.dumps({
        "execution_id": eid,
        "message": f"Execution recorded. Use analyze_executions to check for evolution opportunities.",
    })


@mcp.tool()
def analyze_executions(execution_id: int = 0, recent_count: int = 5) -> str:
    """Analyze executions to find skill evolution opportunities.

    Returns a structured prompt — read it and respond with evolution suggestions.

    Args:
        execution_id: Analyze a specific execution (0 = analyze recent batch)
        recent_count: How many recent executions to analyze in batch mode
    """
    if execution_id > 0:
        prompt = _analyzer.build_analysis_prompt(execution_id)
    else:
        prompt = _analyzer.build_bulk_analysis_prompt(limit=recent_count)

    if not prompt:
        return json.dumps({"message": "No executions to analyze."})

    # Also include underperforming skills
    weak = _analyzer.get_underperforming_skills()
    extra = ""
    if weak:
        lines = ["\n## Underperforming Skills (consider fixing)"]
        for s in weak:
            lines.append(f"- **{s.meta.name}** ({s.id}): {s.success_rate:.0%} success over {s.total_used} uses")
        extra = "\n".join(lines)

    return json.dumps({
        "analysis_prompt": prompt + extra,
        "message": "Read the analysis_prompt above. Respond with a JSON array of evolution suggestions, then call evolve_skills with it.",
    }, ensure_ascii=False)


@mcp.tool()
def evolve_skills(suggestions_json: str) -> str:
    """Apply skill evolution suggestions.

    Call this with the JSON array you produced after reading the analysis prompt.

    Args:
        suggestions_json: JSON array of suggestions, each with:
            - type: "capture" (new skill) or "fix" (improve existing)
            - skill_id: existing skill ID (required for fix, null for capture)
            - skill_name: human-readable name
            - reason: why this evolution is needed
            - new_content: full SKILL.md content (YAML frontmatter + markdown instructions)
    """
    results = _evolver.apply_suggestions(suggestions_json)

    return json.dumps({
        "results": results,
        "stats": _store.get_stats(),
    }, ensure_ascii=False)


@mcp.tool()
def get_stats() -> str:
    """Get Chrysalis statistics — skill count, executions, evolutions."""
    stats = _store.get_stats()
    skills = _store.list_skills(active_only=True)

    skill_list = []
    for s in skills[:20]:
        skill_list.append({
            "id": s.id,
            "name": s.meta.name,
            "version": s.meta.version,
            "success_rate": f"{s.success_rate:.0%}" if s.total_used > 0 else "new",
            "times_used": s.total_used,
        })

    return json.dumps({
        **stats,
        "skills": skill_list,
    }, ensure_ascii=False)


# --- Entry point ---


def main():
    mcp.run()


if __name__ == "__main__":
    main()
