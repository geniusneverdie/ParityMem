#!/usr/bin/env python3
"""Execute the sealed E3 symbolic latency and scalability study once."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys

import psutil
from transformers import AutoTokenizer

from e3_core import canonical, execute_pipeline


ROOT = Path("/data9/amx/fourth/paritymem")
E3 = ROOT / "experiments/icassp_e3_efficiency"
MODEL_PATHS = {
    "Qwen": ROOT.parent / "_models/huggingface/models--Qwen--Qwen3-14B/snapshots/40c069824f4251a91eefaf281ebe4c544efd3e18",
    "Llama": Path("/data5/hanwen/llm_file/Meta-Llama-3.1-8B-Instruct"),
    "Mistral": ROOT / "runs/paper_p2_r1/mistral_exact_snapshot",
}
TIMING_KEYS = ["T_parse_or_load_ns", "T_contractir_ns", "T_p0_p3_ns", "T_pairing_ns", "T_history_closure_ns", "T_first_divergence_ns", "T_total_ns"]
ZERO = {"llm_model": 0, "sglang": 0, "vllm": 0, "transformers_generation": 0, "benchmark_environment": 0}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_protocol() -> None:
    manifest = E3 / "manifests/E3_PROTOCOL_MANIFEST.sha256"
    proc = subprocess.run(["sha256sum", "-c", str(manifest)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise RuntimeError(f"E3_PROTOCOL_MANIFEST_FAIL:{proc.stderr[-1000:]}")


def stats(values: list[int | float]) -> dict[str, float]:
    ordered = sorted(values)
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive")
    twentieths = statistics.quantiles(ordered, n=20, method="inclusive")
    return {"median": statistics.median(ordered), "p95": twentieths[18], "iqr": quartiles[2] - quartiles[0], "minimum": ordered[0], "maximum": ordered[-1]}


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for position in range(start, end):
            result[order[position]] = rank
        start = end
    return result


def pearson(xs: list[float], ys: list[float]) -> float | None:
    xbar, ybar = statistics.mean(xs), statistics.mean(ys)
    numerator = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys, strict=True))
    denominator = math.sqrt(sum((x - xbar) ** 2 for x in xs) * sum((y - ybar) ** 2 for y in ys))
    return numerator / denominator if denominator else None


def log_fit(xs: list[float], ys: list[float]) -> dict[str, float | None]:
    lx, ly = [math.log(value) for value in xs], [math.log(value) for value in ys]
    xbar, ybar = statistics.mean(lx), statistics.mean(ly)
    denom = sum((x - xbar) ** 2 for x in lx)
    if not denom:
        return {"log_log_slope": None, "intercept": None, "r_squared": None}
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(lx, ly, strict=True)) / denom
    intercept = ybar - slope * xbar
    predicted = [intercept + slope * x for x in lx]
    total = sum((y - ybar) ** 2 for y in ly)
    residual = sum((y - pred) ** 2 for y, pred in zip(ly, predicted, strict=True))
    return {"log_log_slope": slope, "intercept": intercept, "r_squared": 1 - residual / total if total else 1.0}


def resource_gate(config: dict) -> dict:
    logical = psutil.cpu_count(logical=True) or 1
    load = os.getloadavg()
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_samples = [psutil.cpu_percent(interval=1.0), psutil.cpu_percent(interval=1.0)]
    others = []
    for process in psutil.process_iter(["pid", "username", "name", "cmdline", "memory_info"]):
        try:
            cmd = " ".join(process.info.get("cmdline") or [])
            if process.pid != os.getpid() and "run_e3_measurements.py" in cmd:
                others.append(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rules = config["resource_stability_gate"]
    checks = {
        "load_per_logical_cpu": load[0] / logical <= rules["max_load1_per_logical_cpu"],
        "available_ram_bytes": memory.available >= rules["min_available_ram_bytes"],
        "swap_used_bytes": swap.used <= rules["max_swap_used_bytes"],
        "cpu_utilization": max(cpu_samples) <= rules["max_cpu_utilization_percent"],
        "no_concurrent_e3": not others,
        "affinity": sorted(os.sched_getaffinity(0)) == config["cpu_affinity"],
    }
    return {"captured_at_utc": now(), "load_average": load, "logical_cpus": logical, "load1_per_cpu": load[0] / logical,
            "available_ram_bytes": memory.available, "swap_used_bytes": swap.used, "cpu_utilization_samples": cpu_samples,
            "concurrent_e3_pids": others, "checks": checks, "status": "PASS" if all(checks.values()) else "SAFE_RESOURCE_PAUSE"}


def base_record(row: dict, measurement_type: str, repeat: int) -> dict:
    return {
        "run_id": f"{measurement_type}::{row['input_id']}::R{repeat:04d}", "input_id": row["input_id"], "input_sha256": row["input_sha256"],
        "measurement_type": measurement_type, "repeat_index": repeat, "process_id": os.getpid(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)), "history_turns": row["history_turns"], "message_count": row["message_count"],
        "tool_call_count": row["tool_call_count"], "tool_result_count": row["tool_result_count"],
        "serialized_bytes": row["serialized_bytes"], "contractir_nodes": row["contractir_nodes"], "contractir_edges": row["contractir_edges"],
        "final_verdict": None, "expected_frozen_verdict": row["expected_frozen_verdict"], "status": "NOT_STARTED", "error_class": None,
        "RSS_BASELINE": None, "RSS_PEAK": None, "RSS_DELTA": None, "PY_ALLOC_PEAK": None,
        **{key: None for key in TIMING_KEYS}, "call_counts": ZERO,
    }


def run_latency(rows: list[dict], tokenizer_cache: dict, raw_path: Path, warmups: int, repeats: int, measurement_type: str) -> tuple[list[dict], int]:
    records: list[dict] = []
    mismatches = 0
    with raw_path.open("x", encoding="utf-8") as handle:
        for index, row in enumerate(rows):
            payload = json.loads(row["payload_json"])
            tokenizer = tokenizer_cache[payload["model_family"]]
            for warmup in range(warmups):
                result, _ = execute_pipeline(row["payload_json"], tokenizer)
                if result["verdict"] != row["expected_frozen_verdict"]:
                    raise RuntimeError(f"E3_HARNESS_SEMANTIC_MISMATCH:WARMUP:{row['input_id']}:{warmup}:{result['verdict']}:{row['expected_frozen_verdict']}")
            for repeat in range(repeats):
                record = base_record(row, measurement_type, repeat)
                process = psutil.Process()
                rss_before = process.memory_info().rss
                try:
                    result, timing = execute_pipeline(row["payload_json"], tokenizer)
                    rss_after = process.memory_info().rss
                    record.update(timing)
                    record.update({"contractir_nodes": result["contractir_nodes"], "contractir_edges": result["contractir_edges"],
                                   "final_verdict": result["verdict"], "RSS_BASELINE": rss_before,
                                   "RSS_PEAK": max(rss_before, rss_after), "RSS_DELTA": max(0, rss_after - rss_before),
                                   "status": "PASS" if result["verdict"] == row["expected_frozen_verdict"] else "E3_HARNESS_SEMANTIC_MISMATCH"})
                    if result["contractir_nodes"] != row["contractir_nodes"] or result["contractir_edges"] != row["contractir_edges"]:
                        record["status"] = "E3_HARNESS_SEMANTIC_MISMATCH"
                        record["error_class"] = "COMPLEXITY_METADATA_CHANGED"
                    mismatches += int(record["status"] != "PASS")
                except Exception as exc:
                    record.update({"status": "FAILED", "error_class": f"{type(exc).__name__}:{exc}"})
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"); handle.flush(); os.fsync(handle.fileno())
                    raise
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                records.append(record)
                if record["status"] != "PASS":
                    handle.flush(); os.fsync(handle.fileno())
                    raise RuntimeError(f"E3_HARNESS_SEMANTIC_MISMATCH:{row['input_id']}:{repeat}")
            handle.flush(); os.fsync(handle.fileno())
            print(json.dumps({"phase": measurement_type, "input_index": index + 1, "inputs": len(rows), "input_id": row["input_id"], "records": len(records), "mismatches": mismatches}, sort_keys=True), flush=True)
    return records, mismatches


def append_memory(registry_path: Path, rows: list[dict], raw_path: Path, repeats: int, measurement_type: str) -> list[dict]:
    worker = E3 / "harness/e3_memory_worker.py"
    records = []
    with raw_path.open("a", encoding="utf-8") as handle:
        for index, row in enumerate(rows):
            proc = subprocess.run([sys.executable, str(worker), "--registry", str(registry_path), "--input-id", row["input_id"], "--repeats", str(repeats)],
                                  cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800)
            if proc.returncode:
                raise RuntimeError(f"MEMORY_WORKER_FAIL:{row['input_id']}:{proc.stderr[-1000:]}")
            memory = json.loads(proc.stdout.strip().splitlines()[-1])
            record = base_record(row, measurement_type, 0)
            record.update(memory)
            record["measurement_type"] = measurement_type
            record["run_id"] = f"{measurement_type}::{row['input_id']}"
            record["error_class"] = None
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            records.append(record)
            print(json.dumps({"phase": measurement_type, "input_index": index + 1, "inputs": len(rows), "input_id": row["input_id"], "rss_delta": record["RSS_DELTA"]}, sort_keys=True), flush=True)
        handle.flush(); os.fsync(handle.fileno())
    return records


def bucket(value: int, rule: dict) -> str:
    if rule["mode"] == "SINGLE_OBSERVED_BUCKET":
        return f"observed<={rule['short_max']}"
    if value <= rule["short_max"]:
        return f"short<={rule['short_max']}"
    if value <= rule["medium_max"]:
        return f"medium<={rule['medium_max']}"
    return f"long>{rule['medium_max']}"


def tool_bucket(value: int) -> str:
    return "0-1" if value <= 1 else "2" if value == 2 else "3-4" if value <= 4 else ">=5"


def summarize_real(records: list[dict], rows: list[dict], full_registry: dict, mismatches: int, raw_path: Path) -> dict:
    metadata = {row["input_id"]: row for row in rows}
    timings = [record for record in records if record["measurement_type"] == "REAL_TRACE_LATENCY"]
    endpoint = {key: stats([record[key] for record in timings]) for key in TIMING_KEYS}
    strata: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for record in timings:
        row = metadata[record["input_id"]]
        labels = {
            "verdict": row["expected_frozen_verdict"],
            "history_turns": bucket(row["history_turns"], full_registry["bucket_rules"]["history_turns"]),
            "tool_calls": tool_bucket(row["tool_call_count"]),
            "contractir_nodes": bucket(row["contractir_nodes"], full_registry["bucket_rules"]["contractir_nodes"]),
        }
        for dimension, label in labels.items():
            strata[dimension][label].append(record["T_total_ns"])
    return {"schema_version": "paritymem.icassp_e3.real_summary.v1", "generated_at_utc": now(),
            "real_trace_decisions": len(rows), "timed_records": len(timings), "warmup_repeats": 20, "timed_repeats": 100,
            "timed_decision_mismatches": mismatches, "endpoints_ns": endpoint,
            "stratified_T_total_ns": {dimension: {label: {"n": len(values), **stats(values)} for label, values in labels.items()} for dimension, labels in strata.items()},
            "raw_sha256": stable_file(raw_path), "call_counts": ZERO}


def summarize_memory(real_memory: list[dict], scale_memory: list[dict]) -> dict:
    return {"schema_version": "paritymem.icassp_e3.memory_summary.v1", "generated_at_utc": now(),
            "rss_method": "fresh-process repeated-decision batch with 1 ms psutil RSS sampling after tokenizer load",
            "tracemalloc_boundary": "Python allocations only; excludes native allocations",
            "real_trace_batches": len(real_memory), "real_batch_repeats": 100,
            "real_RSS_DELTA_bytes": stats([row["RSS_DELTA"] for row in real_memory]),
            "real_PY_ALLOC_PEAK_bytes": stats([row["PY_ALLOC_PEAK"] for row in real_memory]),
            "scaling_batches": len(scale_memory), "scaling_batch_repeats": 200,
            "scaling_RSS_DELTA_bytes": stats([row["RSS_DELTA"] for row in scale_memory]),
            "scaling_PY_ALLOC_PEAK_bytes": stats([row["PY_ALLOC_PEAK"] for row in scale_memory]),
            "call_counts": ZERO}


def summarize_scaling(records: list[dict], rows: list[dict], raw_path: Path) -> dict:
    latency = [record for record in records if record["measurement_type"] == "SCALING_LATENCY"]
    metadata = {row["input_id"]: row for row in rows}
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for record in latency:
        row = metadata[record["input_id"]]
        groups[(row["measurement_axis"], row["axis_value"])].append(record)
    points = []
    for (axis, value), subset in sorted(groups.items()):
        row = metadata[subset[0]["input_id"]]
        points.append({"measurement_axis": axis, "axis_value": value, "input_id": row["input_id"],
                       "history_turns": row["history_turns"], "tool_call_count": row["tool_call_count"],
                       "contractir_nodes": row["contractir_nodes"], "contractir_edges": row["contractir_edges"],
                       "serialized_bytes": row["serialized_bytes"],
                       "endpoints_ns": {key: stats([record[key] for record in subset]) for key in TIMING_KEYS}})
    analyses = {}
    for axis in ["TOOL_CALL_COUNT", "HISTORY_TURNS"]:
        subset = [point for point in points if point["measurement_axis"] == axis]
        xs = [float(point["axis_value"]) for point in subset]
        ys = [float(point["endpoints_ns"]["T_total_ns"]["median"]) for point in subset]
        nodes = [float(point["contractir_nodes"]) for point in subset]
        analyses[axis] = {"spearman_axis_vs_T_total": pearson(ranks(xs), ranks(ys)),
                          "log_log_axis_vs_T_total": log_fit(xs, ys),
                          "spearman_nodes_vs_T_total": pearson(ranks(nodes), ranks(ys)),
                          "log_log_nodes_vs_T_total": log_fit(nodes, ys)}
    return {"schema_version": "paritymem.icassp_e3.scalability_summary.v1", "generated_at_utc": now(),
            "SCALABILITY_ONLY_SYNTHETIC": True, "semantic_accuracy_denominator": False,
            "points": points, "predeclared_descriptive_analyses": analyses, "raw_sha256": stable_file(raw_path), "call_counts": ZERO}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-sealed", action="store_true")
    args = parser.parse_args()
    if not args.execute_sealed:
        raise SystemExit("--execute-sealed required")
    verify_protocol()
    config = json.loads((E3 / "protocol/E3_MEASUREMENT_CONFIG.json").read_text())
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("CUDA_VISIBLE_DEVICES") not in {"", None}:
        raise RuntimeError("SEALED_ENVIRONMENT_MISMATCH")
    required_affinity = set(config["cpu_affinity"])
    if set(os.sched_getaffinity(0)) != required_affinity:
        raise RuntimeError(f"CPU_AFFINITY_MISMATCH:{sorted(os.sched_getaffinity(0))}:{sorted(required_affinity)}")
    raw_real = E3 / "raw/E3_REAL_TRACE_TIMINGS.jsonl"
    raw_scale = E3 / "raw/E3_SCALING_TIMINGS.jsonl"
    outputs = [raw_real, raw_scale, E3 / "analysis/E3_REAL_TRACE_SUMMARY.json", E3 / "analysis/E3_SCALABILITY_SUMMARY.json",
               E3 / "analysis/E3_MEMORY_SUMMARY.json", E3 / "analysis/E3_OPTIONAL_INFERENCE_RATIO.json"]
    if any(path.exists() for path in outputs):
        raise RuntimeError("EXACTLY_ONCE_OUTPUT_COLLISION")
    gate = resource_gate(config)
    (E3 / "raw/E3_RESOURCE_GATE.json").write_bytes(json.dumps(gate, sort_keys=True, indent=2).encode() + b"\n")
    if gate["status"] != "PASS":
        print(json.dumps({"status": "SAFE_RESOURCE_PAUSE", "checks": gate["checks"]}, sort_keys=True))
        raise SystemExit(2)

    real_doc = json.loads((E3 / "registries/E3_TIMED_REAL_SUBSET.json").read_text())
    full_doc = json.loads((E3 / "protocol/E3_REAL_TRACE_REGISTRY.json").read_text())
    memory_doc = json.loads((E3 / "registries/E3_MEMORY_SUBSET.json").read_text())
    scale_doc = json.loads((E3 / "protocol/E3_SCALING_REGISTRY.json").read_text())
    tokenizers = {family: AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False) for family, path in MODEL_PATHS.items()}
    real_latency, mismatch_real = run_latency(real_doc["rows"], tokenizers, raw_real, 20, 100, "REAL_TRACE_LATENCY")
    real_memory = append_memory(E3 / "registries/E3_MEMORY_SUBSET.json", memory_doc["rows"], raw_real, 100, "REAL_TRACE_MEMORY_BATCH")
    scale_latency, mismatch_scale = run_latency(scale_doc["rows"], tokenizers, raw_scale, 20, 200, "SCALING_LATENCY")
    scale_memory = append_memory(E3 / "protocol/E3_SCALING_REGISTRY.json", scale_doc["rows"], raw_scale, 200, "SCALING_MEMORY_BATCH")
    mismatches = mismatch_real + mismatch_scale + sum(row["timed_decision_mismatches"] for row in real_memory + scale_memory)
    if mismatches:
        raise RuntimeError(f"E3_HARNESS_SEMANTIC_MISMATCH:{mismatches}")

    real_summary = summarize_real(real_latency, real_doc["rows"], full_doc, mismatch_real, raw_real)
    scale_summary = summarize_scaling(scale_latency, scale_doc["rows"], raw_scale)
    memory_summary = summarize_memory(real_memory, scale_memory)
    ratio = {"schema_version": "paritymem.icassp_e3.inference_ratio.v1", "generated_at_utc": now(),
             "status": "NOT_AVAILABLE", "reason": "Frozen E1/E2 logs contain duration fields but not an unambiguous explicit request-start plus completion pair for every eligible call; no model call authorized.",
             "INFERENCE_COST_RATIO": "NOT_AVAILABLE", "call_counts": ZERO}
    for path, value in [(outputs[2], real_summary), (outputs[3], scale_summary), (outputs[4], memory_summary), (outputs[5], ratio)]:
        path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n")
    print(json.dumps({"status": "E3_SCIENTIFIC_TIMING_COMPLETE", "real_decisions": len(real_doc["rows"]),
                      "real_timed_records": len(real_latency), "scaling_points": len(scale_doc["rows"]),
                      "scaling_timed_records": len(scale_latency), "timed_decision_mismatches": mismatches,
                      "T_total_median_ns": real_summary["endpoints_ns"]["T_total_ns"]["median"],
                      "T_total_p95_ns": real_summary["endpoints_ns"]["T_total_ns"]["p95"], "call_counts": ZERO}, sort_keys=True))


if __name__ == "__main__":
    main()

