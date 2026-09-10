"""Small exactly-once ledger for deterministic H0 fixture transactions."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from .io import atomic_write_json


Status = Literal["NOT_STARTED", "RUNNING", "COMPLETE", "FAILED_AMBIGUOUS"]


@dataclass(frozen=True)
class LedgerEntry:
    transaction_id: str
    status: Status
    input_sha256: str
    output_sha256: str | None = None


def commit_ledger(path: str | Path, entries: list[LedgerEntry], *, overwrite: bool = True) -> None:
    identifiers = [entry.transaction_id for entry in entries]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate transaction_id")
    atomic_write_json(
        path,
        {"schema_version": "paritymem.exactly_once.v1", "entries": [asdict(entry) for entry in entries]},
        overwrite=overwrite,
    )

