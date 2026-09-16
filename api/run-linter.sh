#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/../scripts/python-env.sh"
API_PYTHON="${API_PYTHON:-${API_VENV:-$SCRIPT_DIR/venv}/bin/python}"
require_project_python "$API_PYTHON"
PYTHON_TARGETS=(
    "app"
    "migrations"
)

"$API_PYTHON" -m black --check "${PYTHON_TARGETS[@]}"
"$API_PYTHON" -m isort --check-only "${PYTHON_TARGETS[@]}"
"$API_PYTHON" -m flake8 --jobs=1 "${PYTHON_TARGETS[@]}"
"$API_PYTHON" -m mypy "${PYTHON_TARGETS[@]}"
