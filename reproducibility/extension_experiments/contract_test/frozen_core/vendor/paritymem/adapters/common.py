"""Shared, benchmark-neutral fixture-to-trace projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from paritymem.trace.events import CanonicalEvent, TraceBundle


def build_fixture_trace(
    *,
    benchmark: str,
    commit: str,
    fixture_id: str,
    task_id: str,
    step: int,
    observation_items: list[dict[str, Any]],
    action_items: list[dict[str, Any]],
    aliases: dict[str, str],
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    scorer_input: dict[str, Any],
    scorer_output: dict[str, Any],
    source_file: str,
    source_function: str,
    source_identifier: str,
    source_stage: str,
    memory_records: list[dict[str, Any]] | None = None,
    terminal: bool = True,
) -> TraceBundle:
    """Build a compact deterministic trace without inventing model behavior."""
    raw: list[dict[str, Any]] = []
    canonical: list[CanonicalEvent] = []
    parent: str | None = None

    def add(
        event_type: str,
        payload: dict[str, Any],
        *,
        layer: str,
        stage: str,
        authority: str = "AUTHORITATIVE",
        raw_payload: dict[str, Any] | None = None,
    ) -> None:
        nonlocal parent
        raw_value = deepcopy(raw_payload if raw_payload is not None else payload)
        event = CanonicalEvent.create(
            benchmark=benchmark,
            upstream_commit=commit,
            session_id=fixture_id,
            task_id=task_id,
            step=step,
            event_type=event_type,
            raw_payload=raw_value,
            canonical_payload=deepcopy(payload),
            source_file=source_file,
            source_function=source_function,
            source_identifier=source_identifier,
            parent_event=parent,
            provenance_chain=[
                {
                    "benchmark": benchmark,
                    "commit": commit,
                    "source_file": source_file,
                    "source_function": source_function,
                    "source_identifier": source_identifier,
                }
            ],
            order_index=len(canonical),
            authority=authority,
            contract_layer=layer,
            adapter_stage=stage,
        )
        raw.append(
            {
                "event_type": event_type,
                "payload": raw_value,
                "source_identifier": source_identifier,
                "order_index": len(canonical),
            }
        )
        canonical.append(event)
        parent = event.event_id

    add(
        "SESSION_STARTED",
        {"session_id": fixture_id, "task_id": task_id, "initial_state": state_before},
        layer="session_contract",
        stage=stage_for(source_stage, "official_interface"),
    )
    add(
        "OBSERVATION_EMITTED",
        {"items": observation_items, "schema": {"items": "ordered_list"}},
        layer="observation_contract",
        stage=stage_for(source_stage, "observation_adapter"),
    )
    if memory_records is not None:
        add(
            "MEMORY_READ_REQUESTED",
            {"query": task_id, "schema": {"query": "string"}},
            layer="memory_contract",
            stage=stage_for(source_stage, "memory_adapter"),
        )
        add(
            "MEMORY_READ_RETURNED",
            {"records": memory_records, "schema": {"records": "ordered_list"}},
            layer="memory_contract",
            stage=stage_for(source_stage, "memory_adapter"),
        )
    add(
        "ACTION_MENU_EMITTED",
        {
            "items": action_items,
            "aliases": aliases,
            "schema": {"items": "ordered_list", "aliases": "mapping"},
        },
        layer="action_contract",
        stage=stage_for(source_stage, "action_adapter"),
    )
    add(
        "ACTION_SUBMITTED",
        {"action": "NO_OP", "selected_ids": [], "schema": {"action": "string", "selected_ids": "list"}},
        layer="action_contract",
        stage=stage_for(source_stage, "action_adapter"),
    )
    add(
        "TRANSITION_STARTED",
        {"state": state_before, "action": "NO_OP"},
        layer="transition_contract",
        stage=stage_for(source_stage, "transition_adapter"),
    )
    add(
        "STATE_MUTATED",
        {"state": state_after, "object_id": task_id},
        layer="state_contract",
        stage=stage_for(source_stage, "state_adapter"),
    )
    add(
        "TRANSITION_COMMITTED",
        {"state": state_after, "idempotency_key": f"{fixture_id}:{step}:NO_OP"},
        layer="transition_contract",
        stage=stage_for(source_stage, "transition_adapter"),
    )
    add(
        "REWARD_EMITTED",
        {"reward": scorer_output.get("reward"), "deterministic": True},
        layer="transition_contract",
        stage=stage_for(source_stage, "transition_adapter"),
    )
    add(
        "TERMINAL_REACHED",
        {"terminal": terminal, "state": state_after},
        layer="session_contract",
        stage=stage_for(source_stage, "transition_adapter"),
    )
    add(
        "SCORER_INPUT_CREATED",
        scorer_input,
        layer="scorer_contract",
        stage=stage_for(source_stage, "scorer_adapter"),
    )
    add(
        "SCORER_OUTPUT_CREATED",
        scorer_output,
        layer="scorer_contract",
        stage=stage_for(source_stage, "scorer_adapter"),
    )
    bundle = TraceBundle(
        benchmark=benchmark,
        fixture_id=fixture_id,
        raw_events=raw,
        canonical_events=canonical,
        normalization_log=[
            {
                "fixture_id": fixture_id,
                "operation": "canonical_key_sort_for_hash_only",
                "semantic_order_preserved": True,
            }
        ],
        ignored_field_definitions={
            "wall_clock_timestamp": "nondeterministic telemetry; event order_index is authoritative",
            "elapsed_seconds": "nondeterministic performance telemetry",
        },
        order_sensitivity={
            "observation.items": True,
            "action.items": True,
            "memory.records": True,
            "scorer.items": True,
        },
    )
    bundle.validate()
    return bundle


def stage_for(source_stage: str, adapter_stage: str) -> str:
    return "official_interface" if source_stage == "official" else adapter_stage
