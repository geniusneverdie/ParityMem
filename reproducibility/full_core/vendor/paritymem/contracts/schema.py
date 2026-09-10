"""Unified Benchmark Interface Contract (BIC) schema.

The schema is intentionally dependency-free so contracts remain inspectable even
when an upstream benchmark environment cannot be installed.  A contract is not
considered complete unless every semantic assertion carries at least one source
citation to frozen upstream code, documentation, or tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


SHA_RE = re.compile(r"^[0-9a-f]{40}$")

CONTRACT_SECTIONS = (
    "session_contract",
    "observation_contract",
    "memory_contract",
    "action_contract",
    "transition_contract",
    "state_contract",
    "scorer_contract",
    "identifier_contract",
    "ordering_contract",
    "side_effect_contract",
)

CAPABILITIES = (
    "HAS_DYNAMIC_ACTION_MENU",
    "HAS_STATIC_TOOL_SCHEMA",
    "HAS_MUTABLE_ENVIRONMENT",
    "HAS_MEMORY_HOOK",
    "HAS_MULTI_SESSION_STATE",
    "HAS_DETERMINISTIC_SCORER",
    "HAS_LLM_JUDGE",
    "HAS_LURE_HANDLES",
    "HAS_FINAL_STATE_SCORER",
)

SUPPORT_KINDS = {"code", "test", "documentation"}
COMPLETENESS = {"COMPLETE", "PARTIAL", "BLOCKED", "NOT_APPLICABLE"}


@dataclass(frozen=True)
class Citation:
    path: str
    symbol: str
    line_start: int
    line_end: int
    commit: str
    support: str

    def validate(self) -> None:
        if not self.path or self.path.startswith("/"):
            raise ValueError("citation path must be non-empty and repository-relative")
        if not self.symbol:
            raise ValueError("citation symbol is required")
        if self.line_start < 1 or self.line_end < self.line_start:
            raise ValueError("invalid citation line range")
        if not SHA_RE.fullmatch(self.commit):
            raise ValueError("citation commit must be a 40-character Git SHA")
        if self.support not in SUPPORT_KINDS:
            raise ValueError(f"unsupported citation kind: {self.support}")


@dataclass(frozen=True)
class ContractAssertion:
    field: str
    semantics: str
    raw_fields: list[str]
    citations: list[Citation]
    confidence: str = "AUTHORITATIVE"
    limitations: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.field or not self.semantics:
            raise ValueError("contract assertion field and semantics are required")
        if not self.citations:
            raise ValueError(f"contract assertion {self.field!r} has no official citation")
        for citation in self.citations:
            citation.validate()
        if self.confidence not in {"AUTHORITATIVE", "DOCUMENTED", "INFERRED", "UNRESOLVED"}:
            raise ValueError(f"invalid confidence: {self.confidence}")


@dataclass
class BenchmarkInterfaceContract:
    benchmark_id: str
    benchmark_version: str
    upstream_commit: str
    repository_url: str
    capability_profile: dict[str, bool]
    completeness: str
    sections: dict[str, list[ContractAssertion]]
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    selected_scope: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.benchmark_id or not self.benchmark_version:
            raise ValueError("benchmark identity is required")
        if not SHA_RE.fullmatch(self.upstream_commit):
            raise ValueError("upstream_commit must be a 40-character Git SHA")
        if self.completeness not in COMPLETENESS:
            raise ValueError(f"invalid completeness: {self.completeness}")
        missing_caps = set(CAPABILITIES) - set(self.capability_profile)
        extra_caps = set(self.capability_profile) - set(CAPABILITIES)
        if missing_caps or extra_caps:
            raise ValueError(f"capability profile mismatch: missing={sorted(missing_caps)}, extra={sorted(extra_caps)}")
        missing_sections = set(CONTRACT_SECTIONS) - set(self.sections)
        extra_sections = set(self.sections) - set(CONTRACT_SECTIONS)
        if missing_sections or extra_sections:
            raise ValueError(f"contract section mismatch: missing={sorted(missing_sections)}, extra={sorted(extra_sections)}")
        for section, assertions in self.sections.items():
            if self.completeness == "COMPLETE" and not assertions:
                raise ValueError(f"complete contract has empty section: {section}")
            for assertion in assertions:
                assertion.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["contract_schema_version"] = "1.0.0"
        return payload


def validate_contract(payload: dict[str, Any]) -> BenchmarkInterfaceContract:
    raw_sections = payload.get("sections", {})
    missing_sections = set(CONTRACT_SECTIONS) - set(raw_sections)
    extra_sections = set(raw_sections) - set(CONTRACT_SECTIONS)
    if missing_sections or extra_sections:
        raise ValueError(f"contract section mismatch: missing={sorted(missing_sections)}, extra={sorted(extra_sections)}")
    sections: dict[str, list[ContractAssertion]] = {}
    for section in CONTRACT_SECTIONS:
        assertions = []
        for raw in payload.get("sections", {}).get(section, []):
            citations = [Citation(**citation) for citation in raw.get("citations", [])]
            assertions.append(
                ContractAssertion(
                    field=raw["field"],
                    semantics=raw["semantics"],
                    raw_fields=list(raw.get("raw_fields", [])),
                    citations=citations,
                    confidence=raw.get("confidence", "AUTHORITATIVE"),
                    limitations=list(raw.get("limitations", [])),
                )
            )
        sections[section] = assertions
    contract = BenchmarkInterfaceContract(
        benchmark_id=payload["benchmark_id"],
        benchmark_version=payload["benchmark_version"],
        upstream_commit=payload["upstream_commit"],
        repository_url=payload["repository_url"],
        capability_profile=dict(payload["capability_profile"]),
        completeness=payload["completeness"],
        sections=sections,
        unresolved=list(payload.get("unresolved", [])),
        selected_scope=dict(payload.get("selected_scope", {})),
    )
    contract.validate()
    return contract
