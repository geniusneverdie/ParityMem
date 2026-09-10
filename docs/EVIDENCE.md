# Evidence map and denominators

| Claim | Unit / denominator | Repository evidence |
|---|---|---|
| Compatibility prediction | 354 trace–model–backend cells, 295 safe / 59 blocked | `reproducibility/frozen_evidence/TABLE1_CELLWISE_354.csv`, sealed predictions and official outcomes in the same folder |
| Post-hoc record baselines | 3 methods × 354 cells = 1,062 outputs | `reproducibility/offline_baselines/` |
| Controlled holdout | 300 cases, including the same 120 novel compositions | `reproducibility/full_core/holdout_inputs.jsonl`, separate predictions and gold |
| Independent programmatic adjudication | 60 sampled holdout cases | `reproducibility/adjudication/` |
| Frozen-core adapter reuse | 48 traces × three applicable variants each = 144 primary conditions | `reproducibility/extension_experiments/contract_test/` |
| Conditional behavior comparison | 36 admitted pairs × 2 backends × 5 historical calls | `reproducibility/action_comparison/cross_backend_modal_results.json` |
| Version/configuration identity | Eight historical server batches for the 36-pair study | `reproducibility/runtime_binding/PUBLIC_RUNTIME_CONFIGURATION.json` |
| Mechanism coverage and consequence | Four roots | `reproducibility/mechanism_details/source/closure_ablation.json`, `layer_ablation.json` |
| Next-turn probe | Three repeated probes of the same input per relevant root | `reproducibility/mechanism_details/source/reproducer_results.json`, `counterfactual_repair_results.json` |
| Recurring symbolic audit cost | 72 decisions × 100 timed repetitions = 7,200 observations | `reproducibility/timing_records/original_e3/raw/E3_REAL_TRACE_TIMINGS.jsonl` |
| Contract transfer | Per-integration source profiles | `reproducibility/integration_transfer/` |
| Frozen τ³ replay | 14 historical tool calls | `reproducibility/extension_experiments/execution/TAU_EXECUTION_REPORT.json` |

## Interpretation

- Table 1 separates sealed Full predictions, post-hoc record baselines and historical aggregate-derived component summaries. These evidence kinds retain their original labels.
- The 120 novel compositions are a **subset of 300**. The 60 adjudicated cases are sampled from that holdout, not new cases to add to it.
- The adjudicator is a separate Python program over recorded official/observed evidence, with no gold access or checker imports at prediction time. Its independent scoring stage compares with labels afterwards.
- There are six named controlled contract profiles in total: Mistral ID-length guards 6/9/12 and Llama call-count guards 1/2/3. Each trace uses its own family's three applicable variants. The two aliases produce 288 evaluations but retain 144 primary conditions.
- Four-root capability summaries use the original frozen feature/capability analysis. They are not executions of newly implemented competing systems. The three-repeat probe denominator counts repeated checks of one frozen input per root.
- The next-turn continuation view records three historical model responses, with no official environment task step executed. It supports model continuation, not task success. The public view states the original record hash and omitted machine fields.
- The 36-pair action study uses **SGLang 0.5.6.post2 and vLLM 0.23.0**. SGLang 0.5.16 and vLLM 0.11.0 are separate version-validation settings. Same canonical action is distinct from demonstrated task equivalence.
- Timing and action studies both contain a number 72, but their units and records differ. Existing latency records are preserved; no fresh performance benchmark is run by `verify`.
- τ³ replay restoration and matching persistent state do not establish task success; the recorded order query fails. AppWorld remains contract-level transfer evidence, with no approximate execution study added.
- The 642-unit revalidation belongs to the original v7 extended freeze package and rechecks existing endpoints. It is not a denominator of new independent scientific cases.

## Provenance

`SOURCE_PROVENANCE.json` lists byte-preserved files from the v7 package. `MANIFEST.sha256` covers this repository candidate. Public field-selection views are labeled as derived views, with source hashes and exact fields retained; they do not replace the full local originals. Original sealing chronology is retained in original records, not re-created by current packaging hashes.

The default verifier reads existing records. The four-case demo checks that the packaged frozen code runs, and adds no new paper evidence.
