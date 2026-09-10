"""Pure identity-aware conversation round-trip checks.

Transport IDs are retained as audit provenance, while semantic pairing is
evaluated independently using the frozen runtime's canonical order mapping.
No field is repaired and no ambiguous mapping is accepted.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _call(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        "transport_call_id": row.get("transport_call_id"),
        "execution_call_id": row.get("execution_call_id"),
        "model_visible_call_id": row.get("model_visible_call_id"),
        "canonical_order_index": index,
        "name": row["name"],
        "arguments": row.get("arguments", {}),
        "raw_arguments": row.get("raw_arguments", row.get("arguments", {})),
        "official_normalized_arguments": row.get("official_normalized_arguments", row.get("arguments", {})),
        "validator_provenance": row.get("validator_provenance"),
    }


def evaluate_pairing(
    original_calls: Sequence[Mapping[str, Any]],
    history_calls: Sequence[Mapping[str, Any]],
    history_results: Sequence[Mapping[str, Any]],
    *,
    execution_order: Sequence[int] | None = None,
    scorer_order: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Evaluate pairing without requiring literal transport-ID visibility.

    Every history result carries ``paired_call_index``.  This is not a repair:
    it is the frozen STATE/C4 positional execution relation.  Duplicate or
    missing transport IDs remain explicit diagnostics, and a swapped positional
    result fails pairing even if names/arguments happen to be identical.
    """
    original = [_call(row, i) for i, row in enumerate(original_calls)]
    history = [_call(row, i) for i, row in enumerate(history_calls)]
    n = len(original)
    execution_order = list(range(n)) if execution_order is None else list(execution_order)
    scorer_order = list(range(n)) if scorer_order is None else list(scorer_order)
    result_indices = [row.get("paired_call_index") for row in history_results]
    names = [row["name"] for row in original]
    hnames = [row["name"] for row in history]
    args = [row["arguments"] for row in original]
    hargs = [row["arguments"] for row in history]
    normalized = [row["official_normalized_arguments"] for row in original]
    hnormalized = [row["official_normalized_arguments"] for row in history]
    provenance = [row["validator_provenance"] for row in original]
    hprovenance = [row["validator_provenance"] for row in history]
    transport_ids = [row["transport_call_id"] for row in original]
    history_transport_ids = [row["transport_call_id"] for row in history]
    execution_ids = [row["execution_call_id"] for row in history]
    duplicate_ids = len([x for x in transport_ids if x is not None]) != len(set(x for x in transport_ids if x is not None))
    missing_ids = any(x is None for x in transport_ids)
    checks = {
        "call_sequence_uniquely_recoverable": len(history) == n and result_indices == list(range(n)),
        "tool_result_pairing": result_indices == list(range(n)),
        "function_name_preservation": names == hnames,
        "argument_preservation": args == hargs,
        "execution_order_preservation": execution_order == list(range(n)),
        "official_normalization_preservation": normalized == hnormalized,
        "validator_provenance_preservation": provenance == hprovenance,
        "scorer_order_preservation": scorer_order == list(range(n)),
        "environment_consequence_preservation": all("result" in row for row in history_results),
    }
    literal = transport_ids == history_transport_ids and not duplicate_ids and not missing_ids
    pairing = all(checks.values()) and not duplicate_ids and not missing_ids
    return {
        "checks": checks,
        "strict_transport_id_literal_preservation": literal,
        "transport_ids": transport_ids,
        "history_transport_ids": history_transport_ids,
        "execution_call_ids": execution_ids,
        "transport_id_duplicate": duplicate_ids,
        "transport_id_missing": missing_ids,
        "model_visible_id_erasure": all(row["model_visible_call_id"] is None for row in history),
        "pairing_preserving_closure": pairing,
        "classification": (
            "PAIRING_PRESERVING_CLOSURE_PASS"
            if pairing
            else "MODEL_VISIBLE_ID_ERASURE_UNSAFE"
        ),
    }
