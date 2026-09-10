"""Durable benchmark-neutral artifact and manifest utilities.

This module is a clean-room, benchmark-neutral rewrite informed by the legacy
files recorded in docs/LEGACY_ASSET_BOUNDARY.md. It deliberately contains no
ProIntent or PM-Bench runtime semantics.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    digest = hashlib.sha256(value).hexdigest()
    if not SHA256_RE.fullmatch(digest):
        raise AssertionError("hashlib returned a malformed SHA256 digest")
    return digest


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    if not SHA256_RE.fullmatch(value):
        raise AssertionError("hashlib returned a malformed SHA256 digest")
    return value


def atomic_write_bytes(path: str | Path, value: bytes, *, overwrite: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    descriptor, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.tmp.")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: str | Path, value: Any, *, overwrite: bool = False) -> None:
    atomic_write_bytes(path, canonical_json_bytes(value) + b"\n", overwrite=overwrite)


def atomic_write_text(path: str | Path, value: str, *, overwrite: bool = False) -> None:
    atomic_write_bytes(path, value.encode("utf-8"), overwrite=overwrite)


def write_sha256_manifest(
    root: str | Path,
    paths: Iterable[str | Path],
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    base = Path(root).resolve()
    target = Path(destination)
    records: list[tuple[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        relative = path.relative_to(base).as_posix()
        records.append((sha256_file(path), relative))
    records.sort(key=lambda item: item[1])
    text = "".join(f"{digest}  {relative}\n" for digest, relative in records)
    atomic_write_text(target, text, overwrite=overwrite)
    verification = verify_sha256_manifest(base, target)
    return {
        "entry_count": len(records),
        "manifest_sha256": sha256_file(target),
        "verified": verification["passed"],
    }


def verify_sha256_manifest(root: str | Path, manifest: str | Path) -> dict[str, Any]:
    base = Path(root).resolve()
    rows = []
    for line_number, line in enumerate(Path(manifest).read_text(encoding="utf-8").splitlines(), 1):
        digest, separator, relative = line.partition("  ")
        if separator != "  " or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"malformed manifest line {line_number}")
        actual = sha256_file(base / relative)
        rows.append({"path": relative, "expected": digest, "actual": actual, "pass": actual == digest})
    return {"passed": all(row["pass"] for row in rows), "entry_count": len(rows), "rows": rows}

