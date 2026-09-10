"""Fail-closed helpers for exactly-once inference recovery audits."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable


REQUIRED_PREINFERENCE_FALSE = (
    "model_prefill_started",
    "model_decode_started",
    "model_output_created",
    "env_action_submitted",
    "env_state_mutated",
)


@dataclass(frozen=True)
class RecoveryFacts:
    http_status: int
    rejection_class: str
    http_accepted_by_frontend: bool
    scheduler_enqueued: bool
    model_prefill_started: bool
    model_decode_started: bool
    model_output_created: bool
    env_action_submitted: bool
    env_state_mutated: bool


def classify_preinference_retry(facts: RecoveryFacts) -> dict[str, Any]:
    """Apply the R2C preregistered recovery rule without optimistic inference."""
    failed_conditions = [
        field for field in REQUIRED_PREINFERENCE_FALSE if getattr(facts, field)
    ]
    capacity_rejection = (
        facts.http_status == 400
        and facts.rejection_class == "REQUEST_CONTEXT_CAPACITY_REJECTION"
    )
    retry_safe = capacity_rejection and not failed_conditions
    return {
        "capacity_rejection": capacity_rejection,
        "failed_required_false_conditions": failed_conditions,
        "retry_safe": retry_safe,
        "status": (
            "PREINFERENCE_RETRY_SAFE"
            if retry_safe
            else "PREINFERENCE_SAFETY_NOT_PROVEN"
        ),
    }


def exact_bytes_match(original: bytes, reconstructed: bytes) -> bool:
    return original == reconstructed


def deterministic_checkpoint_match(first_hash: str, second_hash: str) -> bool:
    return len(first_hash) == 64 and first_hash == second_hash


def assert_original_ledger_immutable(before: bytes, after: bytes) -> None:
    if before != after:
        raise ValueError("original recovery ledger changed")


def recovery_authorization(classification: dict[str, Any]) -> str | None:
    if classification.get("status") == "PREINFERENCE_RETRY_SAFE":
        return "RETRY_ORIGINAL_FAILED_REQUEST_41_AFTER_CAPACITY_PREFLIGHT"
    return None


def ceil_capacity_target(
    max_requirement: int, safety_margin: int, page_multiple: int
) -> int:
    if max_requirement < 0 or safety_margin < 1024 or page_multiple <= 0:
        raise ValueError("invalid workload-capacity inputs")
    return math.ceil((max_requirement + safety_margin) / page_multiple) * page_multiple


def capacity_preflight_pass(
    *, actual_capacity: int, target: int, truncated: bool, remote_fallback: bool
) -> bool:
    return (
        actual_capacity >= target
        and not truncated
        and not remote_fallback
    )


def detect_previous_request_reissue(
    completed_request_hashes: Iterable[str], resumed_request_hashes: Iterable[str]
) -> bool:
    return bool(set(completed_request_hashes) & set(resumed_request_hashes))


def exactly_once_resume_allowed(
    *, original_status: str, recovery_status: str, request_ordinal: int
) -> bool:
    return (
        original_status == "PARTIAL_AMBIGUOUS"
        and recovery_status == "PREINFERENCE_RETRY_SAFE"
        and request_ordinal == 41
    )


def validate_separate_model_capacity(plans: dict[str, dict[str, int]]) -> bool:
    return (
        set(plans) == {"qwen", "gemma"}
        and all(plan["actual_capacity"] >= plan["capacity_target"] for plan in plans.values())
    )


def recovery_crash_status(*, request_sent: bool, response_persisted: bool) -> str:
    if request_sent and not response_persisted:
        return "PARTIAL_AMBIGUOUS"
    if not request_sent:
        return "NOT_STARTED"
    return "LIVE_COMPLETE_UNSCORED"
