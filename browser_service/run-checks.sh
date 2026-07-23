#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT/venv/bin/python"
cd "$(dirname "$ROOT")"

"$PYTHON" -m black --config "$ROOT/pyproject.toml" --check "$ROOT/app" "$ROOT/tests"
"$PYTHON" -m isort --settings-path "$ROOT/pyproject.toml" --check-only "$ROOT/app" "$ROOT/tests"
"$PYTHON" -m flake8 --max-line-length=100 "$ROOT/app" "$ROOT/tests"
"$PYTHON" -m mypy --config-file "$ROOT/pyproject.toml" "$ROOT/app"
"$PYTHON" -m pytest "$ROOT/tests" -q
