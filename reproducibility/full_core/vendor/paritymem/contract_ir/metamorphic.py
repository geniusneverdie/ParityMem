"""Metamorphic relation definitions and result evaluation."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


SAFE_RELATIONS = {
    "MR-S1": "JSON encoded string to equivalent AST object in a JSON_ENCODED_VALUE field",
    "MR-S2": "JSON object key reorder",
    "MR-S3": "implicit default to explicit identical default under downstream proof",
    "MR-S4": "OpenAI function wrapper to server unwrapped function",
    "MR-S5": "format-only whitespace in JSON encoding",
    "MR-S6": "provider-specific nonsemantic structural wrapper",
    "MR-S7": "equivalent alias representation with unchanged binding",
}

UNSAFE_RELATIONS = {
    "MR-U1": "required key deletion",
    "MR-U2": "semantic value change",
    "MR-U3": "function name change",
    "MR-U4": "tool call identifier change",
    "MR-U5": "alias rebind",
    "MR-U6": "array reorder when order-sensitive",
    "MR-U7": "null to missing when semantically distinct",
    "MR-U8": "integer to string",
    "MR-U9": "non-default extra value",
    "MR-U10": "scorer identifier drift",
}


@dataclass(frozen=True)
class MetamorphicResult:
    fixture_id: str
    relation: str
    safety: str
    representation_parity: bool
    contract_ir_parity: bool | None
    execution_parity: bool | None
    scoring_parity: bool | None
    compile_rejected: bool
    deterministic_conclusion: str
    passed: bool
    provenance_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
