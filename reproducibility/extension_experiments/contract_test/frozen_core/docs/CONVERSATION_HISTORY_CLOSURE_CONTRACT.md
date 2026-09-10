# Conversation-History Closure Contract

For a frozen model/runtime M, H0 requires `ReachableOutputSpace(M) ⊆ HistoryEncoderDomain(M)`. C0 is parser closure, C1 is official benchmark execution closure, and C2 is frozen history-encoder closure. Full closure additionally requires semantic round-trip preservation of tool-call IDs, names, arguments, result pairing, ordering, coercion provenance, and state consequences.

`MODEL_RUNTIME_HISTORY_CLOSURE` is RUNTIME_NORMATIVE. A reachable output that STATE executes but the next-turn template rejects is `REACHABLE_UNENCODABLE_OUTPUT`; it is infrastructure conformance failure, not model task failure. H0 never patches, splits, merges, drops, or textualizes tool calls.
