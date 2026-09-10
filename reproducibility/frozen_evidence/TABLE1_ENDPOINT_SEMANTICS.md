## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: validate
- Origin Date: 2026-09-06T08:43:40.927987+00:00
- Verification Status: ANALYZED (offline evaluator-only; no backend rerun)
- Version Label: table1_endpoint_semantics_v1

# Table-I Endpoint Semantics

## Outputs genuinely defined per cell

- Raw equality, strict schema, and generic normalization explicitly define only
  binary block decisions in `scripts/ai_venue_pivot_compact_eval.py:36-52`.
- Full ParityMem defines class/reachability, severity, and first divergence in
  the sealed `artifacts/ai_venue_pivot_r0/preexecution_predictions.jsonl` rows.
- The component rows have binary aggregate counts whose all-or-none strata
  uniquely identify their cellwise binary decisions.

## Outputs not defined per cell

Representation analyzers do not emit R2/R3 or FD labels and are reported N/A.
The three component ablations also emit no FD labels.

More importantly, `scripts/ai_venue_pivot_compact_eval.py:79-107` writes component
`R2_R3_distinction_accuracy` constants directly. It does not iterate over cells,
does not emit predicted R2/R3 labels, and does not persist a severity output.
The fixed 354-cell records contain no variant field or component prediction.
P0/P1's own diagnosis says its execution/R2-R3 consequence is unavailable.

Therefore the frozen aggregate values 59/59, 0/59, and 0/59 cannot be
independently recomputed as “correct severity labels” without inventing labels.
They remain recorded aggregate diagnostics in JSON but become N/A in the
label-level candidate table. This mismatch, not the justified representation-
baseline N/A values, triggers `TABLE1_ENDPOINT_INCONSISTENCY_REQUIRES_REVIEW`.

`NOT_APPLICABLE_OUTPUT` means the analyzer does not produce the output. It is
never treated as an incorrect label or zero.
