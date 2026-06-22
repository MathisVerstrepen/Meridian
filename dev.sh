#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT_DIR/api"
UI_DIR="$ROOT_DIR/ui"
DOCKER_DIR="$ROOT_DIR/docker"
LOG_DIR="/tmp/meridian-dev"

BACKEND_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${NITRO_PORT:-3000}"

BACKEND_PID=""
FRONTEND_PID=""
CLEANING_UP=0

usage() {
    cat <<'EOF'
Usage: ./dev.sh

Starts the full local development stack in order:
  1. Docker services (Postgres, Neo4j, Redis) via docker/run.sh dev -d
  2. Backend (FastAPI/uvicorn) via api/run-dev.sh
  3. Frontend (Nuxt) via pnpm dev

Each step waits for readiness before proceeding.
Press Ctrl+C to stop the backend and frontend (Docker services keep running).

Options:
  -h, --help    Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

log() { printf '\n==> %s\n' "$*"; }
ok()  { printf '  \xe2\x9c\x93 %s\n' "$*"; }
err() { printf '  \xe2\x9c\x97 %s\n' "$*" >&2; }

wait_for_tcp() {
    local host="$1" port="$2" name="$3" timeout="${4:-60}"
    local elapsed=0
    while ! (echo > "/dev/tcp/$host/$port") 2>/dev/null; do
        sleep 1
        elapsed=$((elapsed + 1))
        if (( elapsed >= timeout )); then
            err "$name not ready on $host:$port after ${timeout}s"
            return 1
        fi
    done
    ok "$name ready (port $port)"
}

dump_log() {
    local logfile="$1"
    if [[ -f "$logfile" ]]; then
        echo ""
        echo "----- $logfile -----"
        tail -n 50 "$logfile"
        echo "---------------------"
        echo "Full log: $logfile"
    fi
}

wait_for_http() {
    local url="$1" name="$2" timeout="${3:-120}" pid="${4:-}" logfile="${5:-}"
    local elapsed=0
    while ! curl -sf --max-time 5 "$url" -o /dev/null 2>/dev/null; do
        if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
            err "$name process exited unexpectedly"
            dump_log "$logfile"
            return 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        if (( elapsed >= timeout )); then
            err "$name not ready at $url after ${timeout}s"
            dump_log "$logfile"
            return 1
        fi
    done
    ok "$name ready ($url)"
}

kill_tree() {
    local pid="$1"
    local children
    children=$(pgrep -P "$pid" 2>/dev/null || true)
    for child in $children; do
        kill_tree "$child"
    done
    kill "$pid" 2>/dev/null || true
}

cleanup() {
    [[ "$CLEANING_UP" -eq 1 ]] && return
    CLEANING_UP=1
    echo ""
    log "Stopping backend and frontend..."
    [[ -n "$FRONTEND_PID" ]] && kill_tree "$FRONTEND_PID"
    [[ -n "$BACKEND_PID" ]] && kill_tree "$BACKEND_PID"
    ok "Backend and frontend stopped"
    echo "Docker services are still running."
    echo "Stop them with: cd docker && ./run.sh down"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ! command -v curl &>/dev/null; then
    err "curl is required but not installed"
    exit 1
fi

# Ensure node is on PATH (nvm setup lives in .bashrc, not sourced by non-interactive shells)
if ! command -v node &>/dev/null; then
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    if [[ -s "$NVM_DIR/nvm.sh" ]]; then
        \. "$NVM_DIR/nvm.sh"
    fi
fi
if ! command -v node &>/dev/null; then
    err "node is required but not found (is nvm installed?)"
    exit 1
fi

mkdir -p "$LOG_DIR"

# --- 1. Docker services (Postgres, Neo4j, Redis) ---
log "Starting Docker dev services (Postgres, Neo4j, Redis)..."
(cd "$DOCKER_DIR" && ./run.sh dev -d)

# --- 2. Wait for Docker services ---
log "Waiting for Docker services to be ready..."
wait_for_tcp localhost 5432 "PostgreSQL" 60
wait_for_tcp localhost 7687 "Neo4j (Bolt)" 60
wait_for_tcp localhost 6379 "Redis" 60

# --- 3. Database migrations ---
log "Running database migrations..."
(cd "$API_DIR" && ./venv/bin/alembic upgrade head)
ok "Migrations complete"

# --- 4. Start backend ---
log "Starting backend..."
(cd "$API_DIR" && exec ./run-dev.sh) > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# --- 5. Wait for backend ---
log "Waiting for backend to be ready..."
wait_for_http "http://localhost:${BACKEND_PORT}/" "Backend" 120 "$BACKEND_PID" "$LOG_DIR/backend.log"

# --- 6. Start frontend ---
log "Starting frontend..."
(cd "$UI_DIR" && exec pnpm dev) > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

# --- 7. Wait for frontend ---
log "Waiting for frontend to be ready..."
wait_for_http "http://localhost:${FRONTEND_PORT}/" "Frontend" 120 "$FRONTEND_PID" "$LOG_DIR/frontend.log"

# --- 8. Summary ---
echo ""
log "All services are ready!"
printf '  Backend API docs: http://localhost:%s/docs\n' "$BACKEND_PORT"
printf '  Frontend:         http://localhost:%s\n' "$FRONTEND_PORT"
printf '  Backend log:      %s/backend.log\n' "$LOG_DIR"
printf '  Frontend log:     %s/frontend.log\n' "$LOG_DIR"
echo ""
echo "Press Ctrl+C to stop backend and frontend."
echo "Docker services keep running — stop with: cd docker && ./run.sh down"
echo ""

wait
