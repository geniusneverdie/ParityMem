# Real-World Defect Severity

- R0 REPRESENTATION_ONLY_SAFE: byte/ordering drift with semantic, execution, and scoring parity.
- R1 BOOKKEEPING_OR_PROVENANCE_DEFECT: audit/identity metadata defect without current execution/scorer change.
- R2 MODEL_VISIBLE_SEMANTIC_DEFECT: changed model-visible meaning without model-free execution consequence.
- R3 EXECUTION_RELEVANT_DEFECT: tool pairing, transition, state, or legal trajectory continuation changes.
- R4 SCORING_OR_OUTCOME_RELEVANT_DEFECT: deterministic official scorer input/output or task outcome changes.

Severity is the highest layer proven by fixed model-free evidence; it is not a model-accuracy claim.
