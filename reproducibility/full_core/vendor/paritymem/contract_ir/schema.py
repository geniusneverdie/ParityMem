"""ContractIR enums, policies, and strict schema validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


CONTRACT_IR_VERSION = "1.0.0"


class SourceLayer(str, Enum):
    OFFICIAL_BIC = "OFFICIAL_BIC"
    OPENAI_WIRE = "OPENAI_WIRE"
    SGLANG_INTERNAL = "SGLANG_INTERNAL"
    ENVIRONMENT_CONSUMER = "ENVIRONMENT_CONSUMER"
    SCORER_INPUT = "SCORER_INPUT"
    CANONICAL_TRACE = "CANONICAL_TRACE"
    COMPILED_REPRESENTATION = "COMPILED_REPRESENTATION"


class OrderingSemantics(str, Enum):
    ORDER_SENSITIVE = "ORDER_SENSITIVE"
    ORDER_INSENSITIVE_OBJECT_KEYS = "ORDER_INSENSITIVE_OBJECT_KEYS"
    ORDER_INSENSITIVE_COLLECTION = "ORDER_INSENSITIVE_COLLECTION"


class DefaultSemantics(str, Enum):
    NO_DEFAULT = "NO_DEFAULT"
    MISSING_DISTINCT_FROM_DEFAULT = "MISSING_DISTINCT_FROM_DEFAULT"
    MISSING_EQUIVALENT_TO_EXPLICIT_DEFAULT = "MISSING_EQUIVALENT_TO_EXPLICIT_DEFAULT"


class NullSemantics(str, Enum):
    NULL_DISTINCT_FROM_MISSING = "NULL_DISTINCT_FROM_MISSING"
    NULL_EQUIVALENT_TO_MISSING = "NULL_EQUIVALENT_TO_MISSING"
    NULL_FORBIDDEN = "NULL_FORBIDDEN"


class EncodingSemantics(str, Enum):
    NATIVE_VALUE = "NATIVE_VALUE"
    JSON_ENCODED_VALUE = "JSON_ENCODED_VALUE"
    UTF8_TEXT = "UTF8_TEXT"
    PROVIDER_WRAPPER = "PROVIDER_WRAPPER"


class InverseStatus(str, Enum):
    EXACT = "EXACT"
    CONDITIONAL = "CONDITIONAL"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class FieldPolicy:
    path: str
    semantic_type: str
    encoding_semantics: EncodingSemantics = EncodingSemantics.NATIVE_VALUE
    ordering_semantics: OrderingSemantics = OrderingSemantics.ORDER_INSENSITIVE_OBJECT_KEYS
    default_semantics: DefaultSemantics = DefaultSemantics.NO_DEFAULT
    null_semantics: NullSemantics = NullSemantics.NULL_DISTINCT_FROM_MISSING
    identifier_namespace: str = "NONE"
    required: bool = False
    json_schema: dict[str, Any] | None = None
    explicit_default: Any = None
    semantic_critical: bool = True

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key, item in list(value.items()):
            if isinstance(item, Enum):
                value[key] = item.value
        return value


@dataclass(frozen=True)
class ContractPolicy:
    benchmark: str
    contract_hash: str
    contract_version: str
    function_wrapper_nonsemantic: bool = True
    object_keys_order_insensitive: bool = True
    tool_arguments_json_encoded: bool = True
    tool_array_order_sensitive: bool = True
    message_order_sensitive: bool = True
    null_missing_equivalent_fields: tuple[str, ...] = (
        "message.name",
        "message.tool_call_id",
        "message.tool_calls",
    )
    explicit_defaults: dict[str, Any] = field(default_factory=lambda: {"tool.strict": False})
    alias_namespaces: tuple[str, ...] = (
        "local_alias",
        "official_id",
        "server_id",
        "scorer_id",
    )


def strict_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_json_schema(value: Any, schema: dict[str, Any], *, path: str = "$") -> None:
    """A strict bounded validator for the JSON-schema subset used by tool APIs."""
    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(strict_type_matches(value, item) for item in expected):
            raise ValueError(f"{path}: strict type mismatch; expected {expected}")
    elif isinstance(expected, str) and not strict_type_matches(value, expected):
        raise ValueError(f"{path}: strict type mismatch; expected {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value outside enum")
    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"{path}: missing required keys {missing}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"{path}: unsupported keys {extra}")
        for key, item in value.items():
            if key in properties:
                validate_json_schema(item, properties[key], path=f"{path}.{key}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            validate_json_schema(item, schema["items"], path=f"{path}[{index}]")
