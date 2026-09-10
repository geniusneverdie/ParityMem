"""P0-P3 ContractIR parity and mismatch classification."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from paritymem.contract_ir.nodes import InterfaceContractIR, digest


class MismatchClass(str, Enum):
    REPRESENTATION_ONLY_DRIFT = "REPRESENTATION_ONLY_DRIFT"
    SEMANTIC_IR_MISMATCH = "SEMANTIC_IR_MISMATCH"
    EXECUTION_EFFECT_MISMATCH = "EXECUTION_EFFECT_MISMATCH"
    SCORING_EFFECT_MISMATCH = "SCORING_EFFECT_MISMATCH"
    AMBIGUOUS_CONTRACT = "AMBIGUOUS_CONTRACT"
    FULL_PARITY = "FULL_PARITY"


@dataclass(frozen=True)
class LayerParity:
    representation_parity: bool
    contract_ir_parity: bool
    execution_parity: bool | None
    scoring_parity: bool | None
    classification: str
    left_representation_hash: str
    right_representation_hash: str
    left_ir_hash: str
    right_ir_hash: str
    semantic_differences: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic_differences"] = list(self.semantic_differences)
        return value


def _diff(left: Any, right: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(left) is not type(right):
        return [{"path": path, "left": left, "right": right, "kind": "TYPE"}]
    if isinstance(left, dict):
        rows: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                rows.append({"path": f"{path}.{key}", "left": left.get(key, "<MISSING>"), "right": right.get(key, "<MISSING>"), "kind": "MISSING"})
            else:
                rows.extend(_diff(left[key], right[key], f"{path}.{key}"))
        return rows
    if isinstance(left, list):
        if len(left) != len(right):
            return [{"path": path, "left": len(left), "right": len(right), "kind": "LENGTH"}]
        rows = []
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            rows.extend(_diff(a, b, f"{path}[{index}]"))
        return rows
    if left != right:
        return [{"path": path, "left": left, "right": right, "kind": "VALUE"}]
    return []


def compare_contract_ir(
    left_representation: Mapping[str, Any],
    right_representation: Mapping[str, Any],
    left_ir: InterfaceContractIR,
    right_ir: InterfaceContractIR,
    *,
    left_execution: Any | None = None,
    right_execution: Any | None = None,
    left_score: Any | None = None,
    right_score: Any | None = None,
) -> LayerParity:
    p0 = type(left_representation) is type(right_representation) and deepcopy(dict(left_representation)) == deepcopy(dict(right_representation))
    left_projection = left_ir.semantic_projection()
    right_projection = right_ir.semantic_projection()
    p1 = left_projection == right_projection
    p2 = None if left_execution is None or right_execution is None else type(left_execution) is type(right_execution) and left_execution == right_execution
    p3 = None if left_score is None or right_score is None else type(left_score) is type(right_score) and left_score == right_score
    ambiguous = bool(left_ir.ambiguous_fields or right_ir.ambiguous_fields)
    if ambiguous:
        classification = MismatchClass.AMBIGUOUS_CONTRACT.value
    elif not p1:
        classification = MismatchClass.SEMANTIC_IR_MISMATCH.value
    elif p2 is False:
        classification = MismatchClass.EXECUTION_EFFECT_MISMATCH.value
    elif p3 is False:
        classification = MismatchClass.SCORING_EFFECT_MISMATCH.value
    elif not p0:
        classification = MismatchClass.REPRESENTATION_ONLY_DRIFT.value
    else:
        classification = MismatchClass.FULL_PARITY.value
    return LayerParity(
        representation_parity=p0,
        contract_ir_parity=p1,
        execution_parity=p2,
        scoring_parity=p3,
        classification=classification,
        left_representation_hash=digest(left_representation),
        right_representation_hash=digest(right_representation),
        left_ir_hash=left_ir.semantic_hash(),
        right_ir_hash=right_ir.semantic_hash(),
        semantic_differences=tuple(_diff(left_projection, right_projection)),
    )
