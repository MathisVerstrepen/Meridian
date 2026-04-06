#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_BIN="$SCRIPT_DIR/../api/venv/bin"
TOOLS=(black isort flake8 mypy pytest)
PYTHON_TARGETS=(
    "app"
    "tests"
    "worker"
)

resolve_tool() {
    local tool="$1"

    if [[ -x "$VENV_BIN/$tool" ]]; then
        printf '%s\n' "$VENV_BIN/$tool"
        return 0
    fi

    if command -v "$tool" >/dev/null 2>&1; then
        command -v "$tool"
        return 0
    fi

    return 1
}

declare -A TOOL_PATHS=()
for tool in "${TOOLS[@]}"; do
    if ! TOOL_PATHS["$tool"]="$(resolve_tool "$tool")"; then
        echo "Missing tool: $tool" >&2
        echo "Install sandbox manager development dependencies in api/venv or make them available on PATH." >&2
        exit 1
    fi
done

"${TOOL_PATHS[black]}" --check "${PYTHON_TARGETS[@]}"
"${TOOL_PATHS[isort]}" --check-only "${PYTHON_TARGETS[@]}"
"${TOOL_PATHS[flake8]}" --jobs=1 "${PYTHON_TARGETS[@]}"
"${TOOL_PATHS[mypy]}" "${PYTHON_TARGETS[@]}"
"${TOOL_PATHS[pytest]}" tests
