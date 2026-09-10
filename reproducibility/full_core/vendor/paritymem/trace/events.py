"""Raw-plus-canonical event representation for benchmark parity audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable

from paritymem.audit.io import atomic_write_bytes, canonical_json_bytes, sha256_bytes


EVENT_TYPES = (
    "SESSION_STARTED",
    "OBSERVATION_EMITTED",
    "MEMORY_READ_REQUESTED",
    "MEMORY_READ_RETURNED",
    "MEMORY_WRITE_REQUESTED",
    "MEMORY_WRITE_COMMITTED",
    "ACTION_MENU_EMITTED",
    "ACTION_SUBMITTED",
    "TOOL_CALLED",
    "TOOL_RETURNED",
    "TRANSITION_STARTED",
    "STATE_MUTATED",
    "TRANSITION_COMMITTED",
    "REWARD_EMITTED",
    "TERMINAL_REACHED",
    "SCORER_INPUT_CREATED",
    "SCORER_OUTPUT_CREATED",
)

STAGES = {
    "official_interface",
    "observation_adapter",
    "memory_adapter",
    "action_adapter",
    "state_adapter",
    "transition_adapter",
    "scorer_adapter",
}


@dataclass
class CanonicalEvent:
    benchmark: str
    upstream_commit: str
    session_id: str
    task_id: str
    step: int
    event_type: str
    raw_payload_hash: str
    canonical_payload: dict[str, Any]
    source_file: str
    source_function: str
    source_identifier: str
    parent_event: str | None
    provenance_chain: list[dict[str, Any]]
    order_index: int
    authority: str
    contract_layer: str
    adapter_stage: str
    event_id: str = ""
    ignored_fields: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        benchmark: str,
        upstream_commit: str,
        session_id: str,
        task_id: str,
        step: int,
        event_type: str,
        raw_payload: Any,
        canonical_payload: dict[str, Any],
        source_file: str,
        source_function: str,
        source_identifier: str,
        parent_event: str | None,
        provenance_chain: list[dict[str, Any]],
        order_index: int,
        authority: str,
        contract_layer: str,
        adapter_stage: str,
        ignored_fields: list[str] | None = None,
    ) -> "CanonicalEvent":
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown canonical event type: {event_type}")
        if adapter_stage not in STAGES:
            raise ValueError(f"unknown adapter stage: {adapter_stage}")
        raw_hash = sha256_bytes(canonical_json_bytes(raw_payload))
        identity = {
            "benchmark": benchmark,
            "session_id": session_id,
            "task_id": task_id,
            "step": step,
            "event_type": event_type,
            "order_index": order_index,
            "raw_payload_hash": raw_hash,
        }
        event_id = sha256_bytes(canonical_json_bytes(identity))[:24]
        return cls(
            benchmark=benchmark,
            upstream_commit=upstream_commit,
            session_id=session_id,
            task_id=task_id,
            step=step,
            event_type=event_type,
            raw_payload_hash=raw_hash,
            canonical_payload=canonical_payload,
            source_file=source_file,
            source_function=source_function,
            source_identifier=source_identifier,
            parent_event=parent_event,
            provenance_chain=provenance_chain,
            order_index=order_index,
            authority=authority,
            contract_layer=contract_layer,
            adapter_stage=adapter_stage,
            event_id=event_id,
            ignored_fields=list(ignored_fields or []),
        )

    def validate(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise ValueError(self.event_type)
        if self.adapter_stage not in STAGES:
            raise ValueError(self.adapter_stage)
        if self.authority not in {"AUTHORITATIVE", "DERIVED"}:
            raise ValueError(self.authority)
        if self.order_index < 0 or self.step < 0:
            raise ValueError("negative step/order")
        if not self.provenance_chain:
            raise ValueError("provenance chain is required")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass
class TraceBundle:
    benchmark: str
    fixture_id: str
    raw_events: list[dict[str, Any]]
    canonical_events: list[CanonicalEvent]
    normalization_log: list[dict[str, Any]]
    ignored_field_definitions: dict[str, str]
    order_sensitivity: dict[str, bool]

    def validate(self) -> None:
        if len(self.raw_events) != len(self.canonical_events):
            raise ValueError("raw/canonical event count mismatch")
        previous = -1
        ids: set[str] = set()
        for event in self.canonical_events:
            event.validate()
            if event.order_index <= previous:
                raise ValueError("canonical events are not strictly ordered")
            if event.parent_event is not None and event.parent_event not in ids:
                raise ValueError("parent event must precede child")
            previous = event.order_index
            ids.add(event.event_id)


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def write_trace_bundle(bundle: TraceBundle, directory: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    bundle.validate()
    root = Path(directory)
    raw_path = root / "raw_trace.jsonl"
    canonical_path = root / "canonical_trace.jsonl"
    normalization_path = root / "normalization_log.jsonl"
    definition_path = root / "trace_definitions.json"
    atomic_write_bytes(raw_path, _jsonl_bytes(bundle.raw_events), overwrite=overwrite)
    atomic_write_bytes(
        canonical_path,
        _jsonl_bytes(event.to_dict() for event in bundle.canonical_events),
        overwrite=overwrite,
    )
    atomic_write_bytes(normalization_path, _jsonl_bytes(bundle.normalization_log), overwrite=overwrite)
    atomic_write_bytes(
        definition_path,
        canonical_json_bytes(
            {
                "ignored_fields": bundle.ignored_field_definitions,
                "order_sensitivity": bundle.order_sensitivity,
            }
        ) + b"\n",
        overwrite=overwrite,
    )
    return {
        "benchmark": bundle.benchmark,
        "fixture_id": bundle.fixture_id,
        "event_count": len(bundle.canonical_events),
        "raw_trace_sha256": sha256_bytes(raw_path.read_bytes()),
        "canonical_trace_sha256": sha256_bytes(canonical_path.read_bytes()),
    }


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
