"""Ownership-aware preservation of model-generated tool payloads.

This boundary never repairs a model output.  A benchmark-specific adapter supplies
what the frozen official consumer actually did; the raw response remains the
primary evidence even when that consumer coerces a value.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
import json
from typing import Any, Mapping

from paritymem.audit.io import canonical_json_bytes, sha256_bytes
from paritymem.contract_ir.schema import validate_json_schema


class ContractOwnership(str, Enum):
    BENCHMARK_NORMATIVE = "BENCHMARK_NORMATIVE"
    RUNTIME_NORMATIVE = "RUNTIME_NORMATIVE"
    MODEL_GENERATED = "MODEL_GENERATED"
    ENVIRONMENT_DERIVED = "ENVIRONMENT_DERIVED"
    SCORER_DERIVED = "SCORER_DERIVED"


class OfficialValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    COERCED = "COERCED"
    REJECTED_CONTINUE = "REJECTED_CONTINUE"
    REJECTED_TERMINAL = "REJECTED_TERMINAL"
    UNRESOLVED = "UNRESOLVED"


class ModelOutputClassification(str, Enum):
    VALID_MODEL_ACTION = "VALID_MODEL_ACTION"
    COERCED_BY_OFFICIAL_VALIDATOR = "COERCED_BY_OFFICIAL_VALIDATOR"
    INVALID_MODEL_ACTION_CONTINUE = "INVALID_MODEL_ACTION_CONTINUE"
    INVALID_MODEL_ACTION_TERMINAL = "INVALID_MODEL_ACTION_TERMINAL"
    OFFICIAL_SEMANTICS_UNRESOLVED = "OFFICIAL_SEMANTICS_UNRESOLVED"


_STATUS_TO_CLASSIFICATION = {
    OfficialValidationStatus.ACCEPTED: ModelOutputClassification.VALID_MODEL_ACTION,
    OfficialValidationStatus.COERCED: ModelOutputClassification.COERCED_BY_OFFICIAL_VALIDATOR,
    OfficialValidationStatus.REJECTED_CONTINUE: ModelOutputClassification.INVALID_MODEL_ACTION_CONTINUE,
    OfficialValidationStatus.REJECTED_TERMINAL: ModelOutputClassification.INVALID_MODEL_ACTION_TERMINAL,
    OfficialValidationStatus.UNRESOLVED: ModelOutputClassification.OFFICIAL_SEMANTICS_UNRESOLVED,
}


def _runtime_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _lookup_path(value: Any, path: str) -> Any:
    current = value
    if path in {"", "$"}:
        return current
    for part in path.removeprefix("$.").split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


@dataclass(frozen=True)
class ModelOutputIR:
    raw_value: Any
    raw_type: str
    declared_schema_type: Any
    validation_status: str
    official_coercion_applied: bool
    official_normalized_value: Any
    validator_provenance: dict[str, Any]
    tool_name: str
    tool_call_id: str
    argument_path: str
    semantic_effect_status: str
    source_response_hash: str
    raw_arguments_text: str
    parsed_arguments: Any
    strict_schema_diagnostic: str
    classification: str
    ownership: str = ContractOwnership.MODEL_GENERATED.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def semantic_hash(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.to_dict()))


def build_model_output_ir(
    *,
    raw_arguments_text: str,
    declared_schema: Mapping[str, Any],
    official_status: OfficialValidationStatus | str,
    official_normalized_value: Any,
    validator_provenance: Mapping[str, Any],
    tool_name: str,
    tool_call_id: str,
    argument_path: str,
    semantic_effect_status: str,
    source_response_hash: str,
) -> ModelOutputIR:
    """Build evidence without mutating or substituting the raw model bytes."""
    status = OfficialValidationStatus(official_status)
    try:
        parsed = json.loads(raw_arguments_text)
        parse_error = None
    except json.JSONDecodeError as exc:
        parsed = None
        parse_error = f"JSONDecodeError:{exc.msg}@{exc.pos}"
    raw_value = _lookup_path(parsed, argument_path) if parse_error is None else None
    schema = dict(declared_schema)
    try:
        if parse_error is not None:
            raise ValueError(parse_error)
        validate_json_schema(parsed, schema, path="$.arguments")
        diagnostic = "STRICT_SCHEMA_PASS"
    except ValueError as exc:
        diagnostic = f"STRICT_SCHEMA_REJECT:{exc}"
    declared_type: Any = schema.get("type")
    if argument_path not in {"", "$"}:
        cursor: Any = schema
        for part in argument_path.removeprefix("$.").split("."):
            cursor = (cursor.get("properties") or {}).get(part, {}) if isinstance(cursor, dict) else {}
        declared_type = cursor.get("type") if isinstance(cursor, dict) else None
    return ModelOutputIR(
        raw_value=deepcopy(raw_value),
        raw_type=_runtime_type(raw_value),
        declared_schema_type=deepcopy(declared_type),
        validation_status=status.value,
        official_coercion_applied=status is OfficialValidationStatus.COERCED,
        official_normalized_value=deepcopy(official_normalized_value),
        validator_provenance=deepcopy(dict(validator_provenance)),
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        argument_path=argument_path,
        semantic_effect_status=semantic_effect_status,
        source_response_hash=source_response_hash,
        raw_arguments_text=raw_arguments_text,
        parsed_arguments=deepcopy(parsed),
        strict_schema_diagnostic=diagnostic,
        classification=_STATUS_TO_CLASSIFICATION[status].value,
    )


def materialize_dynamic_history(
    model_output: ModelOutputIR,
    *,
    assistant_content: str | None,
    official_tool_result: Any,
) -> list[dict[str, Any]]:
    """Represent raw assistant output plus official result without schema repair."""
    return [
        {
            "role": "assistant",
            "content": assistant_content or "",
            "tool_calls": [
                {
                    "id": model_output.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": model_output.tool_name,
                        "arguments": model_output.raw_arguments_text,
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": model_output.tool_call_id,
            "content": json.dumps(official_tool_result, ensure_ascii=False, sort_keys=True),
        },
    ]
