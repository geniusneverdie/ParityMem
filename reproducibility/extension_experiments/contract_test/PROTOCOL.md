# Pre-outcome contract substitution protocol

Freeze the original P0-P3 core plus a newly introduced declarative contract adapter. Generate 48 unique traces, cross them with three relevant contracts, and evaluate two name-only aliases: 144 semantic conditions and 288 evaluations. Seal all predictions before running the consumer templates.

Mistral variants change the original two ID-length guards to 6, 9 or 12; arguments and valid role sequences remain fixed. Llama variants change the exact tool-count guard to 1, 2 or 3 and retain the original first-call serializer. The latter deliberately tests acceptance together with model-visible preservation; serializer capacity is documented from source before outcomes. All variants are controlled copies, not production model upgrades.

The new adapter reads declared guard/serialization fields and input traces, computes prospective feature projections, and invokes the frozen core. It never reads consumer validation output. Gold is obtained afterwards by executing the real template copies and checking exceptions and unique argument-marker preservation. Original files are untouched. This is pre-outcome sealing, not an independently designed double-blind evaluation.
