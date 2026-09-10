"""Deterministic pre-registration of supported single-interface mutations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from paritymem.audit.io import canonical_json_bytes, sha256_bytes
from paritymem.trace.events import TraceBundle
from .operators import apply_mutation


EXPECTED = {
    "M1_EXTRA_ACTION_OR_HANDLE": ("P1_SET", "action_adapter", "HIGH"),
    "M2_ACTIVE_ACTION_OMISSION": ("P1_SET", "action_adapter", "HIGH"),
    "M3_LURE_OR_DECOY_OMISSION": ("P1_SET", "action_adapter", "HIGH"),
    "M4_STATE_UPDATE_LAG": ("P3_TRANSITION", "state_adapter", "CRITICAL"),
    "M5_ALIAS_COLLISION_OR_REBINDING": ("P1_SET", "action_adapter", "CRITICAL"),
    "M6_SCORER_MAPPING_DRIFT": ("P4_SCORER", "scorer_adapter", "CRITICAL"),
}


def _event(bundle: TraceBundle, event_type: str):
    matches = [event for event in bundle.canonical_events if event.event_type == event_type]
    if len(matches) != 1:
        raise ValueError(f"{bundle.fixture_id}: expected one {event_type}")
    return matches[0]


def _item_id(item: dict[str, Any]) -> str:
    return str(item.get("id", item.get("handle", item.get("name"))))


def _spec(bundle: TraceBundle, mutation_class: str, ordinal: int) -> dict[str, Any] | None:
    layer, stage, severity = EXPECTED[mutation_class]
    mutation_id = f"{bundle.benchmark}:{mutation_class}:{ordinal:03d}"
    if mutation_class.startswith(("M1_", "M2_", "M3_", "M5_")):
        event = _event(bundle, "ACTION_MENU_EMITTED")
    elif mutation_class == "M4_STATE_UPDATE_LAG":
        event = _event(bundle, "STATE_MUTATED")
    else:
        event = _event(bundle, "SCORER_INPUT_CREATED")
    payload = event.canonical_payload
    specification: dict[str, Any] = {
        "mutation_id": mutation_id,
        "benchmark": bundle.benchmark,
        "fixture_id": bundle.fixture_id,
        "mutation_class": mutation_class,
        "adapter_stage": stage,
        "target_order_index": event.order_index,
        "expected_first_divergence": event.event_id,
        "expected_affected_contract_layer": layer,
        "expected_localization": stage,
        "expected_severity": severity,
        "collection_key": "items",
    }
    if mutation_class == "M1_EXTRA_ACTION_OR_HANDLE":
        specification["source_object"] = f"injected_{ordinal:03d}"
    elif mutation_class in {"M2_ACTIVE_ACTION_OMISSION", "M3_LURE_OR_DECOY_OMISSION"}:
        wanted_kind = "lure" if mutation_class.startswith("M3_") else None
        candidates = [item for item in payload.get("items", []) if wanted_kind is None or item.get("kind") == wanted_kind]
        if mutation_class.startswith("M2_"):
            candidates = [item for item in candidates if item.get("kind") not in {"lure", "decoy"}]
        if not candidates:
            return None
        specification["source_object"] = _item_id(candidates[0])
    elif mutation_class == "M4_STATE_UPDATE_LAG":
        specification["source_object"] = event.source_identifier
        specification["lagged_state"] = {"stale_snapshot": True, "fixture_id": bundle.fixture_id}
    elif mutation_class == "M5_ALIAS_COLLISION_OR_REBINDING":
        aliases = payload.get("aliases", {})
        if len(aliases) < 2:
            return None
        specification["source_object"] = sorted(aliases)[1]
    elif mutation_class == "M6_SCORER_MAPPING_DRIFT":
        specification["source_object"] = str(payload.get("scorer_id", payload.get("task_id")))
        specification["replacement_scorer_id"] = f"drifted:{specification['source_object']}"
    mutated = apply_mutation(bundle.canonical_events, specification)
    specification["before_payload_hash"] = sha256_bytes(canonical_json_bytes(event.canonical_payload))
    mutated_event = next(candidate for candidate in mutated if candidate.order_index == event.order_index)
    specification["after_payload_hash"] = sha256_bytes(canonical_json_bytes(mutated_event.canonical_payload))
    return specification


def build_registry(
    bundles_by_benchmark: dict[str, list[TraceBundle]],
    *,
    per_class_per_benchmark: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    support = {
        "pm_bench": [
            "M1_EXTRA_ACTION_OR_HANDLE", "M2_ACTIVE_ACTION_OMISSION", "M3_LURE_OR_DECOY_OMISSION",
            "M4_STATE_UPDATE_LAG", "M5_ALIAS_COLLISION_OR_REBINDING", "M6_SCORER_MAPPING_DRIFT",
        ],
        "state_bench": [
            "M1_EXTRA_ACTION_OR_HANDLE", "M2_ACTIVE_ACTION_OMISSION", "M4_STATE_UPDATE_LAG",
            "M5_ALIAS_COLLISION_OR_REBINDING", "M6_SCORER_MAPPING_DRIFT",
        ],
        "memory_agent_bench": ["M6_SCORER_MAPPING_DRIFT"],
        "memory_arena": [],
    }
    registry: list[dict[str, Any]] = []
    for benchmark, mutation_classes in support.items():
        bundles = bundles_by_benchmark.get(benchmark, [])
        for mutation_class in mutation_classes:
            registered = 0
            for bundle in bundles:
                specification = _spec(bundle, mutation_class, registered)
                if specification is None:
                    continue
                registry.append(specification)
                registered += 1
                if registered == per_class_per_benchmark:
                    break
            if registered < per_class_per_benchmark:
                raise ValueError(f"insufficient fixtures for {benchmark}/{mutation_class}: {registered}")
    matrix = {
        benchmark: {
            mutation: (mutation in support.get(benchmark, []))
            for mutation in EXPECTED
        }
        for benchmark in ("pm_bench", "state_bench", "memory_arena", "memory_agent_bench")
    }
    return registry, {"support_matrix": matrix, "mutation_count": len(registry), "mutations_per_supported_cell": per_class_per_benchmark}
