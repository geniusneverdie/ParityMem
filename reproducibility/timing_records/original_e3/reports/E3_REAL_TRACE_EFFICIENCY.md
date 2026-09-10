# E3 Real-Trace Efficiency

## Material Passport

- Source: frozen E1 compatibility inputs
- Selected decisions: 72 from the preserved 354-cell registry
- Warmups: 20 per decision
- Timed repeats: 100 per decision
- Timed records: 7,200
- Timed decision mismatches: 0

| Endpoint | Median | p95 | IQR |
|---|---:|---:|---:|
| Parse/load | 0.0207 ms | 0.0404 ms | 0.0065 ms |
| ContractIR | 1.4992 ms | 2.0738 ms | 0.1284 ms |
| P0–P3 | 2.0678 ms | 2.8900 ms | 0.2023 ms |
| Pairing | 0.0184 ms | 0.0221 ms | 0.0014 ms |
| History closure | 0.2593 ms | 0.5102 ms | 0.0967 ms |
| First divergence | 0.000643 ms | 0.000744 ms | 0.000087 ms |
| **Total compatibility decision** | **3.9439 ms** | **5.4788 ms** | **0.3868 ms** |

The minimum and maximum total observations are 3.3322 ms and 141.8685 ms.
No observation was removed as an outlier.

Frozen-verdict stratification:

- Safe: 6,000 records, median 3.9214 ms, p95 5.2114 ms.
- Defect/F2: 1,200 records, median 4.1063 ms, p95 7.5268 ms.

The source inputs have one user turn and at most one tool call, so their
history-turn and tool-count strata collapse to the single observed buckets.
The larger ContractIR-node bucket (>16 nodes) has median 4.8556 ms versus
3.8903 ms for <=16 nodes.

Classification: `MAIN_TEXT_PRIMARY`.

