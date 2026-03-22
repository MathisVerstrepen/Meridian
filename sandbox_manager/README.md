# Meridian Sandbox Manager - Developer README

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-005571?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Docker](https://img.shields.io/badge/Docker-24+-2496ED?logo=docker&logoColor=white)](https://www.docker.com/) [![NSJail](https://img.shields.io/badge/NSJail-required-111827)](https://github.com/google/nsjail)

This folder contains the **sandbox execution service** for Meridian. It exposes a small FastAPI API that runs untrusted Python code inside isolated Docker worker containers, enforces execution limits, captures stdout/stderr, harvests generated files, and returns structured execution results back to the backend tool layer.

It is intentionally narrow in scope:

- only **Python** is supported
- the public API is just **`/health`** and **`/execute`**
- code runs inside a dedicated **worker image**
- generated files must be written to **`MERIDIAN_OUTPUT_DIR`** to be returned

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Recommended Local Workflow](#recommended-local-workflow)
  - [Run The Service Directly](#run-the-service-directly)
  - [Development Commands](#development-commands)
- [HTTP API](#http-api)
  - [`GET /health`](#get-health)
  - [`POST /execute`](#post-execute)
- [Core Concepts](#core-concepts)
  - [Execution Flow](#execution-flow)
  - [Worker Bootstrap](#worker-bootstrap)
  - [Artifact Flow](#artifact-flow)
  - [Concurrency & Limits](#concurrency--limits)
  - [Container Isolation](#container-isolation)
- [Runtime Modes](#runtime-modes)
  - [`nsjail`](#nsjail)
- [Environment Variables](#environment-variables)
- [Worker Image](#worker-image)
- [Integration With Meridian API](#integration-with-meridian-api)
- [Troubleshooting](#troubleshooting)
- [Building & Deployment](#building--deployment)

## Key Features

- **Isolated Python execution**: user/model-submitted Python runs in disposable Docker containers.
- **Runtime selection**: supports **`nsjail` only** for untrusted execution.
- **Bounded execution**: memory, CPU, PID, code-size, output-size, queue-wait, and timeout limits.
- **Artifact harvesting**: regular files written under `MERIDIAN_OUTPUT_DIR` are returned as structured artifacts.
- **Image/file chat support**: the backend persists returned artifacts and surfaces them in chat as inline images or download actions.
- **Operationally simple API**: one health endpoint and one execute endpoint.
- **Stale container cleanup**: leftover sandbox containers are removed on startup.
- **Debuggable failures**: streamed stderr is captured, Docker log fallback is used, and silent runtime failures get synthesized diagnostics where possible.

## Tech Stack

| Category | Technologies |
|----------|--------------|
| **Framework** | FastAPI |
| **Language** | Python 3.11 |
| **Container Control** | Docker SDK for Python |
| **Isolation** | Docker + NSJail layered isolation |
| **Validation** | Pydantic v2 / pydantic-settings |
| **Worker Libraries** | NumPy, SciPy, pandas, matplotlib, Plotly, scikit-learn, Pillow, OpenCV, NLTK, and more |
| **Dev Tools** | pytest, flake8, black, isort, mypy |

## Project Structure

```plaintext
sandbox_manager/
├── app/
│   ├── config.py          # Environment-driven settings
│   ├── executor.py        # Docker container creation, runtime logic, artifact harvest
│   ├── main.py            # FastAPI app, lifespan, /health and /execute
│   └── models.py          # Request/response DTOs
├── worker/
│   └── bootstrap.py       # Python bootstrap injected into worker containers
├── tests/
│   ├── conftest.py
│   └── test_main.py       # API, runtime, bootstrap, and executor tests
├── requirements.txt       # Sandbox manager runtime deps
├── requirements-dev.txt   # Lint/test/type deps
├── sandbox-requirements.txt # Python packages baked into worker image
└── pyproject.toml
```

Related Docker files live outside this folder:

- [sandbox-manager.Dockerfile](/home/mathis/Documents/Dev/Meridian/docker/sandbox-manager.Dockerfile)
- [sandbox-python.Dockerfile](/home/mathis/Documents/Dev/Meridian/docker/sandbox-python.Dockerfile)
- [docker-compose.yml](/home/mathis/Documents/Dev/Meridian/docker/docker-compose.yml)
- [docker-compose.prod.yml](/home/mathis/Documents/Dev/Meridian/docker/docker-compose.prod.yml)
- [run.sh](/home/mathis/Documents/Dev/Meridian/docker/run.sh)

## Quick Start

### Prerequisites

- Python **3.11+**
- Docker with access to the local daemon
- A built worker image
- If using Docker Compose: the `sandbox_manager` service must have access to `/var/run/docker.sock`

### Recommended Local Workflow

The simplest way to run the sandbox manager in development is through the repo Docker helper:

```bash
cd docker
./run.sh dev --sandbox-manager -d
```

That command:

- generates `docker/env/.env.local` from `docker/config.local.toml`
- builds the sandbox worker image
- starts the `sandbox_manager` container
- exposes the manager on `localhost:${SANDBOX_MANAGER_PORT}`

### Run The Service Directly

If you want to run the FastAPI app directly instead of through Compose:

```bash
cd sandbox_manager
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

In that mode you still need:

- Docker daemon access
- a valid `SANDBOX_WORKER_IMAGE`

### Development Commands

```bash
cd sandbox_manager

# Run tests
../api/venv/bin/pytest tests/test_main.py

# Lint
../api/venv/bin/flake8 .

# Optional syntax verification
python -m py_compile app/config.py app/executor.py app/main.py app/models.py worker/bootstrap.py
```

## HTTP API

### `GET /health`

Checks:

- Docker daemon availability
- worker image availability
- resolved runtime name

Example response:

```json
{
  "status": "ok",
  "worker_image": "meridian_sandbox_python:local",
  "runtime": "nsjail"
}
```

If the worker image is missing or Docker is unavailable, the endpoint returns `503`.

### `POST /execute`

Runs one Python snippet.

Request body:

```json
{
  "language": "python",
  "code": "print('hello')"
}
```

Response shape:

```json
{
  "execution_id": "6a15fc8aa61e4e2885620a44f47e576a",
  "status": "success",
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_ms": 346,
  "output_truncated": false,
  "artifacts": [
    {
      "relative_path": "hello.txt",
      "name": "hello.txt",
      "content_type": "text/plain",
      "size": 2,
      "content_b64": "b2s="
    }
  ],
  "artifact_warnings": []
}
```

Supported `status` values:

- `success`
- `runtime_error`
- `timeout`
- `memory_limit_exceeded`
- `output_limit_exceeded`

Error behavior:

- `400` if `language != python`
- `413` if the submitted code exceeds `SANDBOX_CODE_MAX_BYTES`
- `429` if the execution queue is full for longer than `SANDBOX_QUEUE_WAIT_SECONDS`
- `500` for internal sandbox failures

## Core Concepts

### Execution Flow

1. Meridian backend calls `POST /execute`.
2. Sandbox manager validates language and code size.
3. A semaphore limits concurrent runs.
4. `SandboxExecutor` creates a disposable worker container.
5. The worker receives the submitted code as base64 in `SANDBOX_CODE_B64`.
6. The bootstrap decodes the payload into `/tmp/execution.py` and executes it.
7. Stdout/stderr are streamed back while the container runs.
8. Files written under `MERIDIAN_OUTPUT_DIR` are harvested from the worker container with the Docker archive API.
9. The container is removed.
10. The manager returns a structured result to the backend.

### Worker Bootstrap

The worker bootstrap in [bootstrap.py](/home/mathis/Documents/Dev/Meridian/sandbox_manager/worker/bootstrap.py):

- decodes `SANDBOX_CODE_B64`
- writes the target script to `/tmp/execution.py`
- creates and exports writable runtime dirs:
  - `HOME=/tmp/home`
  - `XDG_CACHE_HOME=/tmp/.cache`
  - `XDG_CONFIG_HOME=/tmp/.config`
  - `MPLCONFIGDIR=/tmp/.config/matplotlib`
- forces `MPLBACKEND=Agg`
- constrains thread-heavy math libraries with:
  - `OMP_NUM_THREADS=1`
  - `OPENBLAS_NUM_THREADS=1`
  - `MKL_NUM_THREADS=1`
  - `VECLIB_MAXIMUM_THREADS=1`
  - `NUMEXPR_NUM_THREADS=1`
- applies `pyseccomp` only when the runtime is not `nsjail`

Important implementation detail:

- The worker no longer applies `RLIMIT_NPROC`. That broke thread creation for libraries like matplotlib under some runtimes. PID control is handled at the Docker container level through `SANDBOX_PIDS_LIMIT`.

### Artifact Flow

To return files, executed code must write them under:

```bash
MERIDIAN_OUTPUT_DIR=/tmp/outputs
```

Artifact collection rules in [executor.py](/home/mathis/Documents/Dev/Meridian/sandbox_manager/app/executor.py):

- only files inside `/tmp/outputs` are considered
- directories are skipped
- symlinks, hardlinks, device nodes, traversal paths, and non-regular files are rejected
- file count, per-file size, and total size are bounded
- artifacts are returned inline as base64 in the sandbox manager response

Manager-side artifact fields:

| Field | Meaning |
|------|---------|
| `relative_path` | Path relative to `MERIDIAN_OUTPUT_DIR` |
| `name` | Display filename |
| `content_type` | MIME type |
| `size` | Raw byte size |
| `content_b64` | Base64 file contents |

Important architectural note:

- The sandbox manager talks to the host Docker daemon through `/var/run/docker.sock`.
- Each execution gets a Docker-managed artifact volume mounted at `/tmp/outputs`.
- After execution finishes, the manager copies that directory out with Docker’s archive API and then removes the volume.

### Concurrency & Limits

The manager enforces:

- max in-flight runs with `MAX_CONCURRENT_SANDBOXES`
- max queue wait with `SANDBOX_QUEUE_WAIT_SECONDS`
- wall-clock timeout with `EXECUTION_TIMEOUT_SECONDS`
- code payload size with `SANDBOX_CODE_MAX_BYTES`
- combined stdout/stderr capture size with `SANDBOX_OUTPUT_LIMIT_BYTES`
- container memory with `SANDBOX_MEMORY_LIMIT`
- container CPU budget with `SANDBOX_CPU_NANO_CPUS`
- container process count with `SANDBOX_PIDS_LIMIT`
- `/tmp` tmpfs size with `SANDBOX_TMPFS_SIZE`

Artifact-specific limits:

- `SANDBOX_ARTIFACT_MAX_FILES`
- `SANDBOX_ARTIFACT_MAX_FILE_BYTES`
- `SANDBOX_ARTIFACT_MAX_TOTAL_BYTES`

### Container Isolation

Common container settings:

- `network_mode="none"`
- `read_only=True`
- `/tmp` mounted as tmpfs
- all Linux capabilities dropped by default
- `no-new-privileges:true`

The exact runtime-specific details vary and are covered below.

## Runtime Modes

### `nsjail`

`SANDBOX_RUNTIME="nsjail"` is the required runtime. The outer worker container runs with standard Docker and launches the Python process inside NSJail.

Outer container behavior:

- runs as `root`
- keeps only:
  - `SYS_ADMIN`
  - `SETUID`
  - `SETGID`
  - `SETPCAP`
- uses:
  - `no-new-privileges:true`
  - `seccomp=unconfined`
  - `apparmor=unconfined`

Inner NSJail behavior:

- `--mode o`
- `--chroot /`
- `--cwd /tmp`
- `--disable_proc`
- `--disable_clone_newuser`
- `--iface_no_lo`
- drops to uid/gid `1000:1000`
- explicitly passes through:
  - `SANDBOX_CODE_B64`
  - `MERIDIAN_OUTPUT_DIR`
  - `MERIDIAN_SANDBOX_RUNTIME`
  - `MERIDIAN_MAX_FILE_SIZE_BYTES`

Why NSJail support exists:

- it offers strong isolation while still handling packages like NumPy and matplotlib reliably
- it keeps a second isolation layer inside the worker container
- on the host, keeping `kernel.unprivileged_userns_clone=0` is still recommended as defense in depth

## Environment Variables

The sandbox manager reads settings from environment variables via [config.py](/home/mathis/Documents/Dev/Meridian/sandbox_manager/app/config.py).

| Variable | Default | Purpose |
|---------|---------|---------|
| `SANDBOX_MANAGER_PORT` | `5000` | HTTP port for the FastAPI service |
| `MAX_CONCURRENT_SANDBOXES` | `10` | Max parallel executions |
| `SANDBOX_QUEUE_WAIT_SECONDS` | `5.0` | Max time to wait for a semaphore slot |
| `EXECUTION_TIMEOUT_SECONDS` | `10.0` | Max wall-clock runtime per execution |
| `SANDBOX_OUTPUT_LIMIT_BYTES` | `51200` | Max combined captured stdout/stderr bytes |
| `SANDBOX_CODE_MAX_BYTES` | `102400` | Max submitted code size |
| `SANDBOX_MEMORY_LIMIT` | `256m` | Docker memory limit |
| `SANDBOX_CPU_NANO_CPUS` | `500000000` | Docker CPU quota in nano CPUs |
| `SANDBOX_PIDS_LIMIT` | `64` | Docker process limit |
| `SANDBOX_TMPFS_SIZE` | `50m` | Size of writable `/tmp` tmpfs inside the worker |
| `SANDBOX_RUNTIME` | `nsjail` | Required runtime selector |
| `SANDBOX_ARTIFACT_MAX_FILES` | `20` | Max files harvested from one execution |
| `SANDBOX_ARTIFACT_MAX_FILE_BYTES` | `5242880` | Max raw bytes per harvested file |
| `SANDBOX_ARTIFACT_MAX_TOTAL_BYTES` | `10485760` | Max raw bytes across all harvested files |
| `SANDBOX_WORKER_IMAGE` | `meridian-sandbox-python:local` | Docker image used for worker containers |

Worker-only environment variables injected at execution time:

| Variable | Meaning |
|---------|---------|
| `SANDBOX_CODE_B64` | Base64-encoded submitted Python source |
| `MERIDIAN_OUTPUT_DIR` | Output directory for returnable artifacts |
| `MERIDIAN_SANDBOX_RUNTIME` | Resolved runtime name seen by the bootstrap |

## Worker Image

The worker image is built from [sandbox-python.Dockerfile](/home/mathis/Documents/Dev/Meridian/docker/sandbox-python.Dockerfile).

Highlights:

- based on `python:3.11-slim`
- builds NSJail from source in a dedicated builder stage
- installs scientific/data libraries from `sandbox-requirements.txt`
- bakes the worker bootstrap script into `/payload/bootstrap.py`
- pre-downloads NLTK datasets
- pre-warms matplotlib
- sets `MPLBACKEND=Agg`
- creates a fixed `sandboxuser` with uid/gid `1000`

Packages intentionally baked into the worker include:

- NumPy, pandas, SciPy, sympy, statsmodels
- scikit-learn, xgboost, lightgbm
- matplotlib, Plotly, Pillow, OpenCV
- BeautifulSoup, lxml, regex, requests
- `pyseccomp`
- `kaleido`

Note on Plotly:

- `kaleido` is present in `sandbox-requirements.txt`
- if Plotly image export says Kaleido is missing, the worker image is stale and must be rebuilt

## Integration With Meridian API

The sandbox manager is not exposed directly to end users. The Meridian backend integrates with it through [code_execution.py](/home/mathis/Documents/Dev/Meridian/api/app/services/tools/code_execution.py).

High-level flow:

1. backend tool sends code to `SANDBOX_MANAGER_URL/execute`
2. manager returns raw execution result plus raw artifact bytes as base64
3. backend persists those artifacts as normal Meridian files
4. backend sanitizes the tool result so model/tool history only sees persisted metadata, not raw bytes
5. UI renders:
   - inline images for image artifacts
   - download links for file artifacts

So:

- **sandbox manager response** contains raw `content_b64`
- **backend/model context** does not

## Troubleshooting

### `stderr` is empty on failure

Current behavior:

- streamed stderr is captured live
- if empty on non-zero exit, the manager falls back to `container.logs(stderr=True)`
- if still empty, it may synthesize a diagnostic for known silent runtime failures

### `MERIDIAN_OUTPUT_DIR` is not writable

Check that the worker is still starting with the expected `/tmp` tmpfs and that you rebuilt/restarted the sandbox stack after changing the worker image or runtime settings.

### matplotlib fails with cache or font-manager issues

The worker already sets:

- `HOME=/tmp/home`
- `MPLCONFIGDIR=/tmp/.config/matplotlib`
- `MPLBACKEND=Agg`

If you still see old matplotlib errors, rebuild the worker image and restart the manager.

### Startup fails with an unsupported runtime

The sandbox manager now supports only `SANDBOX_RUNTIME="nsjail"`. Any other value is treated as invalid configuration and should be changed in your config file before restarting the service.

### Code runs but no artifact is returned

Make sure the code writes files under:

```python
output_dir = os.environ.get("MERIDIAN_OUTPUT_DIR", "/tmp/outputs")
```

Files written elsewhere are not harvested.

### Plotly `write_image()` says Kaleido is missing

Rebuild the worker image. `kaleido` is part of `sandbox-requirements.txt`, so that error normally means the running image is stale.

### Python code is failing with a syntax error that looks like a sandbox issue

Verify the generated code itself. A common example:

```python
ax.set_title(r'$z = \sin(\sqrt{x^2 + y^2})$', fontsize=18)
```

If the closing quote or `$` is misplaced, the sandbox is behaving correctly by returning the traceback.

## Building & Deployment

### Local Dev

```bash
cd docker
./run.sh dev --sandbox-manager -d
```

### Full Local Build

```bash
cd docker
./run.sh build -d
```

### Production Images

`docker/run.sh prod ...`:

- resolves `SANDBOX_WORKER_IMAGE`
- pulls the main app images
- pulls the sandbox worker image separately

### Operational Notes

- restart `sandbox_manager` whenever you change:
  - sandbox manager Python code
  - `sandbox-python.Dockerfile`
  - `sandbox-requirements.txt`
  - runtime-related config in `config.toml` / `config.local.toml`
- rebuild the worker image whenever you change worker dependencies or runtime tooling

For full-stack setup, see the root Docker scripts and the main project README.
