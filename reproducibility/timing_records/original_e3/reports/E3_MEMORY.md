# E3 Memory Overhead

Twelve frozen representative real inputs were measured in fresh processes.
After tokenizer loading, each process executed a 100-decision batch while RSS
was sampled every 1 ms. The values therefore describe peak incremental RSS for
the repeated-decision batch, not byte-precise allocation by one call.

| Endpoint | Median | p95 | Range |
|---|---:|---:|---:|
| RSS delta | 393,216 B (384 KiB) | 963,379 B (940.8 KiB) | 0–1,179,648 B |
| Python allocation peak | 1,255,345 B | 1,656,247 B | 1,093,727–1,681,122 B |

`tracemalloc` covers Python allocations only and does not capture native
allocations. Per-call boundary RSS fields are retained in raw latency records,
but the fresh-process batch is the primary memory endpoint.

Scaling-memory batches were not reached before the history-axis semantic
mismatch and are `NOT_AVAILABLE`.

Classification: `MAIN_TEXT_SUPPORTING` with the batch-measurement boundary.

