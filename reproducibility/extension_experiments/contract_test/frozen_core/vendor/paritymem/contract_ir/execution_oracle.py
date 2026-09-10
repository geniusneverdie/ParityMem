"""Zero-model deterministic consumer and scorer relation oracles."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from typing import Any, Callable, Mapping

from paritymem.contract_ir.nodes import InterfaceContractIR, digest
from paritymem.contract_ir.schema import validate_json_schema


@dataclass(frozen=True)
class OracleResult:
    accepted: bool
    observable_effect: Any
    effect_hash: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _schema_by_name(ir: InterfaceContractIR) -> dict[str, dict[str, Any]]:
    return {
        node.canonical_value["name"]: deepcopy(node.canonical_value["parameters"])
        for node in ir.tools
    }


def execute_tool_calls(
    ir: InterfaceContractIR,
    handlers: Mapping[str, Callable[..., Any]],
    *,
    state_snapshot: Callable[[], Any] | None = None,
) -> OracleResult:
    """Validate official schemas, call exact registered handlers, capture effect."""
    schemas = _schema_by_name(ir)
    outputs = []
    before = deepcopy(state_snapshot()) if state_snapshot is not None else None
    try:
        for node in ir.tool_arguments:
            value = node.canonical_value
            name = value["function"]
            if name not in schemas or name not in handlers:
                raise ValueError(f"undeclared tool {name}")
            kwargs = deepcopy(value["arguments"])
            validate_json_schema(kwargs, schemas[name], path=f"tool.{name}.arguments")
            outputs.append({"call_id": value["call_id"], "function": name, "result": handlers[name](**kwargs)})
        after = deepcopy(state_snapshot()) if state_snapshot is not None else None
        effect = {"outputs": outputs, "state_before": before, "state_after": after}
        return OracleResult(True, effect, digest(effect))
    except Exception as exc:
        effect = {"outputs": outputs, "state_before": before, "rejected": type(exc).__name__}
        return OracleResult(False, effect, digest(effect), f"{type(exc).__name__}: {exc}")


def synthetic_consumer(ir: InterfaceContractIR) -> OracleResult:
    """Benchmark-aware pure consumer used by frozen metamorphic fixtures."""
    state: dict[str, Any] = {"calls": [], "values": {}, "sequence": []}

    def snapshot() -> dict[str, Any]:
        return deepcopy(state)

    handlers: dict[str, Callable[..., Any]] = {}
    for tool in ir.tools:
        name = tool.canonical_value["name"]

        def handler(_name: str = name, **kwargs: Any) -> Any:
            state["calls"].append(_name)
            state["sequence"].append(deepcopy(kwargs))
            state["values"].update(deepcopy(kwargs))
            return {"tool": _name, "accepted": True, "arguments": deepcopy(kwargs)}

        handlers[name] = handler
    return execute_tool_calls(ir, handlers, state_snapshot=snapshot)


def deterministic_score(effect: Any, *, scorer_id: str = "exact_contract_score") -> dict[str, Any]:
    """A deterministic scorer item preserving identifier and aggregate contribution."""
    accepted = bool(effect.get("accepted", True)) if isinstance(effect, dict) else True
    observable = effect.get("observable_effect", effect) if isinstance(effect, dict) else effect
    contribution = 1 if accepted and observable is not None else 0
    item = {"scorer_id": scorer_id, "per_unit_score": contribution, "aggregate_contribution": contribution, "observable_hash": digest(observable)}
    return item
