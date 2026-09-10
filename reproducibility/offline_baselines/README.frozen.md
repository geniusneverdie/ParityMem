# Executed post-hoc record baselines

This revision implements and executes three transparent record-level comparators on 354 frozen input pairs, yielding 1,062 persisted predictions. Development is post hoc: historical outcomes were known. The prediction functions take source and target records only; they neither read outcome labels nor import ParityMem logic. Separate scoring uses the frozen official outcome labels.

Input records contain assistant content, ordered calls (ID/name/arguments), and ordered results (ID/content). Source records come from the original natural projection; target records come from the frozen backend history. All other metadata and outcomes are excluded from the predictor inputs. Source paths and hashes are in `protocol.json`; `PREPARE_INPUTS.py.txt` records preparation for inspection and is not a portable inference launcher.

- Raw equality compares these structured records with IDs retained (object keys serialized deterministically).
- Strict schema is a local record schema: required record fields, call/result field types, nonempty string IDs, object-valued decoded arguments, and source-listed tool names. It has no consumer-specific ID-domain, pairing, or next-history closure rule.
- Generic normalization JSON-decodes argument/result values, removes transport IDs, retains order and other values, and compares canonical records. It does not validate cross-record pairing or consumer acceptance.

`predictions.jsonl` contains actual function outputs, not expansion of aggregate counts. The outcomes reproduce the original table values: raw equality 59/354 with 295/295 safe false alarms; the other two 295/354 with zero safe false alarms and 0/59 blocking recall. Each has 50% balanced accuracy. Component summaries elsewhere remain historical aggregate-derived evidence and are not claimed as newly executed ablations.

Run `python tools/offline_record_baselines.py` from the paper root to recompute predictions, then `python tools/verify_method_evidence.py` for separate scoring and integrity checks. `python tools/test_offline_record_baselines.py` checks identity acceptance, safe ID rewrites, semantic changes, local schema errors, call ordering, and the deliberately absent pairing check.
