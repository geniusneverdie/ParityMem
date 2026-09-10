# ContractIR Specification

Version `1.0.0` defines `InterfaceContractIR` as a typed aggregate, not a generic dictionary. It contains SessionIR, MessageIR, ToolDefinitionIR, ToolParameterIR, ToolCallIR, ToolArgumentsIR, ActionHandleIR, ObservationIR, MemoryRecordIR, StateValueIR, StateTransitionIR, ScorerBindingIR, and IdentifierBindingIR nodes.

Every node carries semantic type/value; source layer/schema/identifier/hash; order, default, null, encoding, and identifier-namespace semantics; complete provenance; applied compiler operators; and contract version. Unsupported fields are explicit and fail closed when semantic-critical. Scalars are never globally coerced; arrays remain ordered unless the BIC explicitly says otherwise.

The single semantic authority is the frozen official BIC for PM-Bench, STATE-Bench, or MemoryAgentBench. BIC, OpenAI wire, SGLang object, environment input, and scorer input compile to IR before comparison. Semantic hashes omit source-location metadata but full artifact hashes retain it.

Parity levels are P0 representation, P1 ContractIR, P2 execution effect, and P3 scorer effect. Outcomes are representation-only drift, semantic IR mismatch, execution mismatch, scoring mismatch, or ambiguous contract.
