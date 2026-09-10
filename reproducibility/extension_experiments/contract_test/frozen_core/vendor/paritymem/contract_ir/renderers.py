"""Experimental schema-first ContractIR representation renderers."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from paritymem.contract_ir.nodes import InterfaceContractIR


def _messages(ir: InterfaceContractIR, *, argument_mode: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in ir.messages:
        value = deepcopy(node.canonical_value)
        value.pop("ordinal", None)
        calls = value.get("tool_calls") or []
        rendered_calls = []
        for call in calls:
            arguments = deepcopy(call["arguments"])
            if argument_mode == "JSON_STRING":
                arguments = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            rendered_calls.append({
                "id": call["call_id"],
                "type": "function",
                "function": {"name": call["function"], "arguments": arguments},
            })
        if rendered_calls:
            value["tool_calls"] = rendered_calls
        rows.append(value)
    return rows


def _tool_functions(ir: InterfaceContractIR) -> list[dict[str, Any]]:
    result = []
    for node in ir.tools:
        value = deepcopy(node.canonical_value)
        value.pop("ordinal", None)
        result.append(value)
    return result


def openai_representation(ir: InterfaceContractIR) -> dict[str, Any]:
    value = deepcopy(ir.session.canonical_value)
    value["messages"] = _messages(ir, argument_mode="JSON_STRING")
    functions = _tool_functions(ir)
    if functions:
        value["tools"] = [{"type": "function", "function": item} for item in functions]
    if ir.scorer_bindings:
        value["scorer_bindings"] = [deepcopy(node.canonical_value) for node in ir.scorer_bindings]
    explicit_identifiers = [
        deepcopy(node.canonical_value)
        for node in ir.identifier_bindings
        if node.identifier_namespace == "explicit_identifier_binding"
    ]
    if explicit_identifiers:
        value["identifier_bindings"] = explicit_identifiers
    return value


def server_expected_representation(ir: InterfaceContractIR) -> dict[str, Any]:
    value = deepcopy(ir.session.canonical_value)
    value["messages"] = _messages(ir, argument_mode="AST_OBJECT")
    functions = _tool_functions(ir)
    if functions:
        value["tools"] = [{**item, "strict": False} for item in functions]
    if ir.scorer_bindings:
        value["scorer_bindings"] = [deepcopy(node.canonical_value) for node in ir.scorer_bindings]
    explicit_identifiers = [
        deepcopy(node.canonical_value)
        for node in ir.identifier_bindings
        if node.identifier_namespace == "explicit_identifier_binding"
    ]
    if explicit_identifiers:
        value["identifier_bindings"] = explicit_identifiers
    return value


def consumer_representation(ir: InterfaceContractIR) -> dict[str, Any]:
    value = server_expected_representation(ir)
    value["_consumer_calls"] = [
            {
                "call_id": node.canonical_value["call_id"],
                "function": node.canonical_value["function"],
                "kwargs": deepcopy(node.canonical_value["arguments"]),
            }
            for node in ir.tool_arguments
        ]
    value["_consumer_observations"] = [deepcopy(node.canonical_value) for node in ir.observations]
    value["_consumer_identifier_bindings"] = [deepcopy(node.canonical_value) for node in ir.identifier_bindings]
    return value
