"""Deterministic 100-safe/100-unsafe metamorphic fixture registry."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from paritymem.contract_ir.nodes import digest


BENCHMARKS = ("pm_bench", "state_bench", "memory_agent_bench")
STATE_DOMAINS = ("customer_support", "shopping_assistant", "travel")


def _base(index: int, benchmark: str) -> dict[str, Any]:
    domain = STATE_DOMAINS[(index // len(BENCHMARKS)) % len(STATE_DOMAINS)] if benchmark == "state_bench" else None
    args: dict[str, Any] = {
        "entity_id": f"entity_{index:03d}",
        "value": index,
        "ordered_items": ["first", "second", "third"],
        "nullable_note": None,
    }
    schema = {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "value": {"type": "integer"},
            "ordered_items": {"type": "array", "items": {"type": "string"}},
            "nullable_note": {"type": ["string", "null"]},
        },
        "required": ["entity_id", "value", "ordered_items", "nullable_note"],
        "additionalProperties": False,
    }
    return {
        "model": "DETERMINISTIC_NO_MODEL",
        "temperature": 0,
        "tool_choice": "auto",
        "messages": [
            {"role": "system", "content": f"{benchmark} authoritative contract"},
            {"role": "user", "content": f"fixture {index} domain={domain}"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": f"call_{index:03d}",
                    "type": "function",
                    "function": {"name": "apply_contract_action", "arguments": json.dumps(args, ensure_ascii=False)},
                }],
            },
            {"role": "tool", "tool_call_id": f"call_{index:03d}", "content": "accepted"},
        ],
        "tools": [{
            "type": "function",
            "function": {
                "name": "apply_contract_action",
                "description": f"deterministic {benchmark} action",
                "parameters": schema,
            },
        }],
        "identifier_bindings": [{
            "local_alias": f"alias_{index:03d}",
            "official_id": f"entity_{index:03d}",
            "server_id": f"entity_{index:03d}",
            "scorer_id": f"entity_{index:03d}",
        }],
        "scorer_bindings": [{
            "scorer_id": f"{benchmark}:score:{index:03d}",
            "item_id": f"entity_{index:03d}",
            "aggregate_contribution": 1,
        }],
        "_fixture_metadata": {
            "benchmark": benchmark,
            "domain": domain,
            "tool_bearing_history": True,
            "dynamic_tool_arguments": True,
            "scorer_id": f"{benchmark}:score:{index:03d}",
            "alias_binding": {"local": f"entity_{index:03d}", "official": f"entity_{index:03d}"},
        },
    }


def _transform_safe(base: dict[str, Any], relation: str) -> dict[str, Any]:
    value = deepcopy(base)
    function = value["messages"][2]["tool_calls"][0]["function"]
    if relation == "MR-S1":
        function["arguments"] = json.loads(function["arguments"])
    elif relation == "MR-S2":
        args = json.loads(function["arguments"])
        function["arguments"] = json.dumps({key: args[key] for key in reversed(list(args))})
    elif relation == "MR-S3":
        value["tools"][0]["function"]["strict"] = False
    elif relation == "MR-S4":
        value["tools"][0] = deepcopy(value["tools"][0]["function"])
    elif relation == "MR-S5":
        function["arguments"] = json.dumps(json.loads(function["arguments"]), indent=2, ensure_ascii=False)
    elif relation == "MR-S6":
        value["tools"][0] = deepcopy(value["tools"][0]["function"])
    elif relation == "MR-S7":
        value["identifier_bindings"][0]["local_alias"] = value["identifier_bindings"][0]["official_id"]
    return value


def _transform_unsafe(base: dict[str, Any], relation: str) -> dict[str, Any]:
    value = deepcopy(base)
    call = value["messages"][2]["tool_calls"][0]
    args = json.loads(call["function"]["arguments"])
    if relation == "MR-U1":
        args.pop("entity_id")
    elif relation == "MR-U2":
        args["value"] += 1
    elif relation == "MR-U3":
        call["function"]["name"] = "different_function"
    elif relation == "MR-U4":
        call["id"] = call["id"] + "_changed"
    elif relation == "MR-U5":
        value["identifier_bindings"][0]["official_id"] = "different_entity"
    elif relation == "MR-U6":
        args["ordered_items"] = list(reversed(args["ordered_items"]))
    elif relation == "MR-U7":
        args.pop("nullable_note")
    elif relation == "MR-U8":
        args["value"] = str(args["value"])
    elif relation == "MR-U9":
        args["extra"] = "not-a-default"
    elif relation == "MR-U10":
        value["scorer_bindings"][0]["scorer_id"] += ":drift"
    if relation not in {"MR-U3", "MR-U4", "MR-U5", "MR-U10"}:
        call["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
    return value


def build_registry() -> dict[str, Any]:
    safe_counts = {"MR-S1": 15, "MR-S2": 15, **{f"MR-S{i}": 14 for i in range(3, 8)}}
    unsafe_counts = {f"MR-U{i}": 10 for i in range(1, 11)}
    fixtures = []
    index = 0
    for relation, count in safe_counts.items():
        for _ in range(count):
            benchmark = BENCHMARKS[index % len(BENCHMARKS)]
            base = _base(index, benchmark)
            transformed = _transform_safe(base, relation)
            fixtures.append({
                "fixture_id": f"SAFE-{index:03d}", "safety": "SAFE", "relation": relation,
                "benchmark": benchmark, "domain": base["_fixture_metadata"]["domain"],
                "base": base, "transformed": transformed,
                "expected": {"P0": "MISMATCH", "P1": "PASS", "P2": "PASS", "P3": "PASS_IF_SUPPORTED"},
            })
            index += 1
    index = 0
    for relation, count in unsafe_counts.items():
        for _ in range(count):
            benchmark = BENCHMARKS[index % len(BENCHMARKS)]
            base = _base(1000 + index, benchmark)
            transformed = _transform_unsafe(base, relation)
            fixtures.append({
                "fixture_id": f"UNSAFE-{index:03d}", "safety": "UNSAFE", "relation": relation,
                "benchmark": benchmark, "domain": base["_fixture_metadata"]["domain"],
                "base": base, "transformed": transformed,
                "expected": {"P0": "MISMATCH", "P1_OR_P2_OR_P3": "FAIL"},
            })
            index += 1
    registry = {
        "schema_version": "paritymem.h2a_ir.metamorphic_registry.v1",
        "freeze_rule": "fixtures and transforms frozen before checker execution",
        "safe_count": 100,
        "unsafe_count": 100,
        "fixtures": fixtures,
    }
    registry["registry_content_sha256"] = digest(registry)
    return registry
