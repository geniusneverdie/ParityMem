# Executed component interventions on frozen controlled inputs

This is a new post-hoc offline analysis of the original 300-case controlled suite, with 150 safe/expected cases and 150 defects. It supports the practical value of pairing, history closure and the P2/P3 evidence paths while keeping the original 354-cell and four-root tables separate.

| Variant | Outcome agreement | Safe false alarms | Defects detected |
|---|---:|---:|---:|
| Full | 300/300 | 0/150 | 150/150 |
| No pairing rejection | 289/300 | 0/150 | 139/150 |
| No history-closure rejection | 285/300 | 0/150 | 135/150 |
| P0/P1 only | 225/300 | 0/150 | 75/150 |
| Literal transport-ID pairing | 150/300 | 150/150 | 150/150 |

Full reproduces all 300 outcomes with zero safe false alarms. Suppressing pairing rejection loses 11 defect detections; suppressing history-closure rejection loses 15. Retaining P0/P1 alone detects 75 of the 150 defects. Requiring literal transport identity rejects all 150 safe/expected cases in this suite, showing the value of permitted ID variation.

Interventions have explicit operational definitions:

- **No pairing rejection:** retain the original projection checks but remove the pairing predicate's rejection effect.
- **No history-closure rejection:** suppress the recorded closure-rejection decision input in a local copy.
- **P0/P1 only:** suppress pairing and history-closure rejection and omit execution/scoring evidence from projection comparison.
- **Literal transport-ID pairing:** require literal ID preservation in addition to the original composite pairing predicate.

The original fixture files and source functions remain unchanged. Each variant executes the original decision body with scoped local interventions, and predictions are persisted before the separate scoring step opens gold. Development is post hoc, not a new blinded or preregistered study. These results do not replace historical Table 1/2 component aggregates. No LLM/backend/GPU call is made.
