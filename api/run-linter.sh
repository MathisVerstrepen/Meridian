#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_BIN="$SCRIPT_DIR/venv/bin"
TOOLS=(black isort flake8 mypy)
PYTHON_TARGETS=(
    "app"
    "migrations"
)

if [[ ! -d "$VENV_BIN" ]]; then
    echo "Missing virtualenv at $VENV_BIN" >&2
    echo "Create it and install backend dependencies before running this script." >&2
    exit 1
fi

for tool in "${TOOLS[@]}"; do
    if [[ ! -x "$VENV_BIN/$tool" ]]; then
        echo "Missing tool: $VENV_BIN/$tool" >&2
        echo "Install backend development dependencies in api/venv before running this script." >&2
        exit 1
    fi
done

"$VENV_BIN/black" --check "${PYTHON_TARGETS[@]}"
"$VENV_BIN/isort" --check-only "${PYTHON_TARGETS[@]}"
"$VENV_BIN/flake8" --jobs=1 "${PYTHON_TARGETS[@]}"
"$VENV_BIN/mypy" "${PYTHON_TARGETS[@]}"
