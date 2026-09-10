"""Bounded subprocess execution for offline official tests and fixtures."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_bounded(
    argv: Sequence[str],
    *,
    cwd: str,
    timeout_seconds: float,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    if not argv:
        raise ValueError("argv must not be empty")
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return CommandResult(tuple(argv), completed.returncode, completed.stdout, completed.stderr)

