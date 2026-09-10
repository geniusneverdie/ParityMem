"""Typed, provenance-carrying ContractIR nodes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, ClassVar

from paritymem.contract_ir.schema import CONTRACT_IR_VERSION


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class ContractIRNode:
    semantic_type: str
    canonical_value: Any
    source_layer: str
    source_schema: str
    source_identifier: str
    ordering_semantics: str
    default_semantics: str
    null_semantics: str
    encoding_semantics: str
    identifier_namespace: str
    provenance_chain: tuple[dict[str, Any], ...]
    compiler_operators_applied: tuple[dict[str, Any], ...]
    source_hash: str
    contract_version: str = CONTRACT_IR_VERSION
    NODE_TYPE: ClassVar[str] = "ContractIRNode"

    def __post_init__(self) -> None:
        if self.semantic_type != self.NODE_TYPE:
            raise ValueError(f"{type(self).__name__} requires semantic_type={self.NODE_TYPE}")
        if not self.source_layer or not self.source_schema or not self.source_identifier:
            raise ValueError("ContractIR source metadata is required")
        if not self.provenance_chain:
            raise ValueError("ContractIR provenance_chain cannot be empty")
        if len(self.source_hash) != 64:
            raise ValueError("ContractIR source_hash must be SHA256")

    def semantic_projection(self) -> dict[str, Any]:
        return {"semantic_type": self.semantic_type, "canonical_value": self.canonical_value}

    def semantic_hash(self) -> str:
        return digest(self.semantic_projection())

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["provenance_chain"] = list(self.provenance_chain)
        value["compiler_operators_applied"] = list(self.compiler_operators_applied)
        value["semantic_hash"] = self.semantic_hash()
        value["artifact_hash"] = digest(value)
        return value


@dataclass(frozen=True)
class SessionIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "SessionIR"


@dataclass(frozen=True)
class MessageIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "MessageIR"


@dataclass(frozen=True)
class ToolDefinitionIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ToolDefinitionIR"


@dataclass(frozen=True)
class ToolParameterIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ToolParameterIR"


@dataclass(frozen=True)
class ToolCallIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ToolCallIR"


@dataclass(frozen=True)
class ToolArgumentsIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ToolArgumentsIR"


@dataclass(frozen=True)
class ActionHandleIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ActionHandleIR"


@dataclass(frozen=True)
class ObservationIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ObservationIR"


@dataclass(frozen=True)
class MemoryRecordIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "MemoryRecordIR"


@dataclass(frozen=True)
class StateValueIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "StateValueIR"


@dataclass(frozen=True)
class StateTransitionIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "StateTransitionIR"


@dataclass(frozen=True)
class ScorerBindingIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "ScorerBindingIR"


@dataclass(frozen=True)
class IdentifierBindingIR(ContractIRNode):
    NODE_TYPE: ClassVar[str] = "IdentifierBindingIR"


NODE_TYPES = {
    cls.NODE_TYPE: cls
    for cls in (
        SessionIR,
        MessageIR,
        ToolDefinitionIR,
        ToolParameterIR,
        ToolCallIR,
        ToolArgumentsIR,
        ActionHandleIR,
        ObservationIR,
        MemoryRecordIR,
        StateValueIR,
        StateTransitionIR,
        ScorerBindingIR,
        IdentifierBindingIR,
    )
}


@dataclass(frozen=True)
class InterfaceContractIR:
    contract_version: str
    benchmark: str
    source_layer: str
    session: SessionIR
    messages: tuple[MessageIR, ...] = ()
    tools: tuple[ToolDefinitionIR, ...] = ()
    tool_parameters: tuple[ToolParameterIR, ...] = ()
    tool_calls: tuple[ToolCallIR, ...] = ()
    tool_arguments: tuple[ToolArgumentsIR, ...] = ()
    action_handles: tuple[ActionHandleIR, ...] = ()
    observations: tuple[ObservationIR, ...] = ()
    memory_records: tuple[MemoryRecordIR, ...] = ()
    state_values: tuple[StateValueIR, ...] = ()
    state_transitions: tuple[StateTransitionIR, ...] = ()
    scorer_bindings: tuple[ScorerBindingIR, ...] = ()
    identifier_bindings: tuple[IdentifierBindingIR, ...] = ()
    unsupported_fields: tuple[dict[str, Any], ...] = ()
    ambiguous_fields: tuple[dict[str, Any], ...] = ()
    compiler_operators_applied: tuple[dict[str, Any], ...] = ()
    provenance_chain: tuple[dict[str, Any], ...] = ()

    def all_nodes(self) -> tuple[ContractIRNode, ...]:
        return (
            self.session,
            *self.messages,
            *self.tools,
            *self.tool_parameters,
            *self.tool_calls,
            *self.tool_arguments,
            *self.action_handles,
            *self.observations,
            *self.memory_records,
            *self.state_values,
            *self.state_transitions,
            *self.scorer_bindings,
            *self.identifier_bindings,
        )

    def semantic_projection(self) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for node in self.all_nodes():
            grouped.setdefault(node.semantic_type, []).append(node.semantic_projection())
        return {"contract_version": self.contract_version, "benchmark": self.benchmark, "nodes": grouped}

    def semantic_hash(self) -> str:
        return digest(self.semantic_projection())

    def to_dict(self) -> dict[str, Any]:
        value = {
            "contract_version": self.contract_version,
            "benchmark": self.benchmark,
            "source_layer": self.source_layer,
            "session": self.session.to_dict(),
            "messages": [node.to_dict() for node in self.messages],
            "tools": [node.to_dict() for node in self.tools],
            "tool_parameters": [node.to_dict() for node in self.tool_parameters],
            "tool_calls": [node.to_dict() for node in self.tool_calls],
            "tool_arguments": [node.to_dict() for node in self.tool_arguments],
            "action_handles": [node.to_dict() for node in self.action_handles],
            "observations": [node.to_dict() for node in self.observations],
            "memory_records": [node.to_dict() for node in self.memory_records],
            "state_values": [node.to_dict() for node in self.state_values],
            "state_transitions": [node.to_dict() for node in self.state_transitions],
            "scorer_bindings": [node.to_dict() for node in self.scorer_bindings],
            "identifier_bindings": [node.to_dict() for node in self.identifier_bindings],
            "unsupported_fields": list(self.unsupported_fields),
            "ambiguous_fields": list(self.ambiguous_fields),
            "compiler_operators_applied": list(self.compiler_operators_applied),
            "provenance_chain": list(self.provenance_chain),
            "semantic_hash": self.semantic_hash(),
        }
        value["artifact_hash"] = digest(value)
        value["node_count"] = len(self.all_nodes())
        return value
