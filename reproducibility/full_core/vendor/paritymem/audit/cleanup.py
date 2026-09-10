"""Ownership declarations for any bounded subprocess used by H0."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

from .io import atomic_write_json


@dataclass(frozen=True)
class OwnedProcess:
    transaction_id: str
    pid: int
    process_group_id: int
    start_time_ticks: int
    command: tuple[str, ...]


def write_ownership_registry(path: str | Path, processes: list[OwnedProcess]) -> None:
    atomic_write_json(
        path,
        {
            "schema_version": "paritymem.cleanup_ownership.v1",
            "owned_processes": [asdict(process) for process in processes],
            "foreign_processes_must_not_be_signalled": True,
            "kill_by_name_forbidden": True,
        },
    )

