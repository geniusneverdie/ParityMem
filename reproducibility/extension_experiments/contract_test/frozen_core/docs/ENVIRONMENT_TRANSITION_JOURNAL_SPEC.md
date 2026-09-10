# Environment Transition Journal Specification

For every action the required order is: `RAW_RESPONSE_PERSISTED` → `MODEL_OUTPUT_PARSED` → `OFFICIAL_VALIDATION_RESULT_PERSISTED` → `TRANSITION_INTENT_PERSISTED` → fsync → environment execution → `TRANSITION_RESULT_PERSISTED` → fsync → `TRANSITION_COMMITTED` → `NEXT_OBSERVATION_MATERIALIZED` → next request.

Every JSONL event is append-only, SHA256 chained, and fsynced with its directory. Transition intent binds unit/request/response IDs, raw response, parsed action, ModelOutputIR, official validation, intended tool/arguments, pre-state, and environment epoch. The result binds exact tool/error output, post-state, next observation, terminal flag, and side-effect identity.

Recovery never reissues a model call. Before intent, parse/validation resumes from raw response. Intent without result is replayable only from a verified deterministic local copy-on-write snapshot; otherwise reconciliation is mandatory. A persisted result is committed without environment re-execution. A committed transition is never executed again.

STATE-Bench uses task-local in-memory dataclasses loaded from a frozen JSON fixture and supports deterministic `deep_copy` plus full snapshots, but it has no durable database transaction or universal tool idempotency key. Future runners therefore must execute on copy-on-write sandbox state and publish it only after result persistence/commit; external side effects require explicit reconciliation.
