"""Pure, zero-model conversation-history closure checks.

The functions in this module deliberately distinguish a model/runtime's frozen
template domain from the adapter that reconstructs benchmark history.  They do
not repair, split, merge, or otherwise normalize model-generated tool calls.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        decoded = json.loads(value)
    else:
        decoded = deepcopy(value)
    if not isinstance(decoded, dict):
        raise ValueError("tool-call arguments must decode to an object")
    return decoded


def canonical_tool_calls(tool_calls: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Preserve the observable ID/name/arguments/order of OpenAI tool calls."""
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(tool_calls):
        function = raw.get("function", raw)
        call_id = raw.get("id")
        name = function.get("name")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError(f"tool call {index} has no stable ID")
        if not isinstance(name, str) or not name:
            raise ValueError(f"tool call {index} has no function name")
        rows.append(
            {
                "index": index,
                "id": call_id,
                "name": name,
                "arguments": _arguments(function.get("arguments", {})),
            }
        )
    return rows


def direct_history(
    *,
    content: str,
    tool_calls: Sequence[Mapping[str, Any]],
    tool_results: Sequence[Any],
) -> list[dict[str, Any]]:
    """Construct lossless OpenAI history while retaining original call IDs."""
    canonical = canonical_tool_calls(tool_calls)
    if len(canonical) != len(tool_results):
        raise ValueError("tool-call/result cardinality mismatch")
    assistant = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": row["id"],
                "type": "function",
                "function": {
                    "name": row["name"],
                    "arguments": json.dumps(
                        row["arguments"], ensure_ascii=False, separators=(",", ":")
                    ),
                },
            }
            for row in canonical
        ],
    }
    messages: list[dict[str, Any]] = [assistant]
    for row, result in zip(canonical, tool_results, strict=True):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": row["id"],
                "content": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            }
        )
    return messages


def adapter_history(
    *,
    content: str,
    tool_calls: Sequence[Mapping[str, Any]],
    tool_results: Sequence[Any],
) -> list[dict[str, Any]]:
    """Reproduce the frozen C4 LocalStateAgent history adapter exactly.

    The C4 adapter receives STATE's benchmark records (name/arguments/result),
    so it invents call_0... IDs.  Retaining this behavior here is provenance,
    not endorsement and not a proposed repair.
    """
    canonical = canonical_tool_calls(tool_calls)
    if len(canonical) != len(tool_results):
        raise ValueError("tool-call/result cardinality mismatch")
    calls: list[dict[str, Any]] = []
    for index, row in enumerate(canonical):
        calls.append(
            {
                "id": f"call_{index}",
                "type": "function",
                "function": {
                    "name": row["name"],
                    "arguments": json.dumps(row["arguments"], ensure_ascii=False),
                },
            }
        )
    messages: list[dict[str, Any]] = [
        {"role": "assistant", "content": content, "tool_calls": calls}
    ]
    for call, result in zip(calls, tool_results, strict=True):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
    return messages


def history_semantics(messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    assistant = next(
        (row for row in messages if row.get("role") == "assistant"), None
    )
    if assistant is None:
        raise ValueError("assistant message absent")
    calls = canonical_tool_calls(assistant.get("tool_calls") or [])
    tool_messages = [row for row in messages if row.get("role") == "tool"]
    results: list[dict[str, Any]] = []
    for row in tool_messages:
        raw = row.get("content")
        try:
            value = json.loads(raw) if isinstance(raw, str) else deepcopy(raw)
        except json.JSONDecodeError:
            value = raw
        results.append({"tool_call_id": row.get("tool_call_id"), "result": value})
    return {"content": assistant.get("content") or "", "calls": calls, "results": results}


def compare_roundtrip(
    *,
    original_tool_calls: Sequence[Mapping[str, Any]],
    original_results: Sequence[Any],
    reconstructed_messages: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    original = canonical_tool_calls(original_tool_calls)
    reconstructed = history_semantics(reconstructed_messages)
    calls = reconstructed["calls"]
    results = reconstructed["results"]
    ids = [row["id"] for row in original]
    reconstructed_ids = [row["id"] for row in calls]
    names = [row["name"] for row in original]
    reconstructed_names = [row["name"] for row in calls]
    arguments = [row["arguments"] for row in original]
    reconstructed_arguments = [row["arguments"] for row in calls]
    result_ids = [row["tool_call_id"] for row in results]
    result_values = [row["result"] for row in results]
    checks = {
        "tool_id_preservation": ids == reconstructed_ids,
        "function_name_preservation": names == reconstructed_names,
        "argument_preservation": arguments == reconstructed_arguments,
        "ordering_preservation": list(range(len(original)))
        == [row["index"] for row in calls],
        "tool_result_pairing_accuracy": result_ids == ids,
        "tool_result_preservation": list(original_results) == result_values,
        "cardinality_preservation": len(original) == len(calls) == len(results),
    }
    return {
        "original": {"calls": original, "results": list(original_results)},
        "roundtrip": reconstructed,
        "checks": checks,
        "semantic_accuracy": sum(checks.values()) / len(checks),
        "semantic_parity": all(checks.values()),
    }
