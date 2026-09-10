"""Immutable provenance records for ContractIR compilation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProvenanceRecord:
    source_layer: str
    source_schema: str
    source_identifier: str
    source_hash: str
    field_path: str
    authority: str
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperatorApplication:
    operator: str
    field_path: str
    precondition: str
    transformation: str
    postcondition: str
    semantic_fields_preserved: tuple[str, ...]
    inverse_status: str
    idempotence_expectation: str
    downstream_consumer_expectation: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic_fields_preserved"] = list(self.semantic_fields_preserved)
        return value


def append_operator(
    provenance: list[dict[str, Any]], application: OperatorApplication
) -> list[dict[str, Any]]:
    return [*provenance, {"kind": "COMPILER_OPERATOR", **application.to_dict()}]
