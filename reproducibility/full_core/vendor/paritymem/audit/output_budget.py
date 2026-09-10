"""Zero-model output-budget contract helpers.

The functions in this module deliberately distinguish configured generation
limits from protocol bounds and actual model usage.  They never estimate model
behavior and never repair a request.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
import math
import random
from typing import Any


CONFIGURED_MAX_OUTPUT = "CONFIGURED_MAX_OUTPUT"
PROTOCOL_COMPLETE_OUTPUT_CAP = "PROTOCOL_COMPLETE_OUTPUT_CAP"
PREDICTED_OUTPUT = "PREDICTED_OUTPUT"
ACTUAL_OUTPUT = "ACTUAL_OUTPUT"
SUM_OF_PER_REQUEST_MAX_OUTPUT_RESERVATIONS = (
    "SUM_OF_PER_REQUEST_MAX_OUTPUT_RESERVATIONS"
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def protocol_safety_margin(protocol_max_tokens: int) -> int:
    """Return the frozen O0 formatting/tokenizer margin."""

    if not isinstance(protocol_max_tokens, int) or protocol_max_tokens < 0:
        raise ValueError("protocol_max_tokens must be a non-negative integer")
    return max(16, math.ceil(protocol_max_tokens * 0.10))


def protocol_safe_cap(protocol_max_tokens: int) -> int:
    return protocol_max_tokens + protocol_safety_margin(protocol_max_tokens)


def reconstruct_configured_reservation(rows: Iterable[Mapping[str, Any]]) -> int:
    """Sum the exact configured per-request limits.

    Absence of the configured field is an error, rather than an unknown or a
    silently invented prediction.
    """

    total = 0
    for row in rows:
        value = row.get("requested_max_output_tokens")
        if not isinstance(value, int) or value < 0:
            raise ValueError("invalid requested_max_output_tokens")
        total += value
    return total


def classify_output_budget_aggregation(
    rows: Iterable[Mapping[str, Any]], aggregate: int
) -> str:
    values = list(rows)
    if reconstruct_configured_reservation(values) != aggregate:
        raise ValueError("aggregate is not the sum of configured reservations")
    return SUM_OF_PER_REQUEST_MAX_OUTPUT_RESERVATIONS


def _field_path(parent: str, name: str) -> str:
    return f"{parent}.{name}" if parent else name


def audit_json_schema_fields(
    schema: Mapping[str, Any],
    *,
    root: str,
) -> list[dict[str, Any]]:
    """Classify bounded and unbounded JSON-schema fields conservatively.

    JSON Schema defaults (such as additionalProperties=true) are respected.
    A task-local database does not turn a schema-unbounded string into an enum.
    """

    records: list[dict[str, Any]] = []

    def visit(current: Mapping[str, Any], path: str, required: bool) -> None:
        field_type = current.get("type")
        enum = current.get("enum")
        record: dict[str, Any] = {
            "path": path,
            "type": field_type,
            "required": required,
            "default_present": "default" in current,
            "default": current.get("default"),
        }
        if enum is not None:
            record.update(
                classification="BOUNDED_BY_OFFICIAL_ENUM",
                bounded=True,
                enum_count=len(enum),
                longest_enum_utf8_bytes=max(
                    (len(str(item).encode("utf-8")) for item in enum), default=0
                ),
            )
        elif field_type == "string":
            maximum = current.get("maxLength")
            record.update(
                classification=(
                    "BOUNDED_BY_OFFICIAL_SCHEMA"
                    if isinstance(maximum, int)
                    else "UNBOUNDED_BY_OFFICIAL_SCHEMA"
                ),
                bounded=isinstance(maximum, int),
                max_length=maximum,
                reason=None if isinstance(maximum, int) else "string has no maxLength",
            )
        elif field_type in {"integer", "number"}:
            bounded = "minimum" in current and "maximum" in current
            record.update(
                classification=(
                    "BOUNDED_BY_OFFICIAL_SCHEMA"
                    if bounded
                    else "UNBOUNDED_BY_OFFICIAL_SCHEMA"
                ),
                bounded=bounded,
                minimum=current.get("minimum"),
                maximum=current.get("maximum"),
                reason=None if bounded else "numeric field lacks a closed range",
            )
        elif field_type == "array":
            maximum = current.get("maxItems")
            record.update(
                classification=(
                    "BOUNDED_BY_OFFICIAL_SCHEMA"
                    if isinstance(maximum, int)
                    else "UNBOUNDED_BY_OFFICIAL_SCHEMA"
                ),
                bounded=isinstance(maximum, int),
                max_items=maximum,
                reason=None if isinstance(maximum, int) else "array has no maxItems",
            )
        elif field_type == "object":
            additional = current.get("additionalProperties", True)
            record.update(
                classification=(
                    "STRUCTURALLY_BOUNDED_OBJECT"
                    if additional is False
                    else "UNBOUNDED_BY_OFFICIAL_SCHEMA"
                ),
                bounded=additional is False,
                additional_properties=additional,
                reason=(
                    None
                    if additional is False
                    else "object permits unspecified additional properties"
                ),
            )
        elif field_type == "boolean":
            record.update(classification="FINITE_SCALAR", bounded=True)
        else:
            record.update(
                classification="UNBOUNDED_BY_OFFICIAL_SCHEMA",
                bounded=False,
                reason="missing or unsupported type constraint",
            )
        records.append(record)

        required_names = set(current.get("required", []))
        for name, child in sorted(current.get("properties", {}).items()):
            visit(child, _field_path(path, name), name in required_names)
        items = current.get("items")
        if isinstance(items, Mapping):
            visit(items, f"{path}[]", True)

    visit(schema, root, True)
    return records


def validate_pm_action(action: Mapping[str, Any], schema: Mapping[str, Any]) -> bool:
    """Validate the frozen heartbeat-disabled PM semantic action language."""

    if set(action) != {"action", "choice", "task_ids", "channel"}:
        return False
    properties = schema["properties"]
    if action["action"] not in properties["action"]["enum"]:
        return False
    if action["choice"] not in properties["choice"]["enum"]:
        return False
    if action["channel"] not in properties["channel"]["enum"]:
        return False
    task_ids = action["task_ids"]
    if not isinstance(task_ids, list):
        return False
    if len(task_ids) > properties["task_ids"]["maxItems"]:
        return False
    allowed_ids = properties["task_ids"]["items"]["enum"]
    if any(item not in allowed_ids for item in task_ids):
        return False
    if action["action"] == "choose":
        return action["choice"] in {"A", "B", "C"} and action["channel"] == "NONE"
    if action["action"] in {"check_time", "query_state"}:
        return action["choice"] == "NONE" and not task_ids
    return False


def pm_boundary_actions(
    schema: Mapping[str, Any],
    *,
    random_cases: int = 64,
) -> list[dict[str, Any]]:
    """Generate exhaustive scalar and deterministic structural boundary cases.

    Scalar enums and every finite identifier are covered exhaustively. Arrays
    use empty, maximum repeated, every ordered-pair alternation, rotations and
    deterministic property cases, as required for a structural combination
    space that is too large to enumerate naively.
    """

    properties = schema["properties"]
    ids = list(properties["task_ids"]["items"]["enum"])
    maximum = int(properties["task_ids"]["maxItems"])
    channels = list(properties["channel"]["enum"])
    arrays: list[list[str]] = [[]]
    if maximum:
        arrays.extend([[identifier] * maximum for identifier in ids])
        for left in ids:
            for right in ids:
                arrays.append([left if index % 2 == 0 else right for index in range(maximum)])
        for offset in range(len(ids)):
            arrays.append([ids[(offset + index) % len(ids)] for index in range(maximum)])
        seed = int(sha256_bytes(canonical_json_bytes(schema))[:16], 16)
        rng = random.Random(seed)
        for _ in range(random_cases):
            length = rng.choice([0, 1, maximum])
            arrays.append([rng.choice(ids) for _ in range(length)])

    unique_arrays: dict[str, list[str]] = {
        json.dumps(value, separators=(",", ":")): value for value in arrays
    }
    actions: list[dict[str, Any]] = []
    for choice in ("A", "B", "C"):
        for task_ids in unique_arrays.values():
            actions.append(
                {
                    "action": "choose",
                    "choice": choice,
                    "task_ids": task_ids,
                    "channel": "NONE",
                }
            )
    for action_name in ("check_time", "query_state"):
        for channel in channels:
            actions.append(
                {
                    "action": action_name,
                    "choice": "NONE",
                    "task_ids": [],
                    "channel": channel,
                }
            )
    return actions


def serialize_pm_action(
    action: Mapping[str, Any],
    *,
    key_order: Sequence[str] = ("action", "choice", "task_ids", "channel"),
    spaced: bool = False,
    newline: bool = False,
) -> str:
    ordered = {name: action[name] for name in key_order}
    separators = (", ", ": ") if spaced else (",", ":")
    text = json.dumps(ordered, ensure_ascii=False, separators=separators)
    return f"\n{text}\n" if newline else text


def summarize_field_audit(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = list(records)
    unbounded = [row for row in values if not row.get("bounded", False)]
    return {
        "total_fields": len(values),
        "bounded_fields": len(values) - len(unbounded),
        "unbounded_fields": len(unbounded),
        "unbounded_by_type": {
            (kind if kind is not None else "unspecified"): sum(
                row.get("type") == kind for row in unbounded
            )
            for kind in ("string", "array", "integer", "number", "object", None)
        },
    }
