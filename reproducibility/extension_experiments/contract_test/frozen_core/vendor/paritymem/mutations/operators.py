"""Single-layer mutation operators for frozen canonical traces."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from paritymem.trace.events import CanonicalEvent


MUTATION_CLASSES = (
    "M1_EXTRA_ACTION_OR_HANDLE",
    "M2_ACTIVE_ACTION_OMISSION",
    "M3_LURE_OR_DECOY_OMISSION",
    "M4_STATE_UPDATE_LAG",
    "M5_ALIAS_COLLISION_OR_REBINDING",
    "M6_SCORER_MAPPING_DRIFT",
)


def _replace_payload(event: CanonicalEvent, payload: dict[str, Any], *, object_id: str, mutation_id: str) -> CanonicalEvent:
    provenance = [*event.provenance_chain, {"mutation_id": mutation_id, "object_id": object_id, "operation": "controlled_adapter_distortion"}]
    return replace(event, canonical_payload=payload, provenance_chain=provenance, source_identifier=object_id)


def apply_mutation(
    events: list[CanonicalEvent],
    mutation: dict[str, Any],
) -> list[CanonicalEvent]:
    """Apply exactly one pre-registered mutation to an adapter trace."""
    mutation_class = mutation["mutation_class"]
    if mutation_class not in MUTATION_CLASSES:
        raise ValueError(f"unsupported mutation: {mutation_class}")
    result = deepcopy(events)
    target_index = int(mutation["target_order_index"])
    matches = [index for index, event in enumerate(result) if event.order_index == target_index]
    if len(matches) != 1:
        raise ValueError("mutation target must resolve to exactly one event")
    index = matches[0]
    event = result[index]
    payload = deepcopy(event.canonical_payload)
    object_id = str(mutation["source_object"])

    if mutation_class == "M1_EXTRA_ACTION_OR_HANDLE":
        key = mutation.get("collection_key", "items")
        payload.setdefault(key, []).append({"id": object_id, "kind": "injected", "authority": "adapter"})
    elif mutation_class in {"M2_ACTIVE_ACTION_OMISSION", "M3_LURE_OR_DECOY_OMISSION"}:
        key = mutation.get("collection_key", "items")
        before = payload.get(key, [])
        payload[key] = [item for item in before if str(item.get("id", item.get("handle", item.get("name")))) != object_id]
        if len(payload[key]) == len(before):
            raise ValueError("omission target absent")
    elif mutation_class == "M4_STATE_UPDATE_LAG":
        payload["state"] = deepcopy(mutation["lagged_state"])
        payload["object_id"] = object_id
    elif mutation_class == "M5_ALIAS_COLLISION_OR_REBINDING":
        aliases = deepcopy(payload.get("aliases", {}))
        if len(aliases) < 2:
            raise ValueError("alias mutation needs at least two bindings")
        names = sorted(aliases)
        aliases[names[1]] = aliases[names[0]]
        payload["aliases"] = aliases
    elif mutation_class == "M6_SCORER_MAPPING_DRIFT":
        payload["scorer_id"] = str(mutation["replacement_scorer_id"])
    result[index] = _replace_payload(event, payload, object_id=object_id, mutation_id=mutation["mutation_id"])
    return result
