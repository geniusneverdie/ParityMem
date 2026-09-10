# E3 Structural Scalability

## Result status

```text
SCALABILITY_TOOL_CALL_AXIS = PASS
SCALABILITY_HISTORY_AXIS = FAIL
```

All scaling inputs are `SCALABILITY_ONLY_SYNTHETIC` and enter no semantic
accuracy denominator.

## Tool-call axis

| Calls | ContractIR nodes | Median total | p95 total |
|---:|---:|---:|---:|
| 1 | 15 | 3.568 ms | 3.655 ms |
| 2 | 20 | 4.670 ms | 4.860 ms |
| 4 | 30 | 6.868 ms | 7.009 ms |
| 8 | 50 | 10.955 ms | 11.283 ms |
| 16 | 90 | 19.319 ms | 20.162 ms |
| 32 | 170 | 36.264 ms | 37.655 ms |

Median total latency increases monotonically over the tested range. The
predeclared Spearman correlation is 1.0. The descriptive log-log slope versus
tool-call count is 0.673 (R² 0.980); versus actual ContractIR nodes it is 0.952
(R² 0.9998). These are empirical finite-range summaries, not asymptotic
complexity claims.

## History-turn axis

The one-turn point completed (median 3.591 ms). The two-turn input returned
`DEFECT` instead of frozen `SAFE` on warmup 0. The frozen semantic-mismatch rule
terminated the command immediately. No 2/4/8/16/32-turn timing and no
history-axis fit are reported. The generator and harness were not repaired or
retried.

Failure:
`E3_HARNESS_SEMANTIC_MISMATCH:WARMUP:E3_SCALE::HISTORY_TURNS::02:0:DEFECT:SAFE`

Classification: valid tool axis `MAIN_TEXT_SUPPORTING`; history axis
`INCONCLUSIVE`.

