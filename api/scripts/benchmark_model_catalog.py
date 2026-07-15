#!/usr/bin/env python3
import gzip
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(API_ROOT / "app"))
sys.path.insert(0, str(API_ROOT / "tests" / "fixtures"))

from model_catalog import build_representative_model_catalog  # noqa: E402
from services.model_catalog import encode_model_catalog  # noqa: E402

WARMUP_ITERATIONS = 10
ITERATIONS_PER_SAMPLE = 50
SAMPLE_COUNT = 5


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _measure(operation: Callable[[], bytes]) -> float:
    started = time.perf_counter_ns()
    for _ in range(ITERATIONS_PER_SAMPLE):
        operation()
    elapsed_ns = time.perf_counter_ns() - started
    return elapsed_ns / ITERATIONS_PER_SAMPLE / 1_000_000


def main() -> None:
    catalog = build_representative_model_catalog()

    def serialize_baseline() -> bytes:
        return _json_bytes(catalog.model_dump(mode="json"))

    def encode_and_serialize_compact() -> bytes:
        compact = encode_model_catalog(catalog)
        return _json_bytes(
            compact.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        )

    baseline_payload = serialize_baseline()
    compact_payload = encode_and_serialize_compact()
    baseline_gzip = gzip.compress(baseline_payload, compresslevel=6, mtime=0)
    compact_gzip = gzip.compress(compact_payload, compresslevel=6, mtime=0)

    for _ in range(WARMUP_ITERATIONS):
        serialize_baseline()
        encode_and_serialize_compact()

    baseline_samples: list[float] = []
    compact_samples: list[float] = []
    for sample_index in range(SAMPLE_COUNT):
        operations = (
            (serialize_baseline, baseline_samples),
            (encode_and_serialize_compact, compact_samples),
        )
        if sample_index % 2:
            operations = tuple(reversed(operations))
        for operation, samples in operations:
            samples.append(_measure(operation))

    baseline_ms = statistics.median(baseline_samples)
    compact_ms = statistics.median(compact_samples)
    raw_reduction = 100 * (1 - len(compact_payload) / len(baseline_payload))
    gzip_reduction = 100 * (1 - len(compact_gzip) / len(baseline_gzip))
    allowed_delta_ms = max(2.0, 0.20 * baseline_ms)

    print(f"models: {len(catalog.data)}")
    print(f"runtime: Python {platform.python_version()} ({platform.platform()})")
    print(f"B_raw: {len(baseline_payload)} bytes")
    print(f"C_raw: {len(compact_payload)} bytes ({raw_reduction:.2f}% smaller)")
    print(f"B_gzip: {len(baseline_gzip)} bytes")
    print(f"C_gzip: {len(compact_gzip)} bytes ({gzip_reduction:.2f}% smaller)")
    print(f"B_backend_ms: {baseline_ms:.3f}")
    print(f"C_backend_ms: {compact_ms:.3f}")
    print(f"backend_delta_ms: {compact_ms - baseline_ms:.3f} (allowed {allowed_delta_ms:.3f})")

    failures = []
    if len(compact_payload) > 0.60 * len(baseline_payload):
        failures.append("compact raw JSON is not at least 40% smaller")
    if len(compact_gzip) > len(baseline_gzip):
        failures.append("compact gzip size regressed")
    if compact_ms - baseline_ms > allowed_delta_ms:
        failures.append("compact backend timing exceeded the allowed delta")
    if failures:
        raise SystemExit("benchmark failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
