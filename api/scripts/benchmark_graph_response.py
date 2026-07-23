#!/usr/bin/env python3
import gc
import gzip
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Callable

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(API_ROOT / "app"))
sys.path.insert(0, str(API_ROOT / "tests" / "fixtures"))

from database.pg.graph_ops.graph_crud import CompleteGraph  # noqa: E402
from graph_response import build_large_graph_fixture, build_small_graph_fixture  # noqa: E402
from services.graph_response import encode_graph_editor_response  # noqa: E402

WARMUP_ITERATIONS = 5
ITERATIONS_PER_SAMPLE = 5
SAMPLE_COUNT = 5


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _measure(operation: Callable[[], bytes]) -> float:
    started = time.perf_counter_ns()
    for _ in range(ITERATIONS_PER_SAMPLE):
        operation()
    elapsed_ns = time.perf_counter_ns() - started
    return elapsed_ns / ITERATIONS_PER_SAMPLE / 1_000_000


def _measure_peak(operation: Callable[[], bytes]) -> int:
    gc.collect()
    tracemalloc.start()
    payload = operation()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if not payload:
        raise AssertionError("benchmark operation returned an empty payload")
    return peak


def _reply_utf8_bytes(complete_graph: CompleteGraph) -> int:
    total = 0
    for node in complete_graph.nodes:
        if isinstance(node.data, dict):
            reply = node.data.get("reply")
            if isinstance(reply, str):
                total += len(reply.encode("utf-8"))
    return total


def _benchmark_fixture(name: str, complete_graph: CompleteGraph) -> list[str]:
    def serialize_baseline() -> bytes:
        return _json_bytes(complete_graph.model_dump(mode="json"))

    def encode_and_serialize_v1() -> bytes:
        encoded = encode_graph_editor_response(complete_graph)
        return _json_bytes(
            encoded.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        )

    baseline_payload = serialize_baseline()
    v1_payload = encode_and_serialize_v1()
    baseline_gzip = {
        level: gzip.compress(baseline_payload, compresslevel=level, mtime=0) for level in (1, 6)
    }
    v1_gzip = {level: gzip.compress(v1_payload, compresslevel=level, mtime=0) for level in (1, 6)}

    for _ in range(WARMUP_ITERATIONS):
        serialize_baseline()
        encode_and_serialize_v1()

    baseline_samples: list[float] = []
    v1_samples: list[float] = []
    for sample_index in range(SAMPLE_COUNT):
        operations = (
            (serialize_baseline, baseline_samples),
            (encode_and_serialize_v1, v1_samples),
        )
        if sample_index % 2:
            operations = tuple(reversed(operations))
        for operation, samples in operations:
            samples.append(_measure(operation))

    baseline_ms = statistics.median(baseline_samples)
    v1_ms = statistics.median(v1_samples)
    baseline_peak = _measure_peak(serialize_baseline)
    v1_peak = _measure_peak(encode_and_serialize_v1)
    allowed_delta_ms = max(5.0, 0.20 * baseline_ms)
    allowed_peak_delta = max(4 * 1024 * 1024, int(0.20 * baseline_peak))

    raw_reduction = 100 * (1 - len(v1_payload) / len(baseline_payload))
    print(f"[{name}]")
    print(
        f"nodes={len(complete_graph.nodes)} edges={len(complete_graph.edges)} "
        f"reply_utf8_bytes={_reply_utf8_bytes(complete_graph)}"
    )
    print(f"baseline_raw={len(baseline_payload)}")
    print(f"v1_raw={len(v1_payload)} reduction={raw_reduction:.2f}%")
    for level in (1, 6):
        reduction = 100 * (1 - len(v1_gzip[level]) / len(baseline_gzip[level]))
        print(f"baseline_gzip{level}={len(baseline_gzip[level])}")
        print(f"v1_gzip{level}={len(v1_gzip[level])} reduction={reduction:.2f}%")
    print(f"baseline_backend_ms={baseline_ms:.3f}")
    print(f"v1_backend_ms={v1_ms:.3f}")
    print(f"backend_delta_ms={v1_ms - baseline_ms:.3f} allowed={allowed_delta_ms:.3f}")
    print(f"baseline_peak_bytes={baseline_peak}")
    print(f"v1_peak_bytes={v1_peak}")
    print(f"peak_delta_bytes={v1_peak - baseline_peak} allowed={allowed_peak_delta}")

    failures = []
    raw_ratio_limit = 0.82 if name == "small" else 0.98
    if len(v1_payload) > raw_ratio_limit * len(baseline_payload):
        failures.append(f"{name} v1 raw JSON exceeded {raw_ratio_limit:.0%} of baseline")
    for level in (1, 6):
        if len(v1_gzip[level]) > len(baseline_gzip[level]):
            failures.append(f"{name} v1 gzip level {level} size regressed")
    if v1_ms - baseline_ms > allowed_delta_ms:
        failures.append(f"{name} v1 backend timing exceeded the allowed delta")
    if v1_peak - baseline_peak > allowed_peak_delta:
        failures.append(f"{name} v1 peak allocation exceeded the allowed delta")
    return failures


def main() -> None:
    print(f"runtime=Python {platform.python_version()} ({platform.platform()})")
    failures = []
    failures.extend(_benchmark_fixture("small", build_small_graph_fixture()))
    failures.extend(_benchmark_fixture("large", build_large_graph_fixture()))
    if failures:
        raise SystemExit("benchmark failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
