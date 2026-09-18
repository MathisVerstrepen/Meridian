#!/usr/bin/env python3
"""Bounded, local-only min/max comparison using committed representative Dockerfiles."""

import argparse
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = Path("/tmp/opencode")
BUILD_TIMEOUT = 900
TOTAL_BUDGET = 3600
IMAGES = {"frontend": "docker/ui.Dockerfile", "sandbox-python": "docker/sandbox-python.Dockerfile"}
SOURCE_PATHS = (
    ".dockerignore",
    *IMAGES.values(),
    "ui",
    "docs/changelogs",
    "sandbox_manager/sandbox-requirements.txt",
    "sandbox_manager/worker",
)
FRONTEND_MARKER = '<script lang="ts" setup>'
EXPENSIVE = re.compile(
    r"\bRUN\b.*(?:apt-get|pnpm install|pnpm run build|git clone|\bmake\b|"
    r"pip install|nltk\.downloader|matplotlib\.pyplot)"
)


class BenchmarkError(RuntimeError):
    pass


class Budget:
    def __init__(self):
        self.deadline = time.monotonic() + TOTAL_BUDGET

    def remaining(self, limit):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise BenchmarkError("Total 3600-second budget exhausted")
        return min(limit, remaining)


def capture(command, budget, cwd=ROOT):
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=budget.remaining(60),
    )
    return result.stdout.strip()


def snapshot(root, destination, budget):
    """Archive only tracked HEAD inputs, never copy a developer working tree."""
    dirty = capture(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *SOURCE_PATHS,
            "docker/*.dockerignore",
        ],
        budget,
        root,
    )
    if dirty:
        raise BenchmarkError(f"Representative build inputs must be clean:\n{dirty}")
    # A Dockerfile-specific ignore overrides the root rules; do not silently omit one.
    overrides = capture(["git", "ls-files", "--", "docker/*.dockerignore"], budget, root)
    if overrides:
        raise BenchmarkError("Dockerfile-specific ignore files require updating snapshot inputs")
    commit = capture(["git", "rev-parse", "HEAD"], budget, root)
    archive = destination.parent / "source.tar"
    capture(
        ["git", "archive", "--format=tar", f"--output={archive}", commit, "--", *SOURCE_PATHS],
        budget,
        root,
    )
    destination.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")
    archive.unlink()
    return commit


def change_context(context, image):
    if image == "frontend":
        target = context / "ui/app/app.vue"
        original = target.read_text()
        if original.count(FRONTEND_MARKER) != 1:
            raise BenchmarkError("Frontend script fixture changed; update benchmark marker")
        changed = original.replace(
            FRONTEND_MARKER, FRONTEND_MARKER + "\n// Docker cache benchmark release fixture.", 1
        )
    else:
        target = context / "sandbox_manager/worker/bootstrap.py"
        original = target.read_text()
        changed = original + "\n# Docker cache benchmark release fixture.\n"
    target.write_text(changed)
    return target, original


def build_command(builder, context, image, mode, probe, cache):
    command = [
        "docker",
        "buildx",
        "build",
        "--builder",
        builder,
        "--progress=plain",
        "--file",
        str(context / IMAGES[image]),
        "--output=type=cacheonly",
    ]
    if image == "frontend":
        version = "0.0.1-beta" if probe == "changed" else "0.0.0-beta"
        command += ["--build-arg", f"NUXT_PUBLIC_VERSION={version}"]
    if probe == "cold":
        command += ["--no-cache", "--cache-to", f"type=local,dest={cache},mode={mode}"]
    else:
        command += ["--cache-from", f"type=local,src={cache}"]
    return command + [str(context)]


def log_metrics(text):
    """Missing/incomplete BuildKit observations stay unknown, never assumed zero."""
    steps = {}
    export_id = None
    export_seconds = None
    for line in text.splitlines():
        match = re.match(r"^(#\d+) (.*)$", line)
        if not match:
            continue
        step_id, detail = match.groups()
        if "exporting cache to client" in detail:
            export_id = step_id
        if detail.startswith("[") and EXPENSIVE.search(detail):
            steps[step_id] = {"step": detail, "status": "unknown"}
        if step_id in steps:
            if detail == "CACHED":
                steps[step_id]["status"] = "cached"
            elif detail.startswith("DONE"):
                steps[step_id]["status"] = "executed"
        duration = re.fullmatch(r"DONE ([\d.]+)s", detail)
        if step_id == export_id and duration:
            export_seconds = float(duration[1])
    return export_seconds, list(steps.values())


def blob_bytes(cache):
    if not (cache / "index.json").is_file():
        return None
    blobs = {path.name: path for path in (cache / "blobs/sha256").glob("*") if path.is_file()}
    return sum(path.stat().st_size for path in blobs.values()) if blobs else None


def measured_build(command, budget, log_path):
    started = time.monotonic()
    status = "not-started"
    try:
        with log_path.open("w") as log:
            timeout = budget.remaining(BUILD_TIMEOUT)
            status = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            ).returncode
    except subprocess.TimeoutExpired:
        status = "timeout"
    except KeyboardInterrupt:
        status = "interrupted"
    finally:
        text = log_path.read_text(errors="replace") if log_path.exists() else ""
        print(text, end="" if text.endswith("\n") else "\n", flush=True)
    return time.monotonic() - started, status, text


def run_probe(context, workspace, image, mode, probe, budget, rows):
    builder = "meridian-cache-bench-" + uuid.uuid4().hex
    cache = workspace / f"{image}-{mode}"
    if probe == "cold" and cache.exists():
        raise BenchmarkError(f"Cold export destination must be absent: {cache}")
    command = build_command(builder, context, image, mode, probe, cache)
    cleanup_error = None
    try:
        # Record ownership before create, so even an interrupted partial create is removed.
        print(
            capture(
                ["docker", "buildx", "create", "--name", builder, "--driver", "docker-container"],
                budget,
            )
        )
        print(capture(["docker", "buildx", "inspect", "--builder", builder, "--bootstrap"], budget))
        print(f"\nBUILD image={image} mode={mode} probe={probe} builder={builder}", flush=True)
        elapsed, status, text = measured_build(command, budget, workspace / "build.log")
        export_seconds, expensive = log_metrics(text)
        rows.append(
            {
                "image": image,
                "mode": mode,
                "probe": probe,
                "elapsed_s": round(elapsed, 3),
                "export_s": export_seconds,
                "blob_bytes": blob_bytes(cache),
                "expensive": expensive,
                "exit": status,
            }
        )
        if status != 0:
            raise BenchmarkError(f"Build stopped: {image}/{mode}/{probe}, exit={status}")
    finally:
        # Cleanup has its own small bound, even when the measurement budget is exhausted.
        try:
            subprocess.run(["docker", "buildx", "rm", "--force", builder], check=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            cleanup_error = error
        if cleanup_error is not None:
            raise BenchmarkError(f"Owned builder cleanup failed ({builder}): {cleanup_error}")


def compare(context, workspace, budget, rows):
    for image in IMAGES:
        for mode in ("min", "max"):
            run_probe(context, workspace, image, mode, "cold", budget, rows)
            run_probe(context, workspace, image, mode, "unchanged", budget, rows)
            target, original = change_context(context, image)
            try:
                run_probe(context, workspace, image, mode, "changed", budget, rows)
            finally:
                target.write_text(original)


def print_summary(rows):
    print("\nimage\tmode\tprobe\telapsed_s\texport_s\texported_blob_bytes\texit")
    for row in rows:
        print(
            "\t".join(
                str(row[key]) if row[key] is not None else "unknown/not-applicable"
                for key in ("image", "mode", "probe", "elapsed_s", "export_s", "blob_bytes", "exit")
            )
        )
        if not row["expensive"]:
            print("  expensive steps: unknown (no identifiable step headers)")
        for step in row["expensive"]:
            print(f"  {step['status']}: {step['step']}")
    print(f"Measured builds: {len(rows)}/12; one sample per case, no statistical significance.")
    print("Blob bytes describe each mode's cold export, reused unchanged by both import probes.")
    print(
        "Confounders: early frontend version ARG invalidation; mutable base images/nsjail inputs."
    )
    print(
        "Local disk exports do not predict GHCR transfers, runner contention or five-way speedup."
    )
    print(
        "No min/max conclusions for backend, browser-service or sandbox-manager. "
        "Retain trusted max."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Runs 12 sequential local builds: frontend and sandbox-python, min/max, "
            "cold export then fresh-builder unchanged/changed imports. Requires Docker/Buildx "
            "and clean committed representative inputs. Uses /tmp/opencode; 900s/build, "
            "3600s total plus bounded cleanup. No push, registry caches or login."
        ),
    )
    parser.parse_args(argv)
    budget = Budget()
    rows = []
    try:
        if not TEMP_ROOT.is_dir():
            raise BenchmarkError(f"Required temporary parent does not exist: {TEMP_ROOT}")
        with tempfile.TemporaryDirectory(prefix="meridian-cache-bench-", dir=TEMP_ROOT) as temp:
            workspace = Path(temp)
            context = workspace / "context"
            commit = snapshot(ROOT, context, budget)
            print(f"Source commit: {commit}\nHost: {platform.platform()} ({platform.machine()})")
            print(capture(["docker", "version"], budget))
            print(capture(["docker", "buildx", "version"], budget))
            print("BuildKit versions/platforms follow from each fresh builder's inspect output.")
            compare(context, workspace, budget, rows)
        return 0
    except (BenchmarkError, OSError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"Benchmark stopped: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stdout:
            print(error.stdout, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Benchmark interrupted", file=sys.stderr)
        return 130
    finally:
        print_summary(rows)


if __name__ == "__main__":
    sys.exit(main())
