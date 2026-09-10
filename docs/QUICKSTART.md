# Quick start

Run commands from the repository root with Python 3.10+. The default verifier and four-fixture demo use the standard library only. The release validation records the exact Python version used for the smoke check; it does not claim testing on every supported interpreter.

1. Verify files and existing results:

   ```bash
   python3 -B tools/artifact.py verify
   ```

   Expected: `status: PASS`, 354 matrix cells, 144 primary adapter conditions, 36 action pairs and 7,200 timed repetitions. The timing median is calculated from the preserved observations; the verifier does not run a stopwatch benchmark.

2. Run four existing fixtures through the frozen symbolic core:

   ```bash
   python3 -B tools/artifact.py demo --output outputs/demo
   ```

   Expected: four decisions matching the frozen predictions, with `NEW_MODEL_CALLS`, `NEW_BACKEND_CALLS`, `NEW_GPU_RUNS` and `NEW_TIMING_MEASUREMENTS` all zero. The output includes `predictions.jsonl` and `DEMO_REPORT.json`. Use a new output directory for a later run.

3. Check packaging boundaries:

   ```bash
   python3 -B -m unittest discover -s tests -v
   ```

   These tests check integrity failure, path traversal rejection and existing-output protection. They do not run additional scientific cases.

The original `tools/run_full_core.py`, `tools/run_matrix_prediction.py` and `tools/run_core_ablations.py` are retained for source inspection and optional symbolic replay. Their study scopes differ. They are not called by the default verifier, and no full replay or new ablation was run during repository preparation. Historical outputs are in `recorded_outputs/`; keep new outputs in `outputs/`.

On systems where the interpreter is named `python`, replace `python3` accordingly. An optional virtual environment can be created with `python3 -m venv .venv`; no pip dependencies are needed for the default commands.
