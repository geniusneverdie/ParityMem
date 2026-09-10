"""Schema-gated compiler from benchmark/provider/runtime representations to ContractIR."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from paritymem.contract_ir.nodes import (
    ActionHandleIR,
    IdentifierBindingIR,
    InterfaceContractIR,
    MemoryRecordIR,
    MessageIR,
    ObservationIR,
    ScorerBindingIR,
    SessionIR,
    StateTransitionIR,
    StateValueIR,
    ToolArgumentsIR,
    ToolCallIR,
    ToolDefinitionIR,
    ToolParameterIR,
    digest,
)
from paritymem.contract_ir.operators import (
    application,
    canonicalize_object,
    canonicalize_tool_arguments,
    elide_defaults,
    normalize_order,
    preserve_model_generated_arguments,
    provider_wrapper_elision,
    strict_scalar,
)
from paritymem.contract_ir.provenance import ProvenanceRecord
from paritymem.contract_ir.schema import (
    CONTRACT_IR_VERSION,
    ContractPolicy,
    DefaultSemantics,
    EncodingSemantics,
    NullSemantics,
    OrderingSemantics,
    SourceLayer,
)


class ContractCompileError(ValueError):
    """The source representation cannot be compiled without semantic widening."""


NODE_CLASSES = {
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


MESSAGE_FIELDS = {"role", "content", "name", "tool_call_id", "tool_calls"}
NONCRITICAL_MESSAGE_FIELDS = {
    "reasoning_content",
    "reasoning_details",
    "audio",
    "annotations",
    "tools",
}
TOOL_CALL_FIELDS = {"id", "type", "function", "index"}
FUNCTION_CALL_FIELDS = {"name", "arguments"}
TOOL_FUNCTION_FIELDS = {"name", "description", "parameters", "strict"}
SESSION_FIELDS = (
    "model",
    "temperature",
    "top_p",
    "max_tokens",
    "max_completion_tokens",
    "tool_choice",
    "parallel_tool_calls",
    "reasoning_effort",
    "chat_template_kwargs",
    "continue_final_message",
    "stop",
    "seed",
)


@dataclass(frozen=True)
class CompileStats:
    total_fields: int
    compiled_fields: int
    exact_representation_fields: int
    normalized_representation_fields: int
    unsupported_fields: int
    ambiguous_fields: int
    semantic_critical_fields: int
    semantic_critical_compiled_fields: int

    def to_dict(self) -> dict[str, int | float]:
        return {
            **self.__dict__,
            "semantic_critical_coverage": (
                self.semantic_critical_compiled_fields / self.semantic_critical_fields
                if self.semantic_critical_fields
                else 1.0
            ),
        }


def _field_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value) + sum(_field_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_field_count(item) for item in value)
    return 0


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


class ContractCompiler:
    """Compile only transformations authorized by an official BIC policy."""

    def __init__(
        self,
        policy: ContractPolicy,
        *,
        preserve_model_generated_schema_events: bool = False,
    ) -> None:
        self.policy = policy
        self.preserve_model_generated_schema_events = bool(
            preserve_model_generated_schema_events
        )

    def _node(
        self,
        semantic_type: str,
        canonical_value: Any,
        *,
        source_layer: str,
        source_identifier: str,
        source_value: Any,
        operators: Iterable[Any] = (),
        ordering: OrderingSemantics = OrderingSemantics.ORDER_INSENSITIVE_OBJECT_KEYS,
        default: DefaultSemantics = DefaultSemantics.NO_DEFAULT,
        null: NullSemantics = NullSemantics.NULL_DISTINCT_FROM_MISSING,
        encoding: EncodingSemantics = EncodingSemantics.NATIVE_VALUE,
        namespace: str = "NONE",
    ) -> Any:
        operator_dicts = tuple(
            item.to_dict() if hasattr(item, "to_dict") else deepcopy(item)
            for item in operators
        )
        source_hash = digest(source_value)
        provenance = ProvenanceRecord(
            source_layer=source_layer,
            source_schema=f"BIC:{self.policy.benchmark}@{self.policy.contract_hash}",
            source_identifier=source_identifier,
            source_hash=source_hash,
            field_path=source_identifier,
            authority="AUTHORITATIVE_BIC",
            note="schema-gated deterministic compilation",
        ).to_dict()
        cls = NODE_CLASSES[semantic_type]
        return cls(
            semantic_type=semantic_type,
            canonical_value=canonicalize_object(canonical_value),
            source_layer=source_layer,
            source_schema=f"BIC:{self.policy.benchmark}@{self.policy.contract_hash}",
            source_identifier=source_identifier,
            ordering_semantics=_enum_value(ordering),
            default_semantics=_enum_value(default),
            null_semantics=_enum_value(null),
            encoding_semantics=_enum_value(encoding),
            identifier_namespace=namespace,
            provenance_chain=(provenance,),
            compiler_operators_applied=operator_dicts,
            source_hash=source_hash,
        )

    def compile(self, representation: Mapping[str, Any] | InterfaceContractIR, *, source_layer: SourceLayer | str) -> InterfaceContractIR:
        if isinstance(representation, InterfaceContractIR):
            return representation
        if not isinstance(representation, Mapping):
            raise ContractCompileError("InterfaceContractIR source must be an object")
        layer = _enum_value(source_layer)
        payload = deepcopy(dict(representation))
        if not isinstance(payload.get("messages", []), list):
            raise ContractCompileError("messages must be an ordered array")
        if not isinstance(payload.get("tools", []), list):
            raise ContractCompileError("tools must be an ordered array")

        unsupported: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        exact_fields = 0
        normalized_fields = 0
        critical_fields = 0
        critical_compiled = 0

        def compiled(*, exact: int = 0, normalized: int = 0, critical: int = 1) -> None:
            nonlocal exact_fields, normalized_fields, critical_fields, critical_compiled
            exact_fields += exact
            normalized_fields += normalized
            critical_fields += critical
            critical_compiled += critical

        raw_tools = payload.get("tools") or []
        selected_name: str | None = None
        tool_choice = payload.get("tool_choice", "auto" if raw_tools else "none")
        if isinstance(tool_choice, dict):
            selected_name = (tool_choice.get("function") or {}).get("name")
            if not isinstance(selected_name, str):
                raise ContractCompileError("tool_choice function name must be an exact string")
        elif tool_choice not in {"auto", "none", "required", None}:
            raise ContractCompileError("unsupported tool_choice")

        session_value: dict[str, Any] = {}
        for key in SESSION_FIELDS:
            if key in payload:
                session_value[key] = deepcopy(payload[key])
                compiled(exact=1)
        session_value["tool_choice"] = deepcopy(tool_choice)
        session = self._node(
            "SessionIR",
            session_value,
            source_layer=layer,
            source_identifier="session",
            source_value={key: payload.get(key) for key in SESSION_FIELDS if key in payload},
            ordering=OrderingSemantics.ORDER_SENSITIVE,
        )

        tool_nodes: list[ToolDefinitionIR] = []
        parameter_nodes: list[ToolParameterIR] = []
        handle_nodes: list[ActionHandleIR] = []
        identifier_nodes: list[IdentifierBindingIR] = []
        schemas: dict[str, dict[str, Any]] = {}
        for index, raw_tool in enumerate(raw_tools):
            if not isinstance(raw_tool, dict):
                raise ContractCompileError(f"tools[{index}] must be an object")
            try:
                function, wrapper_trace = provider_wrapper_elision(
                    raw_tool, authorized=self.policy.function_wrapper_nonsemantic
                )
            except ValueError as exc:
                raise ContractCompileError(str(exc)) from exc
            if set(function) - TOOL_FUNCTION_FIELDS:
                for key in sorted(set(function) - TOOL_FUNCTION_FIELDS):
                    unsupported.append({
                        "path": f"tools[{index}].{key}",
                        "semantic_critical": False,
                        "reason": "unrecognized tool-definition telemetry",
                    })
            name = function.get("name")
            if not isinstance(name, str) or not name:
                raise ContractCompileError(f"tools[{index}].name must be an exact string")
            if selected_name is not None and name != selected_name:
                continue
            parameters = function.get("parameters", {"type": "object", "properties": {}})
            if not isinstance(parameters, dict) or parameters.get("type") != "object":
                raise ContractCompileError(f"tools[{index}].parameters must be an object schema")
            function, default_trace = elide_defaults(
                function, self.policy.explicit_defaults, prefix=f"tools[{index}]"
            )
            operator_trace = [
                *wrapper_trace,
                *default_trace,
                application("OP3_OBJECT_KEY_CANONICALIZATION", f"tools[{index}]"),
                application("OP8_TOOL_WRAPPER_CANONICALIZATION", f"tools[{index}]"),
            ]
            trace.extend(item.to_dict() for item in operator_trace)
            normalized = bool(wrapper_trace or default_trace)
            compiled(exact=0 if normalized else _field_count(function), normalized=_field_count(function) if normalized else 0, critical=4)
            schemas[name] = deepcopy(parameters)
            tool_value = {
                "ordinal": len(tool_nodes),
                "name": name,
                "description": function.get("description", ""),
                "parameters": canonicalize_object(parameters),
            }
            tool_nodes.append(
                self._node(
                    "ToolDefinitionIR",
                    tool_value,
                    source_layer=layer,
                    source_identifier=f"tools[{index}]",
                    source_value=raw_tool,
                    operators=operator_trace,
                    ordering=OrderingSemantics.ORDER_SENSITIVE,
                    default=DefaultSemantics.MISSING_EQUIVALENT_TO_EXPLICIT_DEFAULT,
                    encoding=EncodingSemantics.PROVIDER_WRAPPER if wrapper_trace else EncodingSemantics.NATIVE_VALUE,
                    namespace="official_tool_name",
                )
            )
            for path, value in self._parameter_entries(parameters):
                parameter_nodes.append(
                    self._node(
                        "ToolParameterIR",
                        {"tool": name, "path": path, "schema": value},
                        source_layer=layer,
                        source_identifier=f"tools[{index}].parameters{path}",
                        source_value=value,
                        operators=(application("OP3_OBJECT_KEY_CANONICALIZATION", f"tools[{index}].parameters{path}"),),
                    )
                )
            handle_nodes.append(
                self._node(
                    "ActionHandleIR",
                    {"ordinal": len(handle_nodes), "handle": name, "official_id": name},
                    source_layer=layer,
                    source_identifier=f"tools[{index}].name",
                    source_value=name,
                    operators=(application("OP10_STRICT_SCALAR_NORMALIZATION", f"tools[{index}].name"),),
                    ordering=OrderingSemantics.ORDER_SENSITIVE,
                    namespace="official_tool_name",
                )
            )
            alias_op = application("OP6_ALIAS_NAMESPACE_RESOLUTION", f"tools[{index}].name")
            identifier_nodes.append(
                self._node(
                    "IdentifierBindingIR",
                    {
                        "local_alias": name,
                        "official_id": name,
                        "server_id": name,
                        "scorer_id": name,
                    },
                    source_layer=layer,
                    source_identifier=f"tools[{index}].name",
                    source_value=name,
                    operators=(alias_op,),
                    namespace="tool_identifier_binding",
                )
            )
            trace.append(alias_op.to_dict())

        message_nodes: list[MessageIR] = []
        observation_nodes: list[ObservationIR] = []
        call_nodes: list[ToolCallIR] = []
        argument_nodes: list[ToolArgumentsIR] = []
        for index, raw_message in enumerate(payload.get("messages") or []):
            if not isinstance(raw_message, dict):
                raise ContractCompileError(f"messages[{index}] must be an object")
            role = raw_message.get("role")
            if role not in {"system", "user", "assistant", "tool", "developer"}:
                raise ContractCompileError(f"messages[{index}].role is invalid")
            strict_scalar(role, "string", field_path=f"messages[{index}].role")
            for key in sorted(set(raw_message) - MESSAGE_FIELDS):
                unsupported.append({
                    "path": f"messages[{index}].{key}",
                    "semantic_critical": key not in NONCRITICAL_MESSAGE_FIELDS,
                    "reason": "explicitly unsupported message field",
                })
                if key not in NONCRITICAL_MESSAGE_FIELDS:
                    ambiguous.append({"path": f"messages[{index}].{key}", "reason": "BIC has no semantics"})
            content = raw_message.get("content")
            if content is None and f"message.content" not in self.policy.null_missing_equivalent_fields:
                content = ""
            if not isinstance(content, (str, list)):
                raise ContractCompileError(f"messages[{index}].content has unsupported type")
            canonical_calls: list[dict[str, Any]] = []
            raw_calls = raw_message.get("tool_calls") or []
            if not isinstance(raw_calls, list):
                raise ContractCompileError(f"messages[{index}].tool_calls must be an array")
            for call_index, raw_call in enumerate(raw_calls):
                if not isinstance(raw_call, dict):
                    raise ContractCompileError("tool call must be an object")
                for key in sorted(set(raw_call) - TOOL_CALL_FIELDS):
                    unsupported.append({"path": f"messages[{index}].tool_calls[{call_index}].{key}", "semantic_critical": False, "reason": "provider telemetry"})
                function = raw_call.get("function") or {}
                if not isinstance(function, dict):
                    raise ContractCompileError("tool call function must be an object")
                if set(function) - FUNCTION_CALL_FIELDS:
                    for key in sorted(set(function) - FUNCTION_CALL_FIELDS):
                        unsupported.append({"path": f"messages[{index}].tool_calls[{call_index}].function.{key}", "semantic_critical": False, "reason": "provider telemetry"})
                name = function.get("name")
                call_id = raw_call.get("id")
                if not isinstance(name, str) or not isinstance(call_id, str):
                    raise ContractCompileError("tool call name/id must be exact strings")
                model_generated = (
                    role == "assistant" and self.preserve_model_generated_schema_events
                )
                if name not in schemas and not model_generated:
                    raise ContractCompileError(f"tool call references unknown function {name!r}")
                field_path = (
                    f"messages[{index}].tool_calls[{call_index}].function.arguments"
                )
                try:
                    if model_generated:
                        arguments, argument_trace = preserve_model_generated_arguments(
                            function.get("arguments", {}),
                            json_encoded=self.policy.tool_arguments_json_encoded,
                            field_path=field_path,
                        )
                    else:
                        arguments, argument_trace = canonicalize_tool_arguments(
                            function.get("arguments", {}),
                            schema=schemas[name],
                            json_encoded=self.policy.tool_arguments_json_encoded,
                            field_path=field_path,
                        )
                except ValueError as exc:
                    raise ContractCompileError(str(exc)) from exc
                call_value = {
                    "ordinal": call_index,
                    "call_id": call_id,
                    "function": name,
                    "arguments": arguments,
                }
                canonical_calls.append(call_value)
                call_op = application("OP8_TOOL_WRAPPER_CANONICALIZATION", f"messages[{index}].tool_calls[{call_index}]")
                all_call_trace = [*argument_trace, call_op]
                trace.extend(item.to_dict() for item in all_call_trace)
                compiled(normalized=len(argument_trace), critical=4)
                call_nodes.append(
                    self._node(
                        "ToolCallIR",
                        call_value,
                        source_layer=layer,
                        source_identifier=f"messages[{index}].tool_calls[{call_index}]",
                        source_value=raw_call,
                        operators=all_call_trace,
                        ordering=OrderingSemantics.ORDER_SENSITIVE,
                        namespace="tool_call_id",
                    )
                )
                argument_nodes.append(
                    self._node(
                        "ToolArgumentsIR",
                        {"call_id": call_id, "function": name, "arguments": arguments},
                        source_layer=layer,
                        source_identifier=f"messages[{index}].tool_calls[{call_index}].function.arguments",
                        source_value=function.get("arguments", {}),
                        operators=argument_trace,
                        encoding=EncodingSemantics.JSON_ENCODED_VALUE if isinstance(function.get("arguments"), str) else EncodingSemantics.NATIVE_VALUE,
                        namespace="tool_call_id",
                    )
                )
                identifier_nodes.append(
                    self._node(
                        "IdentifierBindingIR",
                        {"local_alias": call_id, "official_id": call_id, "server_id": call_id, "scorer_id": call_id},
                        source_layer=layer,
                        source_identifier=f"messages[{index}].tool_calls[{call_index}].id",
                        source_value=call_id,
                        operators=(application("OP6_ALIAS_NAMESPACE_RESOLUTION", f"messages[{index}].tool_calls[{call_index}].id"),),
                        namespace="tool_call_id",
                    )
                )
            message_value = {
                "ordinal": index,
                "role": role,
                "content": deepcopy(content),
                "name": raw_message.get("name"),
                "tool_call_id": raw_message.get("tool_call_id"),
                "tool_calls": canonical_calls,
            }
            message_value = {key: value for key, value in message_value.items() if value is not None and value != []}
            message_nodes.append(
                self._node(
                    "MessageIR",
                    message_value,
                    source_layer=layer,
                    source_identifier=f"messages[{index}]",
                    source_value=raw_message,
                    operators=(application("OP3_OBJECT_KEY_CANONICALIZATION", f"messages[{index}]"),),
                    ordering=OrderingSemantics.ORDER_SENSITIVE,
                    null=NullSemantics.NULL_EQUIVALENT_TO_MISSING,
                    encoding=EncodingSemantics.UTF8_TEXT,
                )
            )
            compiled(exact=max(2, len(raw_message)), critical=2)
            if role in {"system", "user", "tool"}:
                observation_nodes.append(
                    self._node(
                        "ObservationIR",
                        {"ordinal": index, "role": role, "content": deepcopy(content)},
                        source_layer=layer,
                        source_identifier=f"messages[{index}].content",
                        source_value=raw_message.get("content"),
                        ordering=OrderingSemantics.ORDER_SENSITIVE,
                        encoding=EncodingSemantics.UTF8_TEXT,
                    )
                )

        for index, binding in enumerate(payload.get("identifier_bindings") or []):
            if not isinstance(binding, dict):
                raise ContractCompileError("identifier binding must be an object")
            official_id = binding.get("official_id")
            if not isinstance(official_id, str):
                raise ContractCompileError("identifier binding requires an exact official_id")
            resolved = {
                "official_id": official_id,
                "server_id": binding.get("server_id", official_id),
                "scorer_id": binding.get("scorer_id", official_id),
            }
            op = application("OP6_ALIAS_NAMESPACE_RESOLUTION", f"identifier_bindings[{index}]")
            identifier_nodes.append(
                self._node(
                    "IdentifierBindingIR",
                    resolved,
                    source_layer=layer,
                    source_identifier=f"identifier_bindings[{index}]",
                    source_value=binding,
                    operators=(op,),
                    namespace="explicit_identifier_binding",
                )
            )
            trace.append(op.to_dict())
            compiled(normalized=1, critical=1)

        scorer_nodes: list[ScorerBindingIR] = []
        for index, binding in enumerate(payload.get("scorer_bindings") or []):
            if not isinstance(binding, dict) or not isinstance(binding.get("scorer_id"), str):
                raise ContractCompileError("scorer binding requires an exact scorer_id")
            scorer_nodes.append(
                self._node(
                    "ScorerBindingIR",
                    binding,
                    source_layer=layer,
                    source_identifier=f"scorer_bindings[{index}]",
                    source_value=binding,
                    operators=(application("OP10_STRICT_SCALAR_NORMALIZATION", f"scorer_bindings[{index}].scorer_id"),),
                    namespace="scorer_id",
                )
            )
            compiled(exact=len(binding), critical=1)

        known_top = {"messages", "tools", "identifier_bindings", "scorer_bindings", *SESSION_FIELDS}
        for key in sorted(set(payload) - known_top):
            unsupported.append({"path": key, "semantic_critical": False, "reason": "request transport/generation telemetry"})

        provenance = (
            ProvenanceRecord(
                source_layer=layer,
                source_schema=f"BIC:{self.policy.benchmark}@{self.policy.contract_hash}",
                source_identifier="request",
                source_hash=digest(payload),
                field_path="$",
                authority="AUTHORITATIVE_BIC",
                note="complete request compilation",
            ).to_dict(),
        )
        return InterfaceContractIR(
            contract_version=CONTRACT_IR_VERSION,
            benchmark=self.policy.benchmark,
            source_layer=layer,
            session=session,
            messages=tuple(message_nodes),
            tools=tuple(tool_nodes),
            tool_parameters=tuple(parameter_nodes),
            tool_calls=tuple(call_nodes),
            tool_arguments=tuple(argument_nodes),
            action_handles=tuple(handle_nodes),
            observations=tuple(observation_nodes),
            scorer_bindings=tuple(scorer_nodes),
            identifier_bindings=tuple(identifier_nodes),
            unsupported_fields=tuple(unsupported),
            ambiguous_fields=tuple(ambiguous),
            compiler_operators_applied=tuple(trace),
            provenance_chain=provenance,
        )

    @staticmethod
    def _parameter_entries(schema: dict[str, Any], prefix: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
        yield prefix or "$", deepcopy(schema)
        properties = schema.get("properties") or {}
        for key in sorted(properties):
            child = properties[key]
            if isinstance(child, dict):
                yield from ContractCompiler._parameter_entries(child, f"{prefix}.properties.{key}")
        items = schema.get("items")
        if isinstance(items, dict):
            yield from ContractCompiler._parameter_entries(items, f"{prefix}.items")

    def compile_trace_event(self, event: Mapping[str, Any], *, source_layer: SourceLayer | str) -> InterfaceContractIR:
        """Compile an H0 canonical event without changing its authoritative payload."""
        if not isinstance(event, Mapping) or not isinstance(event.get("canonical_payload"), dict):
            raise ContractCompileError("canonical trace event is malformed")
        payload = deepcopy(event["canonical_payload"])
        layer = _enum_value(source_layer)
        event_type = str(event.get("event_type"))
        base = {
            "model": "DETERMINISTIC_CONSUMER",
            "tool_choice": "none",
            "event_type": event_type,
            "task_id": event.get("task_id"),
            "step": event.get("step"),
            "order_index": event.get("order_index"),
        }
        session = self._node("SessionIR", base, source_layer=layer, source_identifier="event.session", source_value=event)
        kwargs: dict[str, list[Any]] = {
            "messages": [], "tools": [], "tool_parameters": [], "tool_calls": [],
            "tool_arguments": [], "action_handles": [], "observations": [],
            "memory_records": [], "state_values": [], "state_transitions": [],
            "scorer_bindings": [], "identifier_bindings": [],
        }
        node_type = "ObservationIR"
        field = "observations"
        if event_type.startswith("MEMORY_"):
            node_type, field = "MemoryRecordIR", "memory_records"
        elif event_type in {"ACTION_MENU_EMITTED", "ACTION_SUBMITTED", "TOOL_CALLED"}:
            node_type, field = "ActionHandleIR", "action_handles"
        elif event_type in {"STATE_MUTATED"}:
            node_type, field = "StateValueIR", "state_values"
        elif event_type in {"TRANSITION_STARTED", "TRANSITION_COMMITTED", "TERMINAL_REACHED"}:
            node_type, field = "StateTransitionIR", "state_transitions"
        elif event_type.startswith("SCORER_") or event_type == "REWARD_EMITTED":
            node_type, field = "ScorerBindingIR", "scorer_bindings"
        kwargs[field].append(
            self._node(
                node_type,
                {"event_type": event_type, "payload": payload},
                source_layer=layer,
                source_identifier=f"event[{event.get('order_index')}]",
                source_value=event,
                operators=(application("OP3_OBJECT_KEY_CANONICALIZATION", "canonical_payload"),),
                ordering=OrderingSemantics.ORDER_SENSITIVE,
            )
        )
        return InterfaceContractIR(
            contract_version=CONTRACT_IR_VERSION,
            benchmark=self.policy.benchmark,
            source_layer=layer,
            session=session,
            **{key: tuple(value) for key, value in kwargs.items()},
            compiler_operators_applied=(application("OP3_OBJECT_KEY_CANONICALIZATION", "canonical_payload").to_dict(),),
            provenance_chain=session.provenance_chain,
        )

    def stats(self, source: Mapping[str, Any], compiled_ir: InterfaceContractIR) -> CompileStats:
        total = _field_count(source)
        unsupported = len(compiled_ir.unsupported_fields)
        ambiguous = len(compiled_ir.ambiguous_fields)
        normalized = len(compiled_ir.compiler_operators_applied)
        critical = sum(
            1
            for path in self._critical_paths(source)
        )
        critical_unsupported = sum(item.get("semantic_critical") is True for item in compiled_ir.unsupported_fields)
        return CompileStats(
            total_fields=total,
            compiled_fields=max(0, total - unsupported),
            exact_representation_fields=max(0, total - unsupported - normalized),
            normalized_representation_fields=min(total, normalized),
            unsupported_fields=unsupported,
            ambiguous_fields=ambiguous,
            semantic_critical_fields=critical,
            semantic_critical_compiled_fields=max(0, critical - critical_unsupported),
        )

    @staticmethod
    def _critical_paths(source: Mapping[str, Any]) -> Iterable[str]:
        for index, message in enumerate(source.get("messages") or []):
            yield f"messages[{index}].role"
            yield f"messages[{index}].content"
            for call_index, call in enumerate(message.get("tool_calls") or []):
                yield f"messages[{index}].tool_calls[{call_index}].id"
                yield f"messages[{index}].tool_calls[{call_index}].function.name"
                yield f"messages[{index}].tool_calls[{call_index}].function.arguments"
        for index, tool in enumerate(source.get("tools") or []):
            function = tool.get("function", tool)
            for key in ("name", "description", "parameters"):
                if key in function:
                    yield f"tools[{index}].{key}"


def policy_from_bic(path: str | Path) -> ContractPolicy:
    """Construct a policy only from a frozen official BIC JSON artifact."""
    import hashlib
    import json

    bic_path = Path(path)
    raw = bic_path.read_bytes()
    value = json.loads(raw)
    if value.get("completeness") != "COMPLETE":
        raise ContractCompileError(f"BIC is not complete: {bic_path}")
    return ContractPolicy(
        benchmark=value["benchmark_id"],
        contract_hash=hashlib.sha256(raw).hexdigest(),
        contract_version=value["benchmark_version"],
    )
