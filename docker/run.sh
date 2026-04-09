#!/bin/bash

set -e

MODE="$1"

if [[ ! "$MODE" =~ ^(dev|prod|build)$ ]]; then
    echo "❌ Error: Invalid mode '$MODE'"
    echo ""
    echo "Usage: $0 <mode> [options]"
    echo ""
    echo "Modes:"
    echo "  dev     - Start databases for local development, optionally with sandbox_manager"
    echo "  prod    - Start all services using pre-built images from ghcr.io"
    echo "  build   - Start all services by building images locally"
    echo ""
    echo "Options:"
    echo "  down               - Stop and remove containers"
    echo "  down -v            - Stop, remove containers and volumes"
    echo "  -d                 - Run in detached mode"
    echo "  --sandbox-manager  - In dev mode, also run the sandbox_manager container"
    echo "  --force-rebuild    - Force rebuild without cache (build mode only)"
    echo ""
    echo "Examples:"
    echo "  $0 dev -d                                # Start databases in background"
    echo "  $0 dev --sandbox-manager -d              # Start databases and sandbox manager"
    echo "  $0 prod -d                               # Start all services with pre-built images"
    echo "  $0 build --force-rebuild -d              # Build locally without cache"
    echo "  $0 prod down                             # Stop production services"
    exit 1
fi

if [[ "$MODE" == "dev" ]]; then
    TOML_CONFIG_FILE="config.local.toml"
    ENV_OUTPUT_FILE="env/.env.local"
    COMPOSE_FILE="docker-compose.yml"
elif [[ "$MODE" == "prod" ]]; then
    TOML_CONFIG_FILE="config.toml"
    ENV_OUTPUT_FILE="env/.env.prod"
    COMPOSE_FILE="docker-compose.prod.yml"
else
    TOML_CONFIG_FILE="config.toml"
    ENV_OUTPUT_FILE="env/.env.prod"
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
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" "${up_args[@]}" > >(tee "$output_file") 2>&1
    exit_code=$?
    set -e

    if [[ $exit_code -eq 0 ]]; then
        rm -f "$output_file"
        return 0
    fi

    if grep -Eq "failed to set up container networking: network .* not found" "$output_file"; then
        echo ""
        echo "🧹 Detected stale Docker network metadata. Recreating dev containers..."
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" rm -sf "${services[@]}"
        rm -f "$output_file"
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" "${up_args[@]}"
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

    tmp_file="$(mktemp)"
    if [[ -f "$ENV_OUTPUT_FILE" ]]; then
        grep -v -E "^${key}[[:space:]]*=" "$ENV_OUTPUT_FILE" > "$tmp_file" || true
    fi
    printf '%s=%s\n' "$key" "$value" >> "$tmp_file"
    mv "$tmp_file" "$ENV_OUTPUT_FILE"
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
    echo "🛑 Stopping Docker Compose services..."
    if has_arg "-v" "$@"; then
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" down -v
    else
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" down
    fi
    echo "✅ Docker Compose services stopped."
    exit 0
fi

if ! command -v yq &>/dev/null || ! yq --version | grep -q "mikefarah"; then
    echo "❌ Error: The required version of 'yq' (from Mike Farah) is not installed."
    echo "Please visit https://github.com/mikefarah/yq/#install to install it."
    echo ""
    echo "Common installation commands:"
    echo "  macOS (Homebrew): brew install yq"
    echo "  Linux (Snap): snap install yq"
    echo "  (Note: You may need to 'pip uninstall yq' first)"
    exit 1
fi

echo "⚙️ Generating '$ENV_OUTPUT_FILE' from '$TOML_CONFIG_FILE'..."

mkdir -p "$(dirname "$ENV_OUTPUT_FILE")"

if [[ ! -f "$TOML_CONFIG_FILE" ]]; then
    echo "❌ Error: Configuration file '$TOML_CONFIG_FILE' not found."
    if [[ "$MODE" == "dev" ]]; then
        echo "Please copy 'config.local.example.toml' to 'config.local.toml' and configure it."
    else
        echo "Please copy 'config.example.toml' to 'config.toml' and configure it."
    fi
    exit 1
fi

yq eval '.[]' "$TOML_CONFIG_FILE" -o=props > "$ENV_OUTPUT_FILE"

echo "✅ Environment file generated."
echo ""

shift

case "$MODE" in
    "dev")
        DEV_DETACHED=false
        DEV_WITH_SANDBOX_MANAGER=false
        DEV_SERVICES=(db neo4j redis)

        if has_arg "-d" "$@"; then
            DEV_DETACHED=true
        fi

        if has_arg "--sandbox-manager" "$@"; then
            DEV_WITH_SANDBOX_MANAGER=true
            prepare_sandbox_worker_image "local"
            build_sandbox_worker_image false
            DEV_SERVICES+=(sandbox_manager)
            echo "🔧 Dev mode: Starting 'db', 'neo4j', 'redis', and 'sandbox_manager' containers..."
        else
            echo "🔧 Dev mode: Starting only 'db', 'neo4j', and 'redis' containers..."
        fi

        compose_up_with_network_recovery "$DEV_DETACHED" "${DEV_SERVICES[@]}"

        echo ""
        echo "ℹ️ Development services are running:"
        echo "  PostgreSQL:      localhost:$(grep POSTGRES_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Neo4j HTTP:      localhost:$(grep NEO4J_HTTP_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Neo4j Bolt:      localhost:$(grep NEO4J_BOLT_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Redis:           localhost:$(grep REDIS_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        if [[ "$DEV_WITH_SANDBOX_MANAGER" == "true" ]]; then
            echo "  Sandbox Manager: localhost:$(grep SANDBOX_MANAGER_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        fi
        echo ""
        echo "Start your backend and frontend manually for development."
        ;;

    "prod")
        echo "🚀 Production mode: Starting all services with pre-built images..."

        if [[ ! -f "$COMPOSE_FILE" ]]; then
            echo "❌ Error: $COMPOSE_FILE not found."
            echo "This file should define services using ghcr.io images."
            exit 1
        fi

        DOCKER_ARGS=()
        export IMAGE_TAG="latest"

        for arg in "$@"; do
            if [[ "$arg" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
                export IMAGE_TAG="${arg#v}"
            else
                DOCKER_ARGS+=("$arg")
            fi
        done

        prepare_sandbox_worker_image "$IMAGE_TAG"

        echo "📥 Pulling images with tag '$IMAGE_TAG' from ghcr.io..."
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" pull
        pull_sandbox_worker_image

        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" up "${DOCKER_ARGS[@]}"
        ;;

    "build")
        echo "🔨 Build mode: Starting all services with local builds..."

        FORCE_REBUILD=false
        DOCKER_ARGS=()

        for arg in "$@"; do
            if [[ "$arg" == "--force-rebuild" ]]; then
                FORCE_REBUILD=true
            else
                DOCKER_ARGS+=("$arg")
            fi
        done

        prepare_sandbox_worker_image "local"
        build_sandbox_worker_image "$FORCE_REBUILD"

        if [[ "$FORCE_REBUILD" == "true" ]]; then
            echo "⚡ Force rebuild requested. Building images with --no-cache..."
            docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" build --no-cache
            docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" up "${DOCKER_ARGS[@]}"
        else
            docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" up --build "${DOCKER_ARGS[@]}"
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
