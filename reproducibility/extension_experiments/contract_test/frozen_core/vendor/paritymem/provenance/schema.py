"""Benchmark-neutral source and transformation provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


Authority = Literal["authoritative", "derived", "documentation", "test"]


@dataclass(frozen=True)
class SourceCitation:
    repository: str
    commit: str
    path: str
    symbol: str
    line_start: int
    line_end: int
    authority: Authority

    def __post_init__(self) -> None:
        if self.line_start < 1 or self.line_end < self.line_start:
            raise ValueError("invalid source line interval")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProvenanceRecord:
    record_id: str
    source: SourceCitation
    raw_payload_sha256: str
    canonical_payload_sha256: str
    transformation: str
    parent_record_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

