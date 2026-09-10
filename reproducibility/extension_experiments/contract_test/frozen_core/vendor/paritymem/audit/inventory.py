"""Read-only upstream and environment inventory helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any

from paritymem.audit.io import sha256_file


def _run(command: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return completed.returncode, completed.stdout.strip()


def _git(repo: Path, *arguments: str) -> str:
    code, output = _run(["git", *arguments], cwd=repo)
    if code:
        raise RuntimeError(f"git {' '.join(arguments)} failed for {repo}: {output}")
    return output


def _clone_time_provenance(repo: Path) -> dict[str, str]:
    """Return a filesystem-backed estimate without changing the Git tree."""

    git_config = repo / ".git" / "config"
    code, birth_time = _run(["stat", "-c", "%w", str(git_config)])
    if code == 0 and birth_time and birth_time != "-":
        return {
            "clone_time": birth_time,
            "clone_time_basis": "filesystem_birth_time_of_git_config",
        }
    modified = datetime.fromtimestamp(git_config.stat().st_mtime, timezone.utc).isoformat()
    return {
        "clone_time": modified,
        "clone_time_basis": "filesystem_mtime_of_git_config_fallback",
    }


def write_tracked_manifest(repo: Path, destination: Path) -> dict[str, Any]:
    tracked = [line for line in _git(repo, "ls-files", "-z").split("\0") if line]
    rows = []
    for relative in sorted(tracked):
        path = repo / relative
        if path.is_file():
            rows.append((sha256_file(path), relative))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(f"{digest}  {relative}\n" for digest, relative in rows), encoding="utf-8")
    return {"tracked_file_count": len(rows), "manifest": destination.as_posix(), "manifest_sha256": sha256_file(destination)}


def repository_inventory(
    *,
    benchmark: str,
    repo: Path,
    expected_commit: str,
    expected_url: str,
    manifest_destination: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    actual_commit = _git(repo, "rev-parse", "HEAD")
    branch = _git(repo, "branch", "--show-current") or "DETACHED"
    status = _git(repo, "status", "--porcelain")
    remote_url = _git(repo, "remote", "get-url", "origin")
    tags = _git(repo, "tag", "--points-at", "HEAD").splitlines()
    licenses = sorted(path.relative_to(repo).as_posix() for path in repo.glob("*LICENSE*") if path.is_file())
    manifest = write_tracked_manifest(repo, manifest_destination)
    return {
        "benchmark": benchmark,
        "repository_url_expected": expected_url,
        "repository_url_actual": remote_url,
        "commit_expected": expected_commit,
        "commit_actual": actual_commit,
        "commit_match": actual_commit == expected_commit,
        "branch": branch,
        "tags_at_commit": tags,
        "git_clean": status == "",
        "git_status_porcelain": status,
        **_clone_time_provenance(repo),
        "first_formal_inventory_utc": datetime.now(timezone.utc).isoformat(),
        "licenses": licenses,
        "license_risk": not bool(licenses),
        "read_only_policy": "upstream is never modified or used as a result directory",
        **manifest,
        **metadata,
    }


def environment_inventory(
    *,
    benchmark: str,
    environment: Path,
    install_scope: str,
    install_attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    python = environment / "bin" / "python"
    code_version, version = _run([str(python), "--version"])
    code_freeze, freeze = _run([str(python), "-m", "pip", "freeze", "--all"])
    code_check, check = _run([str(python), "-m", "pip", "check"])
    return {
        "benchmark": benchmark,
        "environment": environment.as_posix(),
        "exists": environment.exists(),
        "python_version": version,
        "python_version_check_exit": code_version,
        "install_scope": install_scope,
        "install_attempts": install_attempts,
        "pip_freeze": freeze.splitlines(),
        "pip_freeze_exit": code_freeze,
        "pip_check_output": check,
        "pip_check_exit": code_check,
        "pip_check_pass": code_check == 0,
    }
