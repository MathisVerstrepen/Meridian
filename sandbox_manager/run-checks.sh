#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/../scripts/python-env.sh"
SANDBOX_PYTHON="${SANDBOX_PYTHON:-${SANDBOX_VENV:-$SCRIPT_DIR/venv}/bin/python}"
require_project_python "$SANDBOX_PYTHON"
PYTHON_TARGETS=(
    "app"
    "tests"
    "worker"
)

"$SANDBOX_PYTHON" -m black --check "${PYTHON_TARGETS[@]}"
"$SANDBOX_PYTHON" -m isort --check-only "${PYTHON_TARGETS[@]}"
"$SANDBOX_PYTHON" -m flake8 --jobs=1 "${PYTHON_TARGETS[@]}"
"$SANDBOX_PYTHON" -m mypy "${PYTHON_TARGETS[@]}"
"$SANDBOX_PYTHON" -m pytest tests
