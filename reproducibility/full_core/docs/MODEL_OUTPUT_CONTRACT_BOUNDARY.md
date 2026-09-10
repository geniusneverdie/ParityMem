# Model Output Contract Boundary

## Ownership

`BENCHMARK_NORMATIVE` and `RUNTIME_NORMATIVE` fields remain pre-HTTP fail-closed. `MODEL_GENERATED` fields are never presumed schema-valid: preserve raw bytes, invoke the frozen official parser/consumer, persist its validation or coercion result, then follow official benchmark semantics. `ENVIRONMENT_DERIVED` observations and `SCORER_DERIVED` mappings retain their own provenance.

This does not normalize M1. `EXTRA_ACTION_OR_HANDLE` is benchmark/harness-owned action-space distortion and must remain detectable. A model choosing an invalid action or emitting a wrong argument type is model behavior.

## Sequence 7

STATE-Bench `json.loads` produced the string `"false"`. `BaseEnvironment.parse_bool` officially converted it to `False`. `process_return` executed and returned `{"error": "Policy review required. Call get_policies(topic='return') first."}` because policy review had not occurred. Durable environment state was unchanged and the episode would continue with that exact tool result. This is `MODEL_OUTPUT_SCHEMA_EVENT / COERCED_BY_OFFICIAL_VALIDATOR`, not an infrastructure contract mismatch.

No generic repair is permitted. The raw string and normalized boolean coexist in `ModelOutputIR`; the normalized value never replaces the raw evidence.
