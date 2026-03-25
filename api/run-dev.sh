#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/app"
USER_FILES_DIR="${APP_DIR}/data/user_files"
CLONED_REPOS_DIR="${APP_DIR}/data/cloned_repos"

cd "${APP_DIR}"

exec "${SCRIPT_DIR}/venv/bin/uvicorn" main:app \
    --host 0.0.0.0 \
    --port "${API_PORT:-8000}" \
    --reload \
    --reload-dir . \
    --reload-exclude "${USER_FILES_DIR}" \
    --reload-exclude "${CLONED_REPOS_DIR}"
