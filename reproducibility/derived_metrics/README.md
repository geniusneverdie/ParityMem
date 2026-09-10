# Count-derived balanced accuracy

`table1_balanced_accuracy.json` records the input registry SHA256, exact fractions, aggregate confusion counts and explicit computation scope. `table1_balanced_accuracy.csv` is the compact seven-variant view.

The source audit summary supplies 295 safe and 59 blocked cases. These two class-specific rates receive equal weight. Full ParityMem: 100%; the other six variants: 50%. This is a derived statistic on the original frozen matrix, not a new empirical result or an independent per-cell replay.

Generate with `python tools/recompute_table1_summary.py --write`; verify with `--check`.
