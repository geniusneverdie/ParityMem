"""Five-layer interface parity checker with first-divergence localization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from paritymem.trace.events import CanonicalEvent


@dataclass(frozen=True)
class Difference:
    difference_type: str
    contract_layer: str
    official_value: Any
    adapter_value: Any
    first_divergence_event: str
    order_index: int
    source_stage: str
    source_file: str
    source_function: str
    source_identifier: str
    object_id: str | None
    downstream_affected_events: list[str]
    severity: str
    reason_code: str
    inferred_mutation_class: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParityResult:
    passed: bool
    compared_events: int
    layer_pass: dict[str, bool]
    differences: list[Difference]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "compared_events": self.compared_events,
            "layer_pass": self.layer_pass,
            "differences": [difference.to_dict() for difference in self.differences],
        }


def _list_ids(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    ids: list[str] = []
    for item in value:
        if isinstance(item, dict):
            identity = item.get("id", item.get("handle", item.get("name")))
        else:
            identity = item
        if identity is None:
            return None
        ids.append(str(identity))
    return ids


def _classify(
    official: CanonicalEvent,
    adapter: CanonicalEvent,
) -> tuple[str, str, str, str | None, str | None] | None:
    op = official.canonical_payload
    ap = adapter.canonical_payload
    if official.event_type != adapter.event_type:
        return ("P0_SCHEMA", "EVENT_TYPE_MISMATCH", "CRITICAL", None, None)

    if op.get("schema") != ap.get("schema"):
        return ("P0_SCHEMA", "SCHEMA_MISMATCH", "HIGH", None, None)

    for key in ("items", "tools", "records", "handles"):
        official_ids = _list_ids(op.get(key))
        adapter_ids = _list_ids(ap.get(key))
        if official_ids is None and adapter_ids is None:
            continue
        if set(official_ids or []) != set(adapter_ids or []):
            added = sorted(set(adapter_ids or []) - set(official_ids or []))
            omitted = sorted(set(official_ids or []) - set(adapter_ids or []))
            object_id = (added or omitted or [None])[0]
            if added:
                return ("P1_SET", "EXTRA_ITEM", "HIGH", object_id, "M1_EXTRA_ACTION_OR_HANDLE")
            kinds = {str(item.get("kind")) for item in (op.get(key) or []) if isinstance(item, dict) and str(item.get("id", item.get("handle", item.get("name")))) in omitted}
            if "lure" in kinds or "decoy" in kinds:
                return ("P1_SET", "LURE_OR_DECOY_OMISSION", "HIGH", object_id, "M3_LURE_OR_DECOY_OMISSION")
            return ("P1_SET", "OFFICIAL_ITEM_OMISSION", "HIGH", object_id, "M2_ACTIVE_ACTION_OMISSION")
        if official_ids != adapter_ids:
            return ("P2_ORDERED", "ORDER_MISMATCH", "MEDIUM", None, None)

    if op.get("aliases") != ap.get("aliases"):
        official_aliases = op.get("aliases") or {}
        aliases = ap.get("aliases") or {}
        changed = sorted(key for key in set(official_aliases) | set(aliases) if official_aliases.get(key) != aliases.get(key))
        object_id = changed[0] if changed else None
        return ("P1_SET", "ALIAS_COLLISION_OR_REBINDING", "CRITICAL", object_id, "M5_ALIAS_COLLISION_OR_REBINDING")

    if official.event_type in {"STATE_MUTATED", "TRANSITION_COMMITTED", "REWARD_EMITTED", "TERMINAL_REACHED"} and op != ap:
        return ("P3_TRANSITION", "STATE_OR_TRANSITION_MISMATCH", "CRITICAL", op.get("object_id"), "M4_STATE_UPDATE_LAG")

    if official.event_type in {"SCORER_INPUT_CREATED", "SCORER_OUTPUT_CREATED"} and op != ap:
        return ("P4_SCORER", "SCORER_MAPPING_MISMATCH", "CRITICAL", ap.get("scorer_id", ap.get("task_id")), "M6_SCORER_MAPPING_DRIFT")

    if op != ap:
        return ("P0_SCHEMA", "CANONICAL_PAYLOAD_MISMATCH", "MEDIUM", op.get("object_id"), None)
    return None


def check_parity(
    official_events: list[CanonicalEvent],
    adapter_events: list[CanonicalEvent],
) -> ParityResult:
    layers = {f"P{i}_{name}": True for i, name in enumerate(("SCHEMA", "SET", "ORDERED", "TRANSITION", "SCORER"))}
    differences: list[Difference] = []
    count = min(len(official_events), len(adapter_events))
    for index in range(count):
        official = official_events[index]
        adapter = adapter_events[index]
        classified = _classify(official, adapter)
        if classified is None:
            continue
        layer, reason, severity, object_id, mutation = classified
        layers[layer] = False
        affected = [event.event_id for event in adapter_events[index + 1 :]]
        differences.append(
            Difference(
                difference_type=reason,
                contract_layer=layer,
                official_value=official.canonical_payload,
                adapter_value=adapter.canonical_payload,
                first_divergence_event=adapter.event_id,
                order_index=adapter.order_index,
                source_stage=adapter.adapter_stage,
                source_file=adapter.source_file,
                source_function=adapter.source_function,
                source_identifier=adapter.source_identifier,
                object_id=object_id,
                downstream_affected_events=affected,
                severity=severity,
                reason_code=reason,
                inferred_mutation_class=mutation,
            )
        )
        break
    if len(official_events) != len(adapter_events) and not differences:
        event = (adapter_events or official_events)[count - 1 if count else 0]
        layers["P0_SCHEMA"] = False
        differences.append(
            Difference(
                difference_type="EVENT_COUNT_MISMATCH",
                contract_layer="P0_SCHEMA",
                official_value=len(official_events),
                adapter_value=len(adapter_events),
                first_divergence_event=event.event_id,
                order_index=count,
                source_stage=event.adapter_stage,
                source_file=event.source_file,
                source_function=event.source_function,
                source_identifier=event.source_identifier,
                object_id=None,
                downstream_affected_events=[],
                severity="CRITICAL",
                reason_code="EVENT_COUNT_MISMATCH",
                inferred_mutation_class=None,
            )
        )
    return ParityResult(not differences, count, layers, differences)
