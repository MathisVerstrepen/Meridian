#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="$1"

if [[ ! "$MODE" =~ ^(dev|prod|build)$ ]]; then
    echo "❌ Error: Invalid mode '$MODE'"
    echo ""
    echo "Usage: $0 <mode> [options]"
    echo ""
    echo "Modes:"
    echo "  dev     - Start databases and browser sidecar, optionally with sandbox_manager"
    echo "  prod    - Start all services using pre-built images from ghcr.io"
    echo "  build   - Start all services by building images locally"
    echo ""
    echo "Options:"
    echo "  down               - Stop and remove containers"
    echo "  down -v            - Stop, remove containers and volumes"
    echo "  -d                 - Run in detached mode"
    echo "  --sandbox-manager  - In dev mode, also run the sandbox_manager container"
    echo "  --force-rebuild    - Force rebuild without cache (build mode only)"
    echo "  --config-only      - Validate and render configuration without Docker activity"
    echo ""
    echo "Examples:"
    echo "  $0 dev -d                                # Start databases and browser sidecar"
    echo "  $0 dev --sandbox-manager -d              # Also start sandbox manager"
    echo "  $0 prod -d                               # Start all services with pre-built images"
    echo "  $0 build --force-rebuild -d              # Build locally without cache"
    echo "  $0 prod down                             # Stop production services"
    exit 1
fi

if [[ "$MODE" == "dev" ]]; then
    CONFIG_PROFILE="local"
    ENV_OUTPUT_FILE="env/.env.local"
    COMPOSE_ENV_FILE="env/.env.compose.local"
    COMPOSE_FILE="docker-compose.yml"
elif [[ "$MODE" == "prod" ]]; then
    CONFIG_PROFILE="production"
    ENV_OUTPUT_FILE="env/.env.prod"
    COMPOSE_ENV_FILE="$ENV_OUTPUT_FILE"
    COMPOSE_FILE="docker-compose.prod.yml"
else
    CONFIG_PROFILE="production"
    ENV_OUTPUT_FILE="env/.env.prod"
    COMPOSE_ENV_FILE="$ENV_OUTPUT_FILE"
    COMPOSE_FILE="docker-compose.yml"
fi

export DOCKER_ENV_FILE="$ENV_OUTPUT_FILE"

has_arg() {
    local needle="$1"
    shift

    for arg in "$@"; do
        if [[ "$arg" == "$needle" ]]; then
            return 0
        fi
    done

    return 1
}

compose_up_with_network_recovery() {
    local detach_mode="$1"
    shift

    local services=("$@")
    local up_args=(up --build)
    local output_file
    local exit_code

    if [[ "$detach_mode" == "true" ]]; then
        up_args+=(-d)
    fi

    up_args+=("${services[@]}")

    output_file="$(mktemp)"

    set +e
    docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "${up_args[@]}" > >(tee "$output_file") 2>&1
    exit_code=$?
    set -e

    if [[ $exit_code -eq 0 ]]; then
        rm -f "$output_file"
        return 0
    fi

    if grep -Eq "failed to set up container networking: network .* not found" "$output_file"; then
        echo ""
        echo "🧹 Detected stale Docker network metadata. Recreating dev containers..."
        docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" rm -sf "${services[@]}"
        rm -f "$output_file"
        docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "${up_args[@]}"
        return 0
    fi

    rm -f "$output_file"
    return "$exit_code"
}

get_env_value() {
    local key="$1"
    sed -n -E "s/^${key}[[:space:]]*=[[:space:]]*//p" "$ENV_OUTPUT_FILE" | tail -n 1
}

set_env_value() {
    local key="$1"
    local value="$2"
    local tmp_file

    tmp_file="$(mktemp "$(dirname "$ENV_OUTPUT_FILE")/.env-update.XXXXXX")"
    if [[ -f "$ENV_OUTPUT_FILE" ]]; then
        grep -v -E "^${key}[[:space:]]*=" "$ENV_OUTPUT_FILE" > "$tmp_file" || true
    fi
    printf '%s=%s\n' "$key" "$value" >> "$tmp_file"
    mv "$tmp_file" "$ENV_OUTPUT_FILE"
    chmod 600 "$ENV_OUTPUT_FILE"
    if [[ "$COMPOSE_ENV_FILE" != "$ENV_OUTPUT_FILE" ]]; then
        tmp_file="$(mktemp "$(dirname "$COMPOSE_ENV_FILE")/.env-update.XXXXXX")"
        grep -v -E "^${key}[[:space:]]*=" "$COMPOSE_ENV_FILE" > "$tmp_file" || true
        printf '%s=%s\n' "$key" "$value" >> "$tmp_file"
        mv "$tmp_file" "$COMPOSE_ENV_FILE"
        chmod 600 "$COMPOSE_ENV_FILE"
    fi
}

render_configuration() {
    "$SCRIPT_DIR/render-config.sh" "$CONFIG_PROFILE"
}

prepare_sandbox_worker_image() {
    local image_tag="$1"
    local name
    local image

    name="$(get_env_value NAME)"
    if [[ -z "$name" ]]; then
        echo "❌ Error: NAME is missing from $ENV_OUTPUT_FILE."
        exit 1
    fi

    if [[ "$MODE" == "prod" ]]; then
        image="ghcr.io/mathisverstrepen/meridian/sandbox-python:${image_tag}"
    else
        image="${name}_sandbox_python:local"
    fi

    set_env_value "SANDBOX_WORKER_IMAGE" "$image"
}

build_sandbox_worker_image() {
    local no_cache="$1"
    local image

    image="$(get_env_value SANDBOX_WORKER_IMAGE)"
    echo "🔨 Building sandbox worker image '$image'..."
    if [[ "$no_cache" == "true" ]]; then
        docker build -f sandbox-python.Dockerfile -t "$image" --no-cache ..
    else
        docker build -f sandbox-python.Dockerfile -t "$image" ..
    fi
}

pull_sandbox_worker_image() {
    local image

    image="$(get_env_value SANDBOX_WORKER_IMAGE)"
    echo "📥 Pulling sandbox worker image '$image'..."
    docker pull "$image"
}

if has_arg "down" "$@"; then
    DOWN_ENV_FILE="$COMPOSE_ENV_FILE"
    if [[ ! -f "$DOWN_ENV_FILE" && -f "$ENV_OUTPUT_FILE" ]]; then
        DOWN_ENV_FILE="$ENV_OUTPUT_FILE"
    fi
    DOWN_COMPOSE_ARGS=(-f "$COMPOSE_FILE")
    if [[ -f "$DOWN_ENV_FILE" ]]; then
        DOWN_COMPOSE_ARGS+=(--env-file "$DOWN_ENV_FILE")
    fi
    echo "🛑 Stopping Docker Compose services..."
    if has_arg "-v" "$@"; then
        docker compose "${DOWN_COMPOSE_ARGS[@]}" down -v
    else
        docker compose "${DOWN_COMPOSE_ARGS[@]}" down
    fi
    echo "✅ Docker Compose services stopped."
    exit 0
fi

render_configuration
echo ""

shift
CONFIG_ONLY=false
if has_arg "--config-only" "$@"; then
    CONFIG_ONLY=true
fi

case "$MODE" in
    "dev")
        DEV_DETACHED=false
        DEV_WITH_SANDBOX_MANAGER=false
        DEV_SERVICES=(db neo4j redis browser_service)

        if has_arg "-d" "$@"; then
            DEV_DETACHED=true
        fi

        if has_arg "--sandbox-manager" "$@"; then
            DEV_WITH_SANDBOX_MANAGER=true
            prepare_sandbox_worker_image "local"
            if [[ "$CONFIG_ONLY" == "false" ]]; then
                build_sandbox_worker_image false
            fi
            DEV_SERVICES+=(sandbox_manager)
        fi

        if [[ "$CONFIG_ONLY" == "true" ]]; then
            echo "✅ Configuration preflight completed; no Docker commands were run."
            exit 0
        fi

        if [[ "$DEV_WITH_SANDBOX_MANAGER" == "true" ]]; then
            echo "🔧 Dev mode: Starting databases, browser_service, and sandbox_manager containers..."
        else
            echo "🔧 Dev mode: Starting databases and browser_service containers..."
        fi

        compose_up_with_network_recovery "$DEV_DETACHED" "${DEV_SERVICES[@]}"

        echo ""
        echo "ℹ️ Development services are running:"
        echo "  PostgreSQL:      localhost:$(grep POSTGRES_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Neo4j HTTP:      localhost:$(grep NEO4J_HTTP_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Neo4j Bolt:      localhost:$(grep NEO4J_BOLT_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Redis:           localhost:$(grep REDIS_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Browser Service: localhost:$(grep LINK_EXTRACTION_BROWSER_SERVICE_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        BROWSER_PORT="$(get_env_value LINK_EXTRACTION_BROWSER_SERVICE_PORT)"
        if ! curl -fsS --max-time 5 "http://127.0.0.1:${BROWSER_PORT}/health" >/dev/null; then
            echo "⚠️ Browser service is started but not ready; direct/proxy fetching remains available."
        fi
        if [[ "$DEV_WITH_SANDBOX_MANAGER" == "true" ]]; then
            echo "  Sandbox Manager: localhost:$(grep SANDBOX_MANAGER_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        fi
        echo ""
        echo "Start your backend and frontend manually for development."
        ;;

    "prod")
        if [[ ! -f "$COMPOSE_FILE" ]]; then
            echo "❌ Error: $COMPOSE_FILE not found."
            echo "This file should define services using ghcr.io images."
            exit 1
        fi

        DOCKER_ARGS=()
        export IMAGE_TAG="latest"

        for arg in "$@"; do
            if [[ "$arg" == "--config-only" ]]; then
                continue
            elif [[ "$arg" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
                export IMAGE_TAG="${arg#v}"
            else
                DOCKER_ARGS+=("$arg")
            fi
        done

        prepare_sandbox_worker_image "$IMAGE_TAG"

        if [[ "$CONFIG_ONLY" == "true" ]]; then
            echo "✅ Configuration preflight completed; no Docker commands were run."
            exit 0
        fi

        echo "🚀 Production mode: Starting all services with pre-built images..."

        echo "📥 Pulling images with tag '$IMAGE_TAG' from ghcr.io..."
        docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" pull
        pull_sandbox_worker_image

        docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" up "${DOCKER_ARGS[@]}"
        if ! docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" exec -T api python -c "import os,urllib.request; urllib.request.urlopen(os.environ['LINK_EXTRACTION_BROWSER_SERVICE_URL'] + '/health', timeout=5)" >/dev/null 2>&1; then
            echo "⚠️ Browser service is not ready; direct/proxy fetching remains available."
        fi
        ;;

    "build")
        FORCE_REBUILD=false
        DOCKER_ARGS=()

        for arg in "$@"; do
            if [[ "$arg" == "--config-only" ]]; then
                continue
            elif [[ "$arg" == "--force-rebuild" ]]; then
                FORCE_REBUILD=true
            else
                DOCKER_ARGS+=("$arg")
            fi
        done

        prepare_sandbox_worker_image "local"

        if [[ "$CONFIG_ONLY" == "true" ]]; then
            echo "✅ Configuration preflight completed; no Docker commands were run."
            exit 0
        fi

        echo "🔨 Build mode: Starting all services with local builds..."
        build_sandbox_worker_image "$FORCE_REBUILD"

        if [[ "$FORCE_REBUILD" == "true" ]]; then
            echo "⚡ Force rebuild requested. Building images with --no-cache..."
            docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" build --no-cache
            docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" up "${DOCKER_ARGS[@]}"
        else
            docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" up --build "${DOCKER_ARGS[@]}"
        fi
        ;;
esac

echo "✅ Docker Compose services started successfully."
echo ""

if [[ "$MODE" != "dev" ]]; then
    NITRO_PORT=$(grep NITRO_PORT "$ENV_OUTPUT_FILE" 2>/dev/null | sed -E 's/^[^=]+=//; s/^[[:space:]]+//; s/[[:space:]]+$//' || echo "3000")
    echo "ℹ️ Post-Start Instructions:"
    echo "  📱 Access the application at: http://localhost:${NITRO_PORT}"
    echo "  🛑 To stop services: ./run.sh $MODE down"
    echo "  📋 To view logs: docker compose -f $COMPOSE_FILE --env-file $ENV_OUTPUT_FILE logs -f"
fi
