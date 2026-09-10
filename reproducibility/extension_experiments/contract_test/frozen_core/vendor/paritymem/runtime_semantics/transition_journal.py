"""Append-only, hash-chained environment-transition journal.

The journal separates a persisted model response from the potentially
side-effecting environment consumer.  It proves a unique recovery action and
never authorizes a model retry.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping

from paritymem.audit.io import canonical_json_bytes, sha256_bytes


class JournalInvariantError(RuntimeError):
    pass


class TransitionStatus(str, Enum):
    RAW_RESPONSE_PERSISTED = "RAW_RESPONSE_PERSISTED"
    MODEL_OUTPUT_PARSED = "MODEL_OUTPUT_PARSED"
    OFFICIAL_VALIDATION_RESULT_PERSISTED = "OFFICIAL_VALIDATION_RESULT_PERSISTED"
    TRANSITION_INTENT_PERSISTED = "TRANSITION_INTENT_PERSISTED"
    TRANSITION_RESULT_PERSISTED = "TRANSITION_RESULT_PERSISTED"
    TRANSITION_COMMITTED = "TRANSITION_COMMITTED"
    NEXT_OBSERVATION_MATERIALIZED = "NEXT_OBSERVATION_MATERIALIZED"


class RecoveryDisposition(str, Enum):
    REPARSE_REVALIDATE_NO_MODEL_CALL = "REPARSE_REVALIDATE_NO_MODEL_CALL"
    REPLAY_FROM_VERIFIED_PRE_STATE = "REPLAY_FROM_VERIFIED_PRE_STATE"
    STATE_RECONCILIATION_REQUIRED = "STATE_RECONCILIATION_REQUIRED"
    COMMIT_PERSISTED_RESULT = "COMMIT_PERSISTED_RESULT"
    MATERIALIZE_PERSISTED_OBSERVATION = "MATERIALIZE_PERSISTED_OBSERVATION"
    NO_OP = "NO_OP"


_ORDER = tuple(item.value for item in TransitionStatus)
_REQUIRED_INTENT = {
    "unit_id", "request_id", "response_id", "raw_response_hash",
    "parsed_action_hash", "model_output_ir_hash", "validation_status",
    "intended_tool", "intended_arguments", "pre_state_hash",
    "environment_epoch", "created_at",
}
_REQUIRED_RESULT = {
    "tool_result", "validation_or_error_result", "post_state_hash",
    "next_observation_hash", "terminal", "environment_side_effect_identity",
}


class EnvironmentTransitionJournal:
    """One append-only event stream with a SHA256 chain and strict stages."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def events(self, transition_id: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.path.exists():
            return rows
        previous = "0" * 64
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalInvariantError(f"malformed journal line {number}") from exc
            if row.get("previous_event_hash") != previous:
                raise JournalInvariantError(f"hash-chain predecessor mismatch at line {number}")
            expected = row.get("event_hash")
            unsigned = {key: value for key, value in row.items() if key != "event_hash"}
            actual = sha256_bytes(canonical_json_bytes(unsigned))
            if expected != actual:
                raise JournalInvariantError(f"hash-chain digest mismatch at line {number}")
            previous = actual
            if transition_id is None or row.get("transition_id") == transition_id:
                rows.append(row)
        return rows

    def _append(self, transition_id: str, status: TransitionStatus, payload: Mapping[str, Any]) -> bool:
        if not transition_id:
            raise JournalInvariantError("transition_id must be non-empty")
        with self._lock:
            all_rows = self.events()
            rows = [row for row in all_rows if row["transition_id"] == transition_id]
            if rows:
                last = rows[-1]
                last_index = _ORDER.index(last["status"])
                requested_index = _ORDER.index(status.value)
                if requested_index < last_index:
                    raise JournalInvariantError("transition stage regression")
                if requested_index == last_index:
                    if last["payload"] == dict(payload):
                        return False
                    raise JournalInvariantError("same stage cannot carry different evidence")
                if requested_index != last_index + 1:
                    raise JournalInvariantError("transition stage skipped")
            elif status is not TransitionStatus.RAW_RESPONSE_PERSISTED:
                raise JournalInvariantError("first transition stage must persist raw response")
            previous = all_rows[-1]["event_hash"] if all_rows else "0" * 64
            unsigned = {
                "schema_version": "paritymem.environment_transition_journal.v1",
                "transition_id": transition_id,
                "status": status.value,
                "payload": deepcopy(dict(payload)),
                "previous_event_hash": previous,
            }
            row = {**unsigned, "event_hash": sha256_bytes(canonical_json_bytes(unsigned))}
            data = canonical_json_bytes(row) + b"\n"
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return True

    def persist_raw_response(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        return self._append(transition_id, TransitionStatus.RAW_RESPONSE_PERSISTED, payload)

    def persist_parse(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        return self._append(transition_id, TransitionStatus.MODEL_OUTPUT_PARSED, payload)

    def persist_validation(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        return self._append(transition_id, TransitionStatus.OFFICIAL_VALIDATION_RESULT_PERSISTED, payload)

    def persist_intent(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        missing = sorted(_REQUIRED_INTENT - set(payload))
        if missing:
            raise JournalInvariantError(f"transition intent missing {missing}")
        return self._append(transition_id, TransitionStatus.TRANSITION_INTENT_PERSISTED, payload)

    def persist_result(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        missing = sorted(_REQUIRED_RESULT - set(payload))
        if missing:
            raise JournalInvariantError(f"transition result missing {missing}")
        return self._append(transition_id, TransitionStatus.TRANSITION_RESULT_PERSISTED, payload)

    def commit(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        return self._append(transition_id, TransitionStatus.TRANSITION_COMMITTED, payload)

    def materialize_observation(self, transition_id: str, payload: Mapping[str, Any]) -> bool:
        return self._append(transition_id, TransitionStatus.NEXT_OBSERVATION_MATERIALIZED, payload)

    def recovery_disposition(
        self,
        transition_id: str,
        *,
        deterministic_local_sandbox: bool,
        pre_state_snapshot_available: bool,
        side_effect_identity_reconcilable: bool,
    ) -> RecoveryDisposition:
        rows = self.events(transition_id)
        if not rows:
            return RecoveryDisposition.NO_OP
        status = TransitionStatus(rows[-1]["status"])
        if status in {
            TransitionStatus.RAW_RESPONSE_PERSISTED,
            TransitionStatus.MODEL_OUTPUT_PARSED,
            TransitionStatus.OFFICIAL_VALIDATION_RESULT_PERSISTED,
        }:
            return RecoveryDisposition.REPARSE_REVALIDATE_NO_MODEL_CALL
        if status is TransitionStatus.TRANSITION_INTENT_PERSISTED:
            if deterministic_local_sandbox and pre_state_snapshot_available:
                return RecoveryDisposition.REPLAY_FROM_VERIFIED_PRE_STATE
            if side_effect_identity_reconcilable:
                return RecoveryDisposition.STATE_RECONCILIATION_REQUIRED
            return RecoveryDisposition.STATE_RECONCILIATION_REQUIRED
        if status is TransitionStatus.TRANSITION_RESULT_PERSISTED:
            return RecoveryDisposition.COMMIT_PERSISTED_RESULT
        if status is TransitionStatus.TRANSITION_COMMITTED:
            return RecoveryDisposition.MATERIALIZE_PERSISTED_OBSERVATION
        return RecoveryDisposition.NO_OP
