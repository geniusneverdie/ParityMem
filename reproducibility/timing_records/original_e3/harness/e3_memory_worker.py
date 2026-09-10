#!/usr/bin/env python3
"""Fresh-process RSS/tracemalloc batch for one frozen E3 input."""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import threading
import time
import tracemalloc

import psutil
from transformers import AutoTokenizer

from e3_core import execute_pipeline


ROOT = Path("/data9/amx/fourth/paritymem")
MODEL_PATHS = {
    "Qwen": ROOT.parent / "_models/huggingface/models--Qwen--Qwen3-14B/snapshots/40c069824f4251a91eefaf281ebe4c544efd3e18",
    "Llama": Path("/data5/hanwen/llm_file/Meta-Llama-3.1-8B-Instruct"),
    "Mistral": ROOT / "runs/paper_p2_r1/mistral_exact_snapshot",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--input-id", required=True)
    parser.add_argument("--repeats", type=int, required=True)
    args = parser.parse_args()
    document = json.loads(Path(args.registry).read_text())
    row = next(item for item in document["rows"] if item["input_id"] == args.input_id)
    payload = json.loads(row["payload_json"])
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATHS[payload["model_family"]], local_files_only=True, trust_remote_code=False)
    gc.collect()
    process = psutil.Process()
    baseline = process.memory_info().rss
    samples = [baseline]
    stop = threading.Event()

    def monitor() -> None:
        while not stop.is_set():
            try:
                samples.append(process.memory_info().rss)
            except psutil.Error:
                pass
            time.sleep(0.001)

    thread = threading.Thread(target=monitor, daemon=True)
    tracemalloc.start()
    tracemalloc.reset_peak()
    thread.start()
    mismatch = 0
    first = None
    try:
        for _ in range(args.repeats):
            result, _ = execute_pipeline(row["payload_json"], tokenizer)
            first = first or result
            mismatch += int(result["verdict"] != row["expected_frozen_verdict"])
    finally:
        stop.set()
        thread.join(timeout=2)
    py_current, py_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    samples.append(process.memory_info().rss)
    peak = max(samples)
    output = {
        "input_id": row["input_id"], "input_sha256": row["input_sha256"], "repeats": args.repeats,
        "process_id": os.getpid(), "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "RSS_BASELINE": baseline, "RSS_PEAK": peak, "RSS_DELTA": max(0, peak - baseline),
        "PY_ALLOC_CURRENT": py_current, "PY_ALLOC_PEAK": py_peak,
        "rss_sample_interval_seconds": 0.001, "rss_samples": len(samples),
        "final_verdict": first["verdict"] if first else None,
        "expected_frozen_verdict": row["expected_frozen_verdict"],
        "timed_decision_mismatches": mismatch, "status": "PASS" if mismatch == 0 else "E3_HARNESS_SEMANTIC_MISMATCH",
        "call_counts": {"llm_model": 0, "sglang": 0, "vllm": 0, "transformers_generation": 0, "benchmark_environment": 0},
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    if mismatch:
        raise SystemExit(3)


if __name__ == "__main__":
    main()

