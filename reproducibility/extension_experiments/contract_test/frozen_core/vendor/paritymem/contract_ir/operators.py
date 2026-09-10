"""Deterministic, schema-gated ContractIR compiler operators."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from typing import Any, Callable

from paritymem.contract_ir.provenance import OperatorApplication
from paritymem.contract_ir.schema import validate_json_schema


@dataclass(frozen=True)
class OperatorSpec:
    operator: str
    precondition: str
    transformation: str
    postcondition: str
    semantic_fields_preserved: tuple[str, ...]
    provenance_update: str
    inverse_status: str
    idempotence_expectation: str
    downstream_consumer_expectation: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic_fields_preserved"] = list(self.semantic_fields_preserved)
        return value


OPERATOR_REGISTRY: dict[str, OperatorSpec] = {
    "OP1_PROVIDER_WRAPPER_ELISION": OperatorSpec(
        "OP1_PROVIDER_WRAPPER_ELISION",
        "authoritative policy marks {type:function,function:{...}} as a provider wrapper",
        "remove only the provider wrapper and retain the function payload",
        "tool identity/schema equal to wrapped payload",
        ("name", "description", "parameters", "strict"),
        "append wrapper path and source hash",
        "CONDITIONAL",
        "second application is a no-op",
        "tool registry consumes the unwrapped function definition",
    ),
    "OP2_JSON_STRING_TO_AST": OperatorSpec(
        "OP2_JSON_STRING_TO_AST",
        "field policy is JSON_ENCODED_VALUE and strict JSON/schema validation succeeds",
        "parse the field-local UTF-8 JSON string to an AST",
        "AST validates under the same authoritative schema",
        ("keys", "values", "nested_types", "array_order"),
        "append encoded and parsed value hashes",
        "CONDITIONAL",
        "AST input is unchanged on recompilation",
        "official tool adapter consumes kwargs/AST",
    ),
    "OP3_OBJECT_KEY_CANONICALIZATION": OperatorSpec(
        "OP3_OBJECT_KEY_CANONICALIZATION",
        "authoritative policy declares JSON object key order non-semantic",
        "recursively order mapping keys; never reorder arrays",
        "all scalar values and array positions preserved",
        ("keys", "values", "nested_types", "array_order"),
        "append canonicalization path",
        "EXACT",
        "canonical mapping order is stable",
        "JSON-object consumers are key-addressed",
    ),
    "OP4_DEFAULT_MATERIALIZATION": OperatorSpec(
        "OP4_DEFAULT_MATERIALIZATION",
        "downstream schema proves missing equals the explicit default",
        "insert only the declared default",
        "downstream observable value unchanged",
        ("all non-default fields",),
        "append field/default/source proof",
        "EXACT_WITH_OP5",
        "already-present defaults are unchanged",
        "consumer applies the same default",
    ),
    "OP5_DEFAULT_ELISION": OperatorSpec(
        "OP5_DEFAULT_ELISION",
        "field equals a declared default and missing has identical semantics",
        "remove only the explicit default field",
        "consumer-observable value unchanged",
        ("all non-default fields",),
        "append elided field/default/source proof",
        "EXACT_WITH_OP4",
        "missing field remains missing",
        "consumer materializes the declared default",
    ),
    "OP6_ALIAS_NAMESPACE_RESOLUTION": OperatorSpec(
        "OP6_ALIAS_NAMESPACE_RESOLUTION",
        "an exact authoritative alias mapping and namespaces are supplied",
        "emit explicit local/official/server/scorer identifier binding",
        "no fuzzy or partial identifier match occurs",
        ("identifier identity", "namespace"),
        "append both source and target identifiers",
        "CONDITIONAL",
        "resolved binding resolves to itself",
        "downstream consumer uses the official identifier",
    ),
    "OP7_TOOL_ARGUMENT_CANONICALIZATION": OperatorSpec(
        "OP7_TOOL_ARGUMENT_CANONICALIZATION",
        "tool call identity and parameter schema are known",
        "schema-gated JSON decode plus object-key canonicalization",
        "strict keys/values/types/array order/default/null semantics preserved",
        ("function", "keys", "values", "nested_types", "array_order"),
        "append tool/schema/operator subtrace",
        "CONDITIONAL",
        "canonical AST remains unchanged",
        "environment kwargs validation and invocation are identical",
    ),
    "OP8_TOOL_WRAPPER_CANONICALIZATION": OperatorSpec(
        "OP8_TOOL_WRAPPER_CANONICALIZATION",
        "input is an authorized OpenAI/server tool-function structure",
        "compile wrapper variants to ToolDefinitionIR",
        "function name and parameter contract preserved",
        ("name", "description", "parameters", "strict"),
        "append provider format and wrapper trace",
        "CONDITIONAL",
        "IR input is not wrapped again",
        "tool registry sees one equivalent definition",
    ),
    "OP9_ORDER_POLICY_NORMALIZATION": OperatorSpec(
        "OP9_ORDER_POLICY_NORMALIZATION",
        "BIC explicitly declares the selected collection order-insensitive",
        "sort by a total canonical key",
        "multiset preserved",
        ("members", "multiplicity"),
        "append ordering policy citation",
        "EXACT",
        "canonical order is stable",
        "consumer is set/map based",
    ),
    "OP10_STRICT_SCALAR_NORMALIZATION": OperatorSpec(
        "OP10_STRICT_SCALAR_NORMALIZATION",
        "authoritative schema identifies an exact scalar type",
        "validate without coercion; preserve the scalar unchanged",
        "1 != '1', true != 1, and null != missing unless explicitly declared",
        ("value", "runtime type"),
        "append validation result and expected type",
        "EXACT",
        "validated scalar remains unchanged",
        "downstream consumer receives the original scalar type",
    ),
    "OP11_MODEL_OUTPUT_PAYLOAD_PRESERVATION": OperatorSpec(
        "OP11_MODEL_OUTPUT_PAYLOAD_PRESERVATION",
        "the payload is assistant-generated and official parse/validation evidence is journaled separately",
        "decode only the provider JSON envelope and preserve every generated key, value, and runtime type",
        "no benchmark schema coercion or repair is performed",
        ("raw keys", "raw values", "nested types", "array order"),
        "append model-generated ownership and source-response evidence",
        "CONDITIONAL",
        "a parsed AST remains unchanged on recompilation",
        "the official benchmark validator/environment, not ContractIR admission, owns behavioral validity",
    ),
}


def application(name: str, field_path: str) -> OperatorApplication:
    spec = OPERATOR_REGISTRY[name]
    return OperatorApplication(
        operator=spec.operator,
        field_path=field_path,
        precondition=spec.precondition,
        transformation=spec.transformation,
        postcondition=spec.postcondition,
        semantic_fields_preserved=spec.semantic_fields_preserved,
        inverse_status=spec.inverse_status,
        idempotence_expectation=spec.idempotence_expectation,
        downstream_consumer_expectation=spec.downstream_consumer_expectation,
    )


def canonicalize_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize_object(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize_object(item) for item in value]
    return deepcopy(value)


def provider_wrapper_elision(value: dict[str, Any], *, authorized: bool) -> tuple[dict[str, Any], list[OperatorApplication]]:
    is_wrapper = set(value) <= {"type", "function"} and value.get("type") == "function" and isinstance(value.get("function"), dict)
    if not is_wrapper:
        return deepcopy(value), []
    if not authorized:
        raise ValueError("provider wrapper elision is not authorized by the contract")
    return deepcopy(value["function"]), [application("OP1_PROVIDER_WRAPPER_ELISION", "tool")]


def json_string_to_ast(value: Any, *, json_encoded: bool, schema: dict[str, Any] | None, field_path: str) -> tuple[Any, list[OperatorApplication]]:
    if not isinstance(value, str):
        if schema is not None:
            validate_json_schema(value, schema, path=field_path)
        return deepcopy(value), []
    if not json_encoded:
        raise ValueError(f"{field_path}: string parsing is not authorized")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_path}: invalid JSON_ENCODED_VALUE") from exc
    if schema is not None:
        validate_json_schema(parsed, schema, path=field_path)
    return parsed, [application("OP2_JSON_STRING_TO_AST", field_path)]


def canonicalize_tool_arguments(value: Any, *, schema: dict[str, Any], json_encoded: bool, field_path: str) -> tuple[Any, list[OperatorApplication]]:
    parsed, trace = json_string_to_ast(value, json_encoded=json_encoded, schema=schema, field_path=field_path)
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_path}: tool arguments must compile to an object")
    canonical = canonicalize_object(parsed)
    trace.extend(
        [
            application("OP3_OBJECT_KEY_CANONICALIZATION", field_path),
            application("OP7_TOOL_ARGUMENT_CANONICALIZATION", field_path),
        ]
    )
    return canonical, trace


def preserve_model_generated_arguments(
    value: Any, *, json_encoded: bool, field_path: str
) -> tuple[Any, list[OperatorApplication]]:
    """Decode provider JSON without applying benchmark-schema validity as admission."""
    parsed, trace = json_string_to_ast(
        value, json_encoded=json_encoded, schema=None, field_path=field_path
    )
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_path}: official tool parser requires an object")
    canonical = canonicalize_object(parsed)
    trace.extend(
        [
            application("OP3_OBJECT_KEY_CANONICALIZATION", field_path),
            application("OP11_MODEL_OUTPUT_PAYLOAD_PRESERVATION", field_path),
        ]
    )
    return canonical, trace


def elide_defaults(value: dict[str, Any], defaults: dict[str, Any], *, prefix: str) -> tuple[dict[str, Any], list[OperatorApplication]]:
    result = deepcopy(value)
    trace: list[OperatorApplication] = []
    for field_path, default in defaults.items():
        key = field_path.rsplit(".", 1)[-1]
        if key in result and type(result[key]) is type(default) and result[key] == default:
            result.pop(key)
            trace.append(application("OP5_DEFAULT_ELISION", f"{prefix}.{key}"))
    return result, trace


def materialize_default(value: dict[str, Any], key: str, default: Any, *, authorized: bool, field_path: str) -> tuple[dict[str, Any], list[OperatorApplication]]:
    result = deepcopy(value)
    if key in result:
        return result, []
    if not authorized:
        raise ValueError(f"{field_path}: default materialization not authorized")
    result[key] = deepcopy(default)
    return result, [application("OP4_DEFAULT_MATERIALIZATION", field_path)]


def normalize_order(value: list[Any], *, order_insensitive: bool, key: Callable[[Any], Any], field_path: str) -> tuple[list[Any], list[OperatorApplication]]:
    if not order_insensitive:
        return deepcopy(value), []
    return sorted(deepcopy(value), key=key), [application("OP9_ORDER_POLICY_NORMALIZATION", field_path)]


def strict_scalar(value: Any, expected_type: str, *, field_path: str) -> tuple[Any, list[OperatorApplication]]:
    validate_json_schema(value, {"type": expected_type}, path=field_path)
    return deepcopy(value), [application("OP10_STRICT_SCALAR_NORMALIZATION", field_path)]


def resolve_alias_binding(
    local_alias: str,
    official_id: str,
    *,
    exact_mapping: dict[str, str],
    field_path: str,
) -> tuple[dict[str, str], list[OperatorApplication]]:
    """Resolve one alias only through an exact authoritative mapping."""
    if exact_mapping.get(local_alias) != official_id:
        raise ValueError(f"{field_path}: exact authoritative alias mapping absent")
    return (
        {
            "official_id": official_id,
            "server_id": official_id,
            "scorer_id": official_id,
        },
        [application("OP6_ALIAS_NAMESPACE_RESOLUTION", field_path)],
    )
