# ICASSP-E3 Efficiency and Scalability Protocol

Frozen after the non-scientific smoke and before scientific timing.

## Study identity

E3 is a new prospective model-free study. E2-D/E remain blocked historical
artifacts and are not retried or modified.

## Scientific workload

The full input registry preserves all 354 eligible E1 compatibility cells
(295 Safe, 59 Defect/F2). Conservative smoke projection exceeds the frozen
two-hour total budget, so the deterministic 72-cell subset in
`registries/E3_TIMED_REAL_SUBSET.json` is the primary real-trace workload.
Cells remain distinct backend/template decisions.

For each selected decision:

- 20 warmups;
- 100 timed repeats;
- single process, one worker, CPU 1 affinity;
- no parallel throughput measurement.

Every timed decision must reproduce its frozen Safe/Defect verdict. Any mismatch
immediately terminates the run as `E3_HARNESS_SEMANTIC_MISMATCH`.

## Non-overlapping component timers

`time.perf_counter_ns()` surrounds these sequential callable boundaries:

1. `T_parse_or_load`: JSON materialization of the frozen decision input;
2. `T_contractir`: frozen `ContractCompiler.compile`;
3. `T_p0_p3`: frozen server renderer, compiler, and ContractIR equivalence;
4. `T_pairing`: frozen identity-pairing checker;
5. `T_history_closure`: frozen round-trip closure plus exact model template;
6. `T_first_divergence`: fail-closed verdict and first-divergence selection;
7. `T_total`: the complete sequential compatibility decision.

Nested component times are not added to another component. `T_total` is timed
independently around the complete sequence.

## Complexity metadata and frozen strata

Every registry row records turns, messages, calls, results, serialized bytes,
ContractIR nodes, and a harness edge descriptor. The edge descriptor counts
ordered-message, call-argument, identifier, observation/result, transition,
and scorer-binding relations; it is a scaling descriptor, not a new semantic
definition.

Real-trace `T_total` is stratified by:

- frozen Safe versus Defect verdict;
- history turns: the registry has only one observed turn, so one bucket is
  reported and no empty post-hoc bins are invented;
- tool-call buckets: 0–1, 2, 3–4, and >=5;
- ContractIR nodes: frozen registry thresholds <=16, <=16, and >16; the middle
  bucket may be empty because of tied node counts.

## Memory endpoint

Boundary RSS fields are retained on each latency record but are not claimed as
transient peaks. The primary memory endpoint uses 12 frozen representative
real inputs in fresh processes. After tokenizer loading, a 100-decision batch
is sampled every 1 ms with psutil; baseline, peak, and delta RSS are reported.
`tracemalloc` peak is reported separately and covers Python allocations only.

The same procedure uses 200-decision fresh-process batches for all 12 scaling
points. Median and p95 RSS delta across representative batches are the memory
headlines; no sub-resolution precision is inferred.

## Structural scalability

Two deterministic Qwen-based axes use a frozen valid source motif:

- tool calls: 1, 2, 4, 8, 16, 32 in one completed turn;
- completed history turns: 1, 2, 4, 8, 16, 32 with one paired call/result per
  turn.

Identifiers are fresh and injective, role order is valid, and no F1–F4 defect
is introduced. Every row is `SCALABILITY_ONLY_SYNTHETIC` and excluded from
semantic-accuracy denominators. Each point uses 20 warmups and 200 timed
repeats.

Predeclared descriptive analyses are Spearman correlation and log-log OLS
slope/R-squared for axis value and actual ContractIR nodes versus median total
latency. These are empirical fits over the tested range, not complexity-theory
claims.

## Aggregation and failures

For every timing endpoint: median, p95, IQR, minimum, maximum. No observations
are discarded as outliers. Invalid system events or exceptions remain explicit
failure records. Arithmetic mean is not a headline.

Before execution, the command requires load1/logical CPU <=0.5, available RAM
>=128 GiB, swap used <=48 GiB, two one-second CPU utilization samples <=70%,
no concurrent E3, and exact CPU affinity `{1}`. Violation yields
`SAFE_RESOURCE_PAUSE` before timing; protocol values do not change.

## Optional inference context

`INFERENCE_COST_RATIO = NOT_AVAILABLE`. Frozen E1/E2 duration fields lack the
required unambiguous explicit request-start plus completion record. No model
call may be made to fill this gap.

## Hard call boundary

```text
LLM_MODEL_CALLS = 0
SGLANG_REQUESTS = 0
VLLM_REQUESTS = 0
TRANSFORMERS_GENERATION_CALLS = 0
BENCHMARK_ENVIRONMENT_CALLS = 0
```

## Exactly-once execution

The exact command is the string in `E3_MEASUREMENT_CONFIG.json`. It may run
once only after explicit human confirmation. Output collision, semantic
mismatch, resource pause, or failure is terminal for that invocation. There is
no automatic retry.

