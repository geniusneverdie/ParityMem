"""No-model STATE-Bench fixture reconstruction using frozen official tasks."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

from .common import build_fixture_trace


def _official_modules(source: Path):
    sys.path.insert(0, str(source))
    try:
        from state_bench.domain import get_domain_config
        from state_bench.schemas import StateDiff, TaskDefinition
        from state_bench.scoring import evaluate_state_requirements
    finally:
        sys.path.pop(0)
    return get_domain_config, StateDiff, TaskDefinition, evaluate_state_requirements


def _domain_name(task_path: Path) -> str:
    return task_path.parts[task_path.parts.index("domains") + 1]


def _tool_items(schemas: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    items = []
    aliases = {}
    for schema in schemas:
        function = schema.get("function", schema)
        name = str(function.get("name"))
        items.append(
            {
                "id": name,
                "kind": "tool",
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {}),
            }
        )
        aliases[name] = name
    return items, aliases


def _score_dict(score: Any) -> dict[str, Any]:
    if score is None:
        return {"score": None, "reasoning": "not deterministically scorable", "reward": None}
    return {"score": int(score.score), "reasoning": score.reasoning, "details": score.details, "reward": int(score.score)}


def build_state_bench_fixtures(source: str | Path, commit: str, *, limit: int = 100) -> tuple[list[Any], list[Any], dict[str, Any]]:
    source = Path(source)
    get_domain_config, StateDiff, TaskDefinition, evaluate_state_requirements = _official_modules(source)
    task_paths = sorted(source.glob("state_bench/domains/*/tasks/*.json"))[:limit]
    official_bundles = []
    adapter_bundles = []
    domain_counts: dict[str, int] = {}

    for index, task_path in enumerate(task_paths):
        raw_task = json.loads(task_path.read_text(encoding="utf-8"))
        task = TaskDefinition.from_dict(raw_task)
        domain_name = _domain_name(task_path)
        domain_counts[domain_name] = domain_counts.get(domain_name, 0) + 1
        domain = get_domain_config(domain_name)
        official_tools, official_aliases = _tool_items(domain.tool_schemas)
        # Independent adapter projection from the same documented static schema.
        adapter_tools, adapter_aliases = _tool_items(deepcopy(domain.tool_schemas))
        env_path = source / str(task.task_env_path)
        initial_state = json.loads(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
        empty_diff = StateDiff()
        official_score = _score_dict(evaluate_state_requirements(task, empty_diff))
        observation = [
            {"id": "opening_message", "kind": "user", "value": task.opening_message},
            {"id": "runtime_now", "kind": "environment", "value": task.now},
            {"id": "user_id", "kind": "identifier", "value": task.user_id},
        ]
        scorer_input = {
            "scorer_id": task.task_id,
            "task_id": task.task_id,
            "state_requirements": task.state_requirements,
            "state_diff": empty_diff.to_dict(),
            "task_requirements_excluded": True,
        }
        fixture_id = f"state_bench:{domain_name}:{task.task_id}"
        relative_task = task_path.relative_to(source).as_posix()
        official_bundles.append(
            build_fixture_trace(
                benchmark="state_bench", commit=commit, fixture_id=fixture_id, task_id=task.task_id,
                step=0, observation_items=observation, action_items=official_tools, aliases=official_aliases,
                state_before=initial_state, state_after=initial_state, scorer_input=scorer_input,
                scorer_output=official_score, source_file=relative_task,
                source_function="TaskDefinition/run_task/evaluate_state_requirements",
                source_identifier=task.task_id, source_stage="official", terminal=True,
            )
        )
        adapter_bundles.append(
            build_fixture_trace(
                benchmark="state_bench", commit=commit, fixture_id=fixture_id, task_id=task.task_id,
                step=0, observation_items=deepcopy(observation), action_items=adapter_tools, aliases=adapter_aliases,
                state_before=deepcopy(initial_state), state_after=deepcopy(initial_state),
                scorer_input=deepcopy(scorer_input), scorer_output=deepcopy(official_score),
                source_file="paritymem/adapters/state_bench.py",
                source_function="build_state_bench_fixtures", source_identifier=task.task_id,
                source_stage="adapter", terminal=True,
            )
        )
    return official_bundles, adapter_bundles, {
        "fixture_count": len(official_bundles),
        "available_official_tasks": len(list(source.glob("state_bench/domains/*/tasks/*.json"))),
        "official_source_kind": "official_task_and_environment_fixtures",
        "domain_counts": domain_counts,
        "llm_judges_excluded": True,
    }
