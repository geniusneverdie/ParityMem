# Executable frozen decision core

Run from the paper root:

```bash
python tools/run_full_core.py --demo
python tools/reproduce.py
```

Python 3.10+ and the standard library suffice. Outputs are written under `reproduction_output/`; `--out` selects another directory. No command starts a model server or accesses the network.

## What the entry points compute

- **Controlled P0–P3 core:** `runner.py` executes the original controlled-validation `predict()` function. The typed IR builder, projection comparison, pairing check, closure decision and first-divergence selection recompute predictions from recorded normative/observed evidence. All 300 outputs match the original prediction records exactly, and all 300 class, severity and first-divergence endpoints match gold.
- **Natural-matrix rules:** `matrix_rule.py` isolates the original source-specific `prediction()` function without its preparation script's side effects. It recomputes all 354 matrix predictions from model/backend identities and natural projections. This is a separate original entry point, with its own study scope.
- **Component interventions:** `tools/run_core_ablations.py` executes clearly defined post-hoc interventions on the controlled suite and produces 1,500 per-case predictions. See `CONTROLLED_COMPONENTS.md`.

The full 59-file frozen source set is included and hash-bound. Active controlled-runner imports use `contract_ir.equivalence`, `contract_ir.nodes`, `contract_ir.schema` and `h2b_h1.identity`; the separately named general parity module is retained for source inspection. All original prediction-function ASTs are unchanged. The only edit to the portable controlled runner changes the absolute import root to the local vendor directory.

## Input and evidence contract

The controlled fixtures contain normative/observed representations, semantic projections, recorded execution/scoring values, pairing relations, history-acceptance evidence and ordered trace events. They exercise decisions over recorded evidence; this entry point is not a new pre-consumer validation experiment. Gold files and saved prediction labels are used by the separate verifier, not by `predict()`.

Each output includes the actual computed prediction plus integration, normative owner and the matching trace event. The composite pairing predicate also checks arguments, normalization provenance and execution order. It therefore has a wider meaning than the gold file's narrower association annotation; the published replay endpoints are classification, severity and first divergence.

The matrix entry point is restricted to its original frozen model/backend profile. Generalizing it to a new consumer requires that consumer's confirmed contract. Runtime/version tests and recorded cost measurements retain their original scope.
