# E3 Harness Provenance

## Import boundary

The smoke used:

```text
PYTHONPATH=/data9/amx/fourth/paritymem
Python 3.11.15
CPU affinity: {1}
```

Frozen modules called by the wrapper:

| Module | Path | SHA256 |
|---|---|---|
| ContractIR compiler | `paritymem/contract_ir/compiler.py` | `cf17ee5450879c7a5ea0ef80de9f6f7215b78b9c1fcd0b2b2df08a0ef05af764` |
| P0–P3 equivalence | `paritymem/contract_ir/equivalence.py` | `b550ae27eb8d7150ffe78170231a5992ff6643909b0928ade707e3880a2a3bd2` |
| ContractIR renderer | `paritymem/contract_ir/renderers.py` | `40e84d6e2828c070049c078703c7670a9003306c97d10f294fd7147b4c89736b` |
| Contract schema | `paritymem/contract_ir/schema.py` | `6c37fc8436766e9ef938d8d29b097c8772737c028cce904abd3c82486028a766` |
| History closure | `paritymem/h2b_h0/closure.py` | `e43fc2be84f98f0ee65e719269b422d248104422ae95fedb8b5b74ab1d2d1451` |
| Identity pairing | `paritymem/h2b_h1/identity.py` | `07c6ffdf3ddfc37fce754fc1a7668f614839d91e11991b0941ba02e212268d3c` |

Instrumentation wrapper:

- `harness/e3_core.py`, smoke-time SHA256
  `19a934ebd796d32e6c1c3a7da04aa5a4fff3902a2bd7a279b0fb533d6ffdb6f5`.
- The wrapper adds JSON loading, monotonic component timers, complexity
  metadata, and verdict comparison. It does not edit imported method code.

Dependencies:

- Transformers 4.57.1, METADATA SHA256 `5a790714…`, RECORD `aa696ac3…`.
- torch 2.9.1+cu128, METADATA `b3a05d36…`, RECORD `e15f2926…`.
- psutil 7.2.2, METADATA `525f8ba7…`, RECORD `a7286fe8…`.

## Non-scientific smoke

The one-record smoke is preserved at `raw/E3_HARNESS_SMOKE.json` with SHA256
`a742a196dcd6bdfeac733c68c4c766488030ad5d3974c0ea5b36f7361ab3d225`.

```text
HARNESS_IMPORT = PASS
CONTRACTIR_CALL = PASS
P0_P3_CALL = PASS
PAIRING_CALL = PASS
CLOSURE_CALL = PASS
TIMING_INSTRUMENTATION = PASS
MEMORY_INSTRUMENTATION = PASS
```

The smoke produced zero model, SGLang, vLLM, Transformers-generation, and
benchmark-environment calls. Its 162,834,820 ns timing is non-scientific and is
used only for pre-measurement cost projection.

## Sealed execution harness

- `harness/e3_memory_worker.py`: SHA256
  `7af1f4da73fbfc3a9b4c82d89a337f4551bb3a6dda92adb01ffae1a41473c420`.
- `harness/run_e3_measurements.py`: SHA256
  `7372f434561c7305c91904fe888f40a071b88591878b690d5305b6c6ba2c0ff4`.
- `protocol/prepare_e3_registries.py`: SHA256
  `64ddde2a04272c9feeef623a4882a4c6119ba886f379540495feec62f72d4553`.

All harness sources passed a static Python syntax parse before protocol sealing.
No scientific measurement command has been executed.

