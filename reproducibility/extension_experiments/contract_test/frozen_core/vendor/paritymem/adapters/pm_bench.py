"""Independent PM-Bench menu/state reconstruction over frozen official data."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random
import re
from typing import Any

from .common import build_fixture_trace


def _load_official(source: Path):
    spec = importlib.util.spec_from_file_location("paritymem_official_pm_bench", source / "sim" / "pm_bench.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen PM-Bench source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _encoding(value: str) -> tuple[str, str | None]:
    if value == "start":
        return "start", None
    if value.startswith("step:"):
        return "step", value.split(":", 1)[1]
    raise ValueError(value)


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _action_text(task: dict[str, Any], current: dict[str, Any]) -> str:
    if current.get("action_text"):
        return current["action_text"]
    label = (current.get("label") or task.get("label") or "").strip().rstrip(".")
    label = re.sub(r"\s+when\s+.*$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+(at|around)\s+\d{1,2}:\d{2}$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+after\s+.*$", "", label, flags=re.IGNORECASE)
    return _sentence(f"{label}.") if label else "Do the task."


def _init(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "completed": False,
        "completed_at": None,
        "cue_seen": False,
        "cue_step_idx": None,
        "active": False,
        "result": None,
        "task": deepcopy(task),
        "current": {
            "type": task.get("type"),
            "cue_id": task.get("cue_id"),
            "cue_channel": task.get("cue_channel", "narrative"),
            "target_time": task.get("target_time"),
            "window_before": task.get("window_before"),
            "window_after": task.get("window_after"),
            "label": task.get("label"),
            "action_text": task.get("action_text"),
        },
        "canceled": False,
        "canceled_by_dependency": False,
        "updated": False,
        "has_update": False,
        "completion_had_required_query": False,
    }


def _cancel(states: dict[str, dict[str, Any]], task_id: str) -> None:
    state = states[task_id]
    if state["canceled"]:
        return
    state["canceled"] = True
    state["result"] = "canceled"
    for dependent_id, dependent in states.items():
        if dependent["task"].get("depends_on") == task_id and not dependent["canceled"]:
            dependent["canceled_by_dependency"] = True
            _cancel(states, dependent_id)


def _apply_update(states: dict[str, dict[str, Any]], update: dict[str, Any]) -> None:
    task_id = update.get("task_id")
    if task_id not in states or states[task_id]["completed"]:
        return
    state = states[task_id]
    action = update.get("action")
    if action == "cancel":
        _cancel(states, task_id)
        return
    if action not in {"reschedule", "override"}:
        return
    state["updated"] = True
    mapping = {
        "new_type": "type",
        "new_cue_id": "cue_id",
        "new_target_time": "target_time",
        "new_window_before": "window_before",
        "new_window_after": "window_after",
        "new_label": "label",
        "new_action_text": "action_text",
    }
    for source, target in mapping.items():
        if source in update and update[source] is not None:
            state["current"][target] = update[source]
            if source in {"new_cue_id", "new_target_time"}:
                state["cue_seen"] = False
                state["cue_step_idx"] = None


def _lures(raw: list[Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for lure in raw:
        if isinstance(lure, str):
            item = {"id": lure, "action_text": _sentence(lure.replace("_", " ") + ".")}
        elif isinstance(lure, dict) and lure.get("id"):
            item = {"id": lure["id"], "action_text": lure.get("action_text") or _sentence(lure["id"].replace("_", " ") + ".")}
        else:
            continue
        if item["id"] not in seen:
            result.append(item)
            seen.add(item["id"])
    return result


def _handles(states: dict[str, Any], lure_catalog: list[dict[str, str]], seed_key: str) -> dict[str, str]:
    identities = sorted(set(states) | {item["id"] for item in lure_catalog})
    random.Random(seed_key).shuffle(identities)
    return {identity: f"task_{index}" for index, identity in enumerate(identities, 1)}


def _menu(
    states: dict[str, dict[str, Any]],
    active: set[str],
    lure_catalog: list[dict[str, str]],
    handles: dict[str, str],
    day: str,
    step: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    tasks = []
    for task_id in sorted(active):
        state = states.get(task_id)
        if state and state["active"] and not state["completed"]:
            tasks.append({"id": task_id, "handle": handles[task_id], "action_text": _action_text(state["task"], state["current"])})
    sample_size = min(3, len(lure_catalog))
    sampled = random.Random(f"{day}:{step}:lures").sample(lure_catalog, k=sample_size) if sample_size else []
    lures = [{"id": lure["id"], "handle": handles[lure["id"]], "action_text": lure["action_text"]} for lure in sampled]
    entries = tasks + lures
    random.Random(f"{day}:{step}:menu").shuffle(entries)
    return entries, {entry["handle"]: entry["id"] for entry in entries}


def _state_view(states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        task_id: {
            "active": state["active"],
            "completed": state["completed"],
            "canceled": state["canceled"],
            "current": state["current"],
        }
        for task_id, state in sorted(states.items())
    }


def _menu_view(entries: list[dict[str, Any]], lure_ids: set[str], states: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": entry["handle"],
            "source_id": entry["id"],
            "kind": "lure" if entry["id"] in lure_ids else "task",
            "action_text": entry["action_text"],
            "canceled": bool(states.get(entry["id"], {}).get("canceled", False)),
        }
        for entry in entries
    ]


def build_pm_bench_fixtures(source: str | Path, commit: str) -> tuple[list[Any], list[Any], dict[str, Any]]:
    source = Path(source)
    official = _load_official(source)
    scenario_path = source / "data" / "synthetic_week_v9.json"
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    updates = official.build_updates_by_day(scenario)
    official_bundles = []
    adapter_bundles = []
    menu_comparisons = []

    for day in scenario["days"]:
        day_name = day["name"]
        official_states = {task["id"]: official.init_task_state(task) for task in day["tasks"]}
        local_states = {task["id"]: _init(task) for task in day["tasks"]}
        official_active: set[str] = set()
        local_active: set[str] = set()
        for task in day["tasks"]:
            kind, _ = _encoding(task["encoding"])
            if kind == "start":
                official_active.add(task["id"])
                local_active.add(task["id"])
                official_states[task["id"]]["active"] = True
                local_states[task["id"]]["active"] = True
        day_updates = updates[day_name]
        for update in day_updates["pre"]:
            if update.get("task_id") in official_states:
                official.apply_task_update(official_states[update["task_id"]], update, task_states=official_states)
                _apply_update(local_states, update)
        official_lures = official.normalize_lure_catalog(day.get("lures", []))
        local_lures = _lures(day.get("lures", []))
        official_handles, _ = official.build_day_handle_maps(official_states, official_lures, f"{day_name}:handles")
        local_handles = _handles(local_states, local_lures, f"{day_name}:handles")
        lure_ids = {item["id"] for item in local_lures}

        for step_index, step in enumerate(day["steps"]):
            for update in day_updates["by_step"].get(step["id"], []):
                if update.get("task_id") in official_states:
                    official.apply_task_update(official_states[update["task_id"]], update, task_states=official_states)
                    _apply_update(local_states, update)
            for task in day["tasks"]:
                kind, at_step = _encoding(task["encoding"])
                if kind == "step" and at_step == step["id"]:
                    official_active.add(task["id"])
                    local_active.add(task["id"])
                    official_states[task["id"]]["active"] = True
                    local_states[task["id"]]["active"] = True
            official_menu, official_aliases = official.build_step_action_menu(
                official_states, official_active, official_lures, official_handles, day_name, step["id"]
            )
            local_menu, local_aliases = _menu(local_states, local_active, local_lures, local_handles, day_name, step["id"])
            observation = [
                {"id": "step_text", "kind": "environment", "value": step["text"]},
                *[{"id": f"option_{index}", "kind": "option", "value": option} for index, option in enumerate(step["options"])],
            ]
            if scenario.get("time_visible_by_default"):
                observation.append({"id": "clock", "kind": "state", "value": step["time"]})
            expected_ids = [action["id"] for action in step.get("groundtruth", {}).get("actions", [])]
            scorer_input = {
                "scorer_id": f"{day_name}:{step['id']}",
                "task_id": f"{day_name}:{step['id']}",
                "selected_ids": [],
                "expected_ids": expected_ids,
            }
            scorer_output = {
                "scorer_id": f"{day_name}:{step['id']}",
                "set_tp": 0,
                "set_fp": 0,
                "set_fn": len(expected_ids),
                "reward": 1 if not expected_ids else -1,
            }
            fixture_id = f"pm_bench:{day_name}:{step['id']}"
            official_view = _state_view(official_states)
            local_view = _state_view(local_states)
            official_bundles.append(
                build_fixture_trace(
                    benchmark="pm_bench", commit=commit, fixture_id=fixture_id, task_id=fixture_id,
                    step=step_index, observation_items=observation,
                    action_items=_menu_view(official_menu, lure_ids, official_states), aliases=official_aliases,
                    state_before=official_view, state_after=official_view, scorer_input=scorer_input,
                    scorer_output=scorer_output, source_file="sim/pm_bench.py",
                    source_function="build_step_action_menu/score_day", source_identifier=step["id"], source_stage="official",
                    terminal=step_index == len(day["steps"]) - 1,
                )
            )
            adapter_bundles.append(
                build_fixture_trace(
                    benchmark="pm_bench", commit=commit, fixture_id=fixture_id, task_id=fixture_id,
                    step=step_index, observation_items=deepcopy(observation),
                    action_items=_menu_view(local_menu, lure_ids, local_states), aliases=local_aliases,
                    state_before=local_view, state_after=local_view, scorer_input=deepcopy(scorer_input),
                    scorer_output=deepcopy(scorer_output), source_file="paritymem/adapters/pm_bench.py",
                    source_function="_menu/build_pm_bench_fixtures", source_identifier=step["id"], source_stage="adapter",
                    terminal=step_index == len(day["steps"]) - 1,
                )
            )
            menu_comparisons.append({"fixture_id": fixture_id, "official_count": len(official_menu), "adapter_count": len(local_menu)})
    return official_bundles, adapter_bundles, {
        "scenario": scenario_path.relative_to(source).as_posix(),
        "fixture_count": len(official_bundles),
        "official_source_kind": "official_saved_scenario",
        "menu_comparisons": menu_comparisons,
    }
