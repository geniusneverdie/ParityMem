# Code and input contract

The frozen core is provided with source bindings rather than repackaged into an unrelated new implementation. The public entry point delegates to the same `runner.py:predict()` function used by the existing controlled replay.

| Code | Responsibility |
|---|---|
| `reproducibility/full_core/runner.py:build_ir` | Lift the recorded official and observed views into typed ContractIR nodes |
| `reproducibility/full_core/runner.py:predict` | Combine projections, pairing, closure, consequence and first-divergence selection |
| `reproducibility/full_core/vendor/paritymem/contract_ir/` | Typed interface representations and projection comparison |
| `reproducibility/full_core/vendor/paritymem/h2b_h1/identity.py` | Call/result binding and pairing-preserving closure |
| `reproducibility/full_core/matrix_rule.py` | Separate original natural-matrix rule, restricted to its frozen profile |
| `reproducibility/extension_experiments/scripts/contract_adapter.py` | Declarative adapter for the controlled contract-substitution study |

An input fixture includes `fixture_id`, `integration_id`, `official`, `observed`, `pairing`, `history`, `ownership` and ordered `trace` evidence. Official/observed views contain representations, semantics and recorded execution/scoring values. The checker requires this evidence; a raw chat transcript alone is not a complete replacement input.

`holdout_inputs.jsonl` contains 300 existing fixtures. Saved predictions and gold labels are separate files. The four-fixture demo computes decisions before reading saved predictions for comparison; it does not read gold. Its fixed IDs cover safe representation drift, expected official behavior, semantic change and a closure/execution defect.

Contract and pairing checks retain identifiers. Permitted transport IDs are omitted only in the later canonical-action comparison over admitted paths. Arrays and strings, including code, retain their semantics and order under the frozen action rules.

Original runner import isolation and file hashes are checked before execution. Archived `*.py.txt` source snapshots preserve provenance and may contain historical local paths. They are not imported by the default commands. Optional environment/template measurement programs in historical studies are likewise outside the default offline entry points.
