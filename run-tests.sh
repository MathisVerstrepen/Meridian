#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT_DIR/api"
UI_DIR="$ROOT_DIR/ui"
RUN_E2E=0

usage() {
    cat <<'EOF'
Usage: ./run-tests.sh [--e2e]

Runs the repository test protocol:
  - Backend pytest suite
  - Backend lint/type checks
  - Frontend lint
  - Frontend typecheck

Options:
  --e2e    Also run Playwright end-to-end tests in ui/
  -h, --help
           Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --e2e)
            RUN_E2E=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

run_step() {
    local label="$1"
    shift
    printf '\n==> %s\n' "$label"
    "$@"
}

if [[ -x "$API_DIR/venv/bin/python" ]]; then
    API_PYTHON="$API_DIR/venv/bin/python"
else
    API_PYTHON="python"
fi

run_step "Backend tests" bash -c "cd '$API_DIR' && '$API_PYTHON' -m pytest tests"
run_step "Backend lint/type checks" bash -c "cd '$API_DIR' && ./run-linter.sh"
run_step "Frontend lint" bash -c "cd '$UI_DIR' && pnpm lint"
run_step "Frontend typecheck" bash -c "cd '$UI_DIR' && pnpm typecheck"

if [[ "$RUN_E2E" -eq 1 ]]; then
    run_step "Frontend Playwright e2e" bash -c "cd '$UI_DIR' && pnpm test:e2e"
fi

printf '\nAll requested checks passed.\n'
