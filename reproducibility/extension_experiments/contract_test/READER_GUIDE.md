# What the 144 adapter conditions test

The new declarative adapter is `../scripts/contract_adapter.py`. It maps declared guard/serialization fields and input trace features into the existing checker interface. The preserved core lives in `frozen_core/`; its manifests bind the original implementation. Predictions are sealed before consumer-template validation, with separate prediction and validation programs.

The 48 controlled traces are generated from source-grounded template constraints by `../scripts/generate_contract_cases.py`. `GENERATION_RECORD.json` records generation and ID seed information; `cases.jsonl` retains every input, marker and alias. These are controlled traces, not 48 newly collected agent task episodes.

Each trace is evaluated under three applicable variants from its template family. There are six named profiles overall:

| Family | Profiles | Changed obligation | Preserved behavior |
|---|---|---|---|
| Mistral | Mistral_6, Mistral_9, Mistral_12 | The two ID-length guards require 6, 9 or 12 characters | Argument content and valid role sequences |
| Llama | Llama_1, Llama_2, Llama_3 | The exact call-count guard requires 1, 2 or 3 calls | The original serializer's first-call capacity |

`contracts.json` binds all six profiles and original/variant template hashes; `PROTOCOL.md` records the intervention design. Keeping the Llama serializer fixed checks both consumer acceptance and model-visible preservation when its declared guard changes. These are controlled copies of released templates; they are not production model upgrades.

The primary denominator is 144 trace–contract conditions: 16 safe and 128 defective. Recorded verdict, consequence and first-divergence agreement is 144/144. Each condition also has two name-only aliases, yielding 288 stored evaluations; alias repetitions are not additional primary cases. The 48 contract-change contrasts involve 24 traces and remain a separately reported contrast endpoint. All values come from the existing `CONTRACT_TEST_REPORT.json` and individual input/prediction/validation records.

This evidence supports reuse of an integration-specific adapter/contract with a frozen checking core. It does not assert unrestricted compatibility for arbitrary new integrations or independent external double-blind validation.
