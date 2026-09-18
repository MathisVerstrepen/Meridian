#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/app"
USER_FILES_DIR="data/user_files"
CLONED_REPOS_DIR="data/cloned_repos"
source "$SCRIPT_DIR/../scripts/python-env.sh"
API_PYTHON="${API_PYTHON:-${API_VENV:-$SCRIPT_DIR/venv}/bin/python}"
require_project_python "$API_PYTHON"

case "${1:-dev}" in
    dev|serve)
        if [ "$#" -gt 1 ]; then
            echo "Usage: $0 [dev|serve]" >&2
            exit 1
        fi
        ;;
    upgrade)
        if [ "$#" -gt 2 ]; then
            echo "Usage: $0 upgrade [revision]" >&2
            exit 1
        fi

        cd "${SCRIPT_DIR}"
        exec "$API_PYTHON" -m alembic upgrade "${2:-head}"
        ;;
    downgrade)
        if [ "$#" -ne 2 ]; then
            echo "Usage: $0 downgrade <revision>" >&2
            exit 1
        fi

        cd "${SCRIPT_DIR}"
        exec "$API_PYTHON" -m alembic downgrade "$2"
        ;;
    *)
        echo "Usage: $0 [dev|serve|upgrade [revision]|downgrade <revision>]" >&2
        exit 1
        ;;
esac

cd "${APP_DIR}"

exec "$API_PYTHON" -m uvicorn \
    --env-file "${SCRIPT_DIR}/../docker/env/.env.local" \
    main:app \
    --host 0.0.0.0 \
    --port "${API_PORT:-8000}" \
    --reload \
    --reload-dir . \
    --reload-exclude "${USER_FILES_DIR}" \
    --reload-exclude "${CLONED_REPOS_DIR}"
