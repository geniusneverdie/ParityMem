# Benchmark Interface Contract (BIC)

The BIC is a source-cited, versioned statement of what a benchmark exposes and
what its harness is authorized to do. It contains ten required sections:

1. session creation/reset/terminal semantics;
2. observation visibility and ordering;
3. memory reads, writes, persistence, and authority;
4. legal actions, tools, handles, parameters, and invalid-action behavior;
5. action validation and state-transition semantics;
6. authoritative, derived, memory, and database state;
7. deterministic and judge-based scorer boundaries;
8. identifier namespaces and conversions;
9. order-sensitive and order-insensitive fields;
10. externally visible side effects and idempotency.

Every assertion records the frozen upstream commit, repository-relative file,
symbol, line range, raw field names, support kind (code/test/documentation),
confidence, and limitations. A `COMPLETE` contract cannot have an empty section.
A `BLOCKED` or `PARTIAL` contract must list unresolved reason codes rather than
fill gaps by inference.

Capability profiles are explicit and total over:

- `HAS_DYNAMIC_ACTION_MENU`
- `HAS_STATIC_TOOL_SCHEMA`
- `HAS_MUTABLE_ENVIRONMENT`
- `HAS_MEMORY_HOOK`
- `HAS_MULTI_SESSION_STATE`
- `HAS_DETERMINISTIC_SCORER`
- `HAS_LLM_JUDGE`
- `HAS_LURE_HANDLES`
- `HAS_FINAL_STATE_SCORER`

The unified schema does not require every benchmark to have every capability.
Unsupported layers are not fabricated. In particular, MemoryAgentBench's answer
surface is not mislabeled as a PM-Bench-style dynamic action menu.
