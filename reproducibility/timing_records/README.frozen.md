# Original recurring-audit timing evidence

`original_e3/raw/E3_REAL_TRACE_TIMINGS.jsonl` is an unchanged copy of the original measurement records: 7,200 latency repetitions over 72 decisions, plus the original 12 memory-batch records. The measurement configuration specifies 20 warmups and 100 timed repetitions per decision. The median 3.94 ms and p95 5.48 ms are the manuscript's original recurring symbolic-audit endpoints.

The timed interval covers JSON materialization through ContractIR construction to first-divergence selection. Human source/contract preparation, tokenizer loading and model inference are excluded. The 72 timing decisions and the 72 backend conditions underlying the 36-pair action study have different units and identities; their denominators are not interchangeable.

The same folder preserves scaling observations, registries, configuration, relevant harness source and original reports. Historical manifests may refer to other files from the original experiment directory; the subset copied here is explicitly enumerated and hashed in `../ADDITIONAL_SOURCE_BINDINGS.json`. No missing observations were generated, and no timing or memory measurements were rerun for v7.
