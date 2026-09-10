# Canonical actions and the three stable cases

The supplied source snapshots document the existing parser normalization and action-extraction rules. Official-parser argument strings are JSON-decoded when possible. An action records its kind and ordered tool/name/argument entries; transport IDs are omitted. Hashing sorts object keys using compact JSON serialization and retains array order and string contents, including code. Nonempty output without accepted tool calls has kind `NO_TOOL_ACTION`; parser failures and empty output are invalid. Code is compared as argument text; program equivalence and task score require execution/scoring.

`cross_backend_modal_results.json` is an unchanged snapshot of the existing 36-pair study. `tools/verify_method_evidence.py` recomputes hashes from every stored repeat action and verifies all five repeats per backend, 33 invariant pairs, three differing pairs, and 288 same-process plus 432 cross-restart comparisons.

The new case table abbreviates these exact differences:

- tau3 trace 7e882479-72f7-49b8-9160-97c6b86d1f42: SGLang has no tool action; vLLM calls `get_order_details` with `order_id='12345'`.
- AppWorld 036: both call `python_exec`; SGLang uses `apis.api_docs.get_continuation_token()` inside the API-description request, whereas vLLM supplies `app_name='gmail'` to that lookup.
- AppWorld 088: both call `python_exec`; SGLang uses `apis.supervisor.get_latest_environment_result()`, whereas vLLM uses `apis.supervisor.get_latest_environment()`.

Each backend condition is 5/5 stable. These are action/code differences; the table does not assign a better-performing backend or claim execution inequivalence. No model or parser was rerun to prepare this clarification.
