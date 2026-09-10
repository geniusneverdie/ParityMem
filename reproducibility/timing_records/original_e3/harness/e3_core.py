"""External timing wrapper around frozen ParityMem call boundaries.

This module contains instrumentation and input plumbing only.  Scientific
logic is imported from the frozen ParityMem package.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import time
from typing import Any

from paritymem.contract_ir.compiler import ContractCompiler
from paritymem.contract_ir.equivalence import compare_contract_ir
from paritymem.contract_ir.renderers import server_expected_representation
from paritymem.contract_ir.schema import ContractPolicy, SourceLayer
from paritymem.h2b_h0.closure import compare_roundtrip
from paritymem.h2b_h1.identity import evaluate_pairing


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def stable(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _decoded(value: Any) -> Any:
    if not isinstance(value, str):
        return deepcopy(value)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _calls_and_results(messages: list[dict]) -> tuple[list[dict], list[Any], list[dict], list[dict], list[dict]]:
    original_calls: list[dict] = []
    original_results: list[Any] = []
    pairing_calls: list[dict] = []
    pairing_results: list[dict] = []
    reconstructed: list[dict] = []
    for message in messages:
        if message.get("role") == "assistant" and message.get("tool_calls"):
            reconstructed.append(deepcopy(message))
            for call in message["tool_calls"]:
                function = call["function"]
                arguments = _decoded(function.get("arguments", {}))
                original_calls.append({"id": call.get("id"), "type": call.get("type", "function"),
                                       "function": {"name": function["name"], "arguments": arguments}})
                pairing_calls.append({
                    "transport_call_id": call.get("id"), "execution_call_id": call.get("id"),
                    "model_visible_call_id": call.get("id"), "name": function["name"],
                    "arguments": arguments, "raw_arguments": function.get("arguments", {}),
                    "official_normalized_arguments": arguments, "validator_provenance": "FROZEN_E1_SOURCE",
                })
        elif message.get("role") == "tool":
            reconstructed.append(deepcopy(message))
            original_results.append(_decoded(message.get("content")))
            pairing_results.append({"paired_call_index": len(pairing_results), "result": message.get("content")})
    return original_calls, original_results, pairing_calls, deepcopy(pairing_calls), pairing_results


def contractir_edge_count(ir) -> int:
    """Count explicit typed relations used for scaling metadata.

    This is a harness complexity descriptor, not a new ContractIR semantic
    definition: ordered-message links, call-to-argument links, identifier
    bindings, observation/result links, state-transition links, and scorer
    bindings.
    """
    return (
        max(len(ir.messages) - 1, 0)
        + len(ir.tool_arguments)
        + len(ir.identifier_bindings)
        + len(ir.observations)
        + len(ir.state_transitions)
        + len(ir.scorer_bindings)
    )


def execute_pipeline(payload_json: str, tokenizer) -> tuple[dict, dict[str, int]]:
    """Execute one complete symbolic decision with non-overlapping timers."""
    timing: dict[str, int] = {}
    total_start = time.perf_counter_ns()

    started = time.perf_counter_ns()
    payload = json.loads(payload_json)
    representation = {
        "model": payload["model"], "messages": payload["messages"], "tools": payload["tools"],
        "temperature": 0, "top_p": 1.0, "max_tokens": 64, "seed": 42,
    }
    timing["T_parse_or_load_ns"] = time.perf_counter_ns() - started

    policy = ContractPolicy(
        benchmark=payload["benchmark"],
        contract_hash=hashlib.sha256((payload["benchmark"] + "|E3_FROZEN").encode()).hexdigest(),
        contract_version="E3_FROZEN_METHOD",
    )
    compiler = ContractCompiler(policy)

    started = time.perf_counter_ns()
    ir = compiler.compile(representation, source_layer=SourceLayer.OPENAI_WIRE)
    timing["T_contractir_ns"] = time.perf_counter_ns() - started

    started = time.perf_counter_ns()
    server_representation = server_expected_representation(ir)
    server_ir = compiler.compile(server_representation, source_layer=SourceLayer.COMPILED_REPRESENTATION)
    parity = compare_contract_ir(
        representation, server_representation, ir, server_ir,
        left_execution="REACHABLE", right_execution="REACHABLE",
    )
    timing["T_p0_p3_ns"] = time.perf_counter_ns() - started

    original_calls, original_results, original_pairing, history_pairing, pairing_results = _calls_and_results(representation["messages"])
    started = time.perf_counter_ns()
    pairing = evaluate_pairing(original_pairing, history_pairing, pairing_results)
    timing["T_pairing_ns"] = time.perf_counter_ns() - started

    started = time.perf_counter_ns()
    closure_error = None
    try:
        reconstructed_messages = [message for message in representation["messages"] if message.get("role") in {"assistant", "tool"}]
        roundtrip = compare_roundtrip(
            original_tool_calls=original_calls,
            original_results=original_results,
            reconstructed_messages=reconstructed_messages,
        )
        kwargs = {"enable_thinking": False} if payload["model_family"] == "Qwen" else {}
        rendered = tokenizer.apply_chat_template(
            representation["messages"], tools=representation["tools"], tokenize=False,
            add_generation_prompt=True, **kwargs,
        )
        content_preserved = all(
            not (message.get("content") or "").strip() or (message.get("content") or "").strip() in rendered
            for message in representation["messages"] if message.get("role") == "assistant" and message.get("tool_calls")
        )
        closure_pass = bool(roundtrip["semantic_parity"] and rendered and content_preserved)
    except Exception as exc:
        roundtrip = None
        rendered = None
        content_preserved = False
        closure_pass = False
        closure_error = {"type": type(exc).__name__, "message": str(exc)}
    timing["T_history_closure_ns"] = time.perf_counter_ns() - started

    started = time.perf_counter_ns()
    if not pairing["pairing_preserving_closure"]:
        verdict, first = "DEFECT", "IDENTITY_PAIRING"
    elif not closure_pass:
        verdict, first = "DEFECT", "HISTORY_CLOSURE"
    elif not parity.contract_ir_parity or parity.execution_parity is False:
        verdict, first = "DEFECT", parity.classification
    elif parity.scoring_parity is False:
        verdict, first = "DEFECT", "P3_SCORER"
    elif ir.ambiguous_fields:
        verdict, first = "UNRESOLVED", "CONTRACT_AMBIGUITY"
    else:
        verdict, first = "SAFE", "NONE"
    timing["T_first_divergence_ns"] = time.perf_counter_ns() - started
    timing["T_total_ns"] = time.perf_counter_ns() - total_start

    result = {
        "verdict": verdict,
        "first_divergence": first,
        "contractir_nodes": len(ir.all_nodes()),
        "contractir_edges": contractir_edge_count(ir),
        "contractir_hash": ir.semantic_hash(),
        "p0_p3_classification": parity.classification,
        "p1_contractir_parity": parity.contract_ir_parity,
        "pairing_classification": pairing["classification"],
        "pairing_pass": pairing["pairing_preserving_closure"],
        "closure_pass": closure_pass,
        "closure_error": closure_error,
        "roundtrip_pass": bool(roundtrip and roundtrip["semantic_parity"]),
        "rendered_prompt_sha256": hashlib.sha256(rendered.encode()).hexdigest() if rendered else None,
        "output_sha256": stable({"verdict": verdict, "first": first, "ir": ir.semantic_hash()}),
    }
    return result, timing

