"""Opportunity-aware mutation lifecycle semantics.

The module is independent of model execution. It records assignment,
opportunity, materialization, and exposure separately and provides a
hash-chained append-only journal for crash-safe runners.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


class LifecycleInvariantError(RuntimeError):
    """Raised when a mutation lifecycle invariant is violated."""


class MutationLifecycleStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    ARMED = "ARMED"
    OPPORTUNITY_NOT_YET_OBSERVED = "OPPORTUNITY_NOT_YET_OBSERVED"
    OPPORTUNITY_OBSERVED = "OPPORTUNITY_OBSERVED"
    MATERIALIZED = "MATERIALIZED"
    EXPOSED_TO_MODEL = "EXPOSED_TO_MODEL"
    COMPLETED_WITH_EXPOSURE = "COMPLETED_WITH_EXPOSURE"
    COMPLETED_WITHOUT_OPPORTUNITY = "COMPLETED_WITHOUT_OPPORTUNITY"
    COMPLETE_MATERIALIZED_NOT_EXPOSED = "COMPLETE_MATERIALIZED_NOT_EXPOSED"
    MISSED_MATERIALIZATION = "MISSED_MATERIALIZATION"
    OVER_MATERIALIZATION = "OVER_MATERIALIZATION"
    MUTATION_RUNTIME_ERROR = "MUTATION_RUNTIME_ERROR"


class LifecycleEventType(str, Enum):
    ASSIGNMENT_PERSISTED = "ASSIGNMENT_PERSISTED"
    MUTATION_ARMED = "MUTATION_ARMED"
    OPPORTUNITY_PERSISTED = "OPPORTUNITY_PERSISTED"
    MATERIALIZATION_PERSISTED = "MATERIALIZATION_PERSISTED"
    EXPOSURE_PERSISTED = "EXPOSURE_PERSISTED"
    LIFECYCLE_COMPLETED = "LIFECYCLE_COMPLETED"


class RecoveryDisposition(str, Enum):
    NO_OP = "NO_OP"
    RESUME_OPPORTUNITY_DETECTION = "RESUME_OPPORTUNITY_DETECTION"
    RESUME_MATERIALIZATION_FROM_PERSISTED_OPPORTUNITY = (
        "RESUME_MATERIALIZATION_FROM_PERSISTED_OPPORTUNITY"
    )
    RESUME_EXPOSURE_FROM_PERSISTED_MATERIALIZATION = (
        "RESUME_EXPOSURE_FROM_PERSISTED_MATERIALIZATION"
    )
    RESUME_COMPLETION_FROM_PERSISTED_EXPOSURE = (
        "RESUME_COMPLETION_FROM_PERSISTED_EXPOSURE"
    )


@dataclass(frozen=True)
class MutationSpec:
    mutation_id: str
    mutation_class: str
    assignment_scope: str
    target_contract_layer: str
    opportunity_predicate: Mapping[str, Any]
    opportunity_cardinality: str
    materialization_rule: str
    materialization_cardinality_given_opportunity: str
    exposure_definition: str
    pre_exposure_invariance: tuple[str, ...]
    zero_opportunity_semantics: str
    multiple_opportunity_semantics: str
    provenance: tuple[str, ...]
    source_hash: str
    contract_version: str = "paritymem.mutation_lifecycle.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def sha256(self) -> str:
        return _hash_json(self.to_dict())


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def event_is_opportunity(spec: MutationSpec, event: Mapping[str, Any]) -> bool:
    """Evaluate the frozen score-independent opportunity predicate."""

    predicate = dict(spec.opportunity_predicate)
    kind = predicate.get("kind")
    if event.get("after_terminal"):
        return False
    if kind == "STATE_TARGET_TOOL_INVOCATION":
        targets = {str(predicate.get("tool_name", ""))}
        targets.update(str(value) for value in predicate.get("aliases", []))
        return (
            event.get("event_type") == "OFFICIAL_TOOL_CONSUMER_ATTEMPT"
            and str(event.get("tool_name")) in targets
            and str(event.get("validation_status"))
            in {"ACCEPTED", "COERCED", "REJECTED_CONTINUE"}
            and bool(event.get("official_consumer_attempted"))
        )
    if kind == "ACTION_MENU_EPOCH":
        return (
            event.get("event_type") == "ACTION_MENU_MATERIALIZATION_POINT"
            and str(event.get("menu_scope")) == str(predicate.get("menu_scope"))
        )
    if kind == "PM_FROZEN_STEP":
        return (
            event.get("event_type") == str(predicate.get("event_type"))
            and int(event.get("day", -1)) == int(predicate.get("day", -2))
            and int(event.get("step", -1)) == int(predicate.get("step", -2))
            and str(event.get("target_identity"))
            == str(predicate.get("target_identity"))
        )
    raise LifecycleInvariantError(f"unsupported opportunity predicate: {kind!r}")


class MutationLifecycleJournal:
    """Append-only, hash-chained lifecycle journal with idempotent recovery."""

    def __init__(
        self,
        path: str | Path,
        *,
        unit_id: str,
        spec: MutationSpec,
        condition: str = "MUTATED",
    ) -> None:
        self.path = Path(path)
        self.unit_id = unit_id
        self.spec = spec
        self.condition = condition
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events = self._read()
        self._validate_chain()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _validate_chain(self) -> None:
        previous = "0" * 64
        seen: set[str] = set()
        for row in self.events:
            if row.get("unit_id") != self.unit_id:
                raise LifecycleInvariantError("journal unit mismatch")
            if row.get("mutation_spec_hash") != self.spec.sha256():
                raise LifecycleInvariantError("journal mutation-spec mismatch")
            if row.get("event_id") in seen:
                raise LifecycleInvariantError("duplicate persisted event id")
            if row.get("previous_hash") != previous:
                raise LifecycleInvariantError("journal previous-hash mismatch")
            body = {key: value for key, value in row.items() if key != "event_hash"}
            if row.get("event_hash") != _hash_json(body):
                raise LifecycleInvariantError("journal event-hash mismatch")
            previous = row["event_hash"]
            seen.add(row["event_id"])

    def _append(
        self, event_type: LifecycleEventType, event_id: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        existing = [row for row in self.events if row["event_id"] == event_id]
        if existing:
            row = existing[0]
            if row["event_type"] != event_type.value or row["payload"] != dict(payload):
                raise LifecycleInvariantError("event-id reuse with different content")
            return row
        if self.events and (
            self.events[-1]["event_type"] == LifecycleEventType.LIFECYCLE_COMPLETED.value
        ):
            raise LifecycleInvariantError("event after lifecycle completion")
        previous = self.events[-1]["event_hash"] if self.events else "0" * 64
        row = {
            "schema_version": "paritymem.mutation_lifecycle_journal.v1",
            "unit_id": self.unit_id,
            "mutation_id": self.spec.mutation_id,
            "mutation_spec_hash": self.spec.sha256(),
            "event_id": event_id,
            "event_type": event_type.value,
            "created_at": _now(),
            "previous_hash": previous,
            "payload": dict(payload),
        }
        row["event_hash"] = _hash_json(row)
        with self.path.open("ab", buffering=0) as handle:
            handle.write(_canonical(row) + b"\n")
            os.fsync(handle.fileno())
        directory_fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        self.events.append(row)
        return row

    def _existing(
        self, event_type: LifecycleEventType, event_id: str
    ) -> dict[str, Any] | None:
        for row in self.events:
            if row["event_id"] == event_id:
                if row["event_type"] != event_type.value:
                    raise LifecycleInvariantError(
                        "event-id reuse with different event type"
                    )
                return row
        return None

    def assign(self, *, assigned: bool = True) -> dict[str, Any]:
        return self._append(
            LifecycleEventType.ASSIGNMENT_PERSISTED,
            "assignment",
            {"assignment_status": "ASSIGNED" if assigned else "UNASSIGNED"},
        )

    def arm(self) -> dict[str, Any]:
        if self.condition == "CLEAN":
            raise LifecycleInvariantError("clean condition cannot arm mutation")
        if not self.events:
            raise LifecycleInvariantError("mutation must be assigned before armed")
        existing = self._existing(LifecycleEventType.MUTATION_ARMED, "armed")
        if existing is not None:
            return existing
        return self._append(
            LifecycleEventType.MUTATION_ARMED,
            "armed",
            {"armed_at": _now(), "status": MutationLifecycleStatus.ARMED.value},
        )

    def opportunity(
        self,
        *,
        event_id: str,
        event_type: str,
        canonical_trace_index: int,
        contract_layer: str,
        target_identity: str,
        pre_state_hash: str,
        source_provenance: str,
        after_terminal: bool = False,
    ) -> dict[str, Any]:
        if after_terminal:
            raise LifecycleInvariantError("opportunity after terminal")
        if not any(
            event["event_type"] == LifecycleEventType.MUTATION_ARMED.value
            for event in self.events
        ):
            raise LifecycleInvariantError("opportunity before arm")
        return self._append(
            LifecycleEventType.OPPORTUNITY_PERSISTED,
            event_id,
            {
                "event_type": event_type,
                "canonical_trace_index": canonical_trace_index,
                "contract_layer": contract_layer,
                "target_identity": target_identity,
                "pre_state_hash": pre_state_hash,
                "opportunity_predicate_result": True,
                "source_provenance": source_provenance,
            },
        )

    def materialize(
        self,
        *,
        materialization_id: str,
        opportunity_event_id: str,
        before_contract_ir_hash: str,
        after_contract_ir_hash: str,
        affected_object: str,
    ) -> dict[str, Any]:
        opportunity_ids = {
            event["event_id"]
            for event in self.events
            if event["event_type"] == LifecycleEventType.OPPORTUNITY_PERSISTED.value
        }
        if opportunity_event_id not in opportunity_ids:
            raise LifecycleInvariantError(
                "materialization without persisted opportunity"
            )
        if self.condition == "CLEAN":
            raise LifecycleInvariantError("clean condition accidentally materialized")
        existing = self._existing(
            LifecycleEventType.MATERIALIZATION_PERSISTED, materialization_id
        )
        if existing is not None:
            if (
                existing["payload"]["opportunity_event_id"]
                != opportunity_event_id
            ):
                raise LifecycleInvariantError(
                    "materialization-id reused for a different opportunity"
                )
            return existing
        return self._append(
            LifecycleEventType.MATERIALIZATION_PERSISTED,
            materialization_id,
            {
                "materialization_id": materialization_id,
                "opportunity_event_id": opportunity_event_id,
                "before_contract_ir_hash": before_contract_ir_hash,
                "after_contract_ir_hash": after_contract_ir_hash,
                "mutation_operator": self.spec.mutation_class,
                "affected_field_or_object": affected_object,
                "materialized_at": _now(),
            },
        )

    def expose(
        self,
        *,
        exposure_id: str,
        materialization_id: str,
        visibility: str,
        visible_artifact_hash: str,
    ) -> dict[str, Any]:
        materialization_ids = {
            event["event_id"]
            for event in self.events
            if event["event_type"] == LifecycleEventType.MATERIALIZATION_PERSISTED.value
        }
        if materialization_id not in materialization_ids:
            raise LifecycleInvariantError("exposure without materialization")
        return self._append(
            LifecycleEventType.EXPOSURE_PERSISTED,
            exposure_id,
            {
                "materialization_id": materialization_id,
                "visibility": visibility,
                "visible_artifact_hash": visible_artifact_hash,
            },
        )

    def counts(self) -> dict[str, int]:
        return {
            "opportunity_count": sum(
                event["event_type"] == LifecycleEventType.OPPORTUNITY_PERSISTED.value
                for event in self.events
            ),
            "materialization_count": sum(
                event["event_type"]
                == LifecycleEventType.MATERIALIZATION_PERSISTED.value
                for event in self.events
            ),
            "exposure_count": sum(
                event["event_type"] == LifecycleEventType.EXPOSURE_PERSISTED.value
                for event in self.events
            ),
        }

    def classify(self) -> MutationLifecycleStatus:
        counts = self.counts()
        opportunities = counts["opportunity_count"]
        materializations = counts["materialization_count"]
        exposures = counts["exposure_count"]
        if self.condition == "CLEAN" and (materializations or exposures):
            return MutationLifecycleStatus.MUTATION_RUNTIME_ERROR
        if exposures > materializations:
            return MutationLifecycleStatus.MUTATION_RUNTIME_ERROR
        if opportunities == 0:
            if materializations or exposures:
                return MutationLifecycleStatus.MUTATION_RUNTIME_ERROR
            return MutationLifecycleStatus.COMPLETED_WITHOUT_OPPORTUNITY
        if materializations == 0:
            return MutationLifecycleStatus.MISSED_MATERIALIZATION
        cardinality = self.spec.materialization_cardinality_given_opportunity
        if (
            cardinality == "EXACTLY_ONE_PER_UNIT_IF_ANY_OPPORTUNITY"
            and materializations != 1
        ):
            return MutationLifecycleStatus.OVER_MATERIALIZATION
        if (
            cardinality == "EXACTLY_ONE_PER_OPPORTUNITY"
            and materializations != opportunities
        ):
            return (
                MutationLifecycleStatus.MISSED_MATERIALIZATION
                if materializations < opportunities
                else MutationLifecycleStatus.OVER_MATERIALIZATION
            )
        if cardinality == "AT_MOST_ONE_PER_UNIT" and materializations > 1:
            return MutationLifecycleStatus.OVER_MATERIALIZATION
        if exposures == 0:
            return MutationLifecycleStatus.COMPLETE_MATERIALIZED_NOT_EXPOSED
        return MutationLifecycleStatus.COMPLETED_WITH_EXPOSURE

    def complete(self) -> dict[str, Any]:
        status = self.classify()
        return self._append(
            LifecycleEventType.LIFECYCLE_COMPLETED,
            "completion",
            {**self.counts(), "final_lifecycle_status": status.value},
        )

    def recovery_disposition(self) -> RecoveryDisposition:
        if any(
            event["event_type"] == LifecycleEventType.LIFECYCLE_COMPLETED.value
            for event in self.events
        ):
            return RecoveryDisposition.NO_OP
        types = [event["event_type"] for event in self.events]
        if LifecycleEventType.EXPOSURE_PERSISTED.value in types:
            return RecoveryDisposition.RESUME_COMPLETION_FROM_PERSISTED_EXPOSURE
        if LifecycleEventType.MATERIALIZATION_PERSISTED.value in types:
            return RecoveryDisposition.RESUME_EXPOSURE_FROM_PERSISTED_MATERIALIZATION
        if LifecycleEventType.OPPORTUNITY_PERSISTED.value in types:
            return (
                RecoveryDisposition.RESUME_MATERIALIZATION_FROM_PERSISTED_OPPORTUNITY
            )
        return RecoveryDisposition.RESUME_OPPORTUNITY_DETECTION


def count_opportunities(
    spec: MutationSpec, event_stream: Iterable[Mapping[str, Any]]
) -> int:
    return sum(event_is_opportunity(spec, event) for event in event_stream)
