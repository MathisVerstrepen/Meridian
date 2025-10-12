#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
MODE="$1"

# Validate mode
if [[ ! "$MODE" =~ ^(dev|prod|build)$ ]]; then
    echo "❌ Error: Invalid mode '$MODE'"
    echo ""
    echo "Usage: $0 <mode> [options]"
    echo ""
    echo "Modes:"
    echo "  dev     - Start only databases (PostgreSQL + Neo4j) for local development"
    echo "  prod    - Start all services using pre-built images from ghcr.io"
    echo "  build   - Start all services by building images locally"
    echo ""
    echo "Options:"
    echo "  down           - Stop and remove containers"
    echo "  down -v        - Stop, remove containers and volumes"
    echo "  -d             - Run in detached mode"
    echo "  --force-rebuild - Force rebuild without cache (build mode only)"
    echo ""
    echo "Examples:"
    echo "  $0 dev -d                    # Start databases in background"
    echo "  $0 prod -d                   # Start all services with pre-built images"
    echo "  $0 build --force-rebuild -d  # Build locally without cache"
    echo "  $0 prod down                 # Stop production services"
    exit 1
fi

# Set configuration based on mode
if [[ "$MODE" == "dev" ]]; then
    TOML_CONFIG_FILE="config.local.toml"
    ENV_OUTPUT_FILE="env/.env.local"
    COMPOSE_FILE="docker-compose.yml"
elif [[ "$MODE" == "prod" ]]; then
    TOML_CONFIG_FILE="config.toml"
    ENV_OUTPUT_FILE="env/.env.prod"
    COMPOSE_FILE="docker-compose.prod.yml"
else # build mode
    TOML_CONFIG_FILE="config.toml"
    ENV_OUTPUT_FILE="env/.env.prod"
    COMPOSE_FILE="docker-compose.yml"
fi

export DOCKER_ENV_FILE="$ENV_OUTPUT_FILE"

# --- Stop Docker Compose services if 'down' argument is provided ---
if [[ "$2" == "down" || "$3" == "down" || "$4" == "down" ]]; then
    echo "🛑 Stopping Docker Compose services..."
    if [[ "$2" == "-v" || "$3" == "-v" || "$4" == "-v" ]]; then
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" down -v
    else
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" down
    fi
    echo "✅ Docker Compose services stopped."
    exit 0
fi

# --- Ensure yq is installed ---
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

# --- Generate the .env file from TOML ---
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

# --- Mode-specific execution ---
shift # Remove mode from arguments

case "$MODE" in
    "dev")
        echo "🔧 Dev mode: Starting only 'db', 'neo4j', and 'redis' containers..."
        if [[ "$1" == "-d" || "$2" == "-d" ]]; then
            docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" up --build db neo4j redis -d
        else
            docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" up --build db neo4j redis
        fi
        echo ""
        echo "ℹ️ Development databases are running:"
        echo "  PostgreSQL: localhost:$(grep POSTGRES_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Neo4j HTTP: localhost:$(grep NEO4J_HTTP_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Neo4j Bolt: localhost:$(grep NEO4J_BOLT_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo "  Redis:      localhost:$(grep REDIS_PORT "$ENV_OUTPUT_FILE" | cut -d'=' -f2)"
        echo ""
        echo "Start your backend and frontend manually for development."
        ;;
        
    "prod")
        echo "🚀 Production mode: Starting all services with pre-built images..."
        
        # Check if production compose file exists
        if [[ ! -f "$COMPOSE_FILE" ]]; then
            echo "❌ Error: $COMPOSE_FILE not found."
            echo "This file should define services using ghcr.io images."
            exit 1
        fi
        
        # Parse arguments for version tag
        DOCKER_ARGS=()
        export IMAGE_TAG="latest"

        for arg in "$@"; do
            # Check for semver-like string (e.g., v1.2.3, 1.2.3, v1.2.3-beta.1)
            if [[ "$arg" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
                # remove 'v' prefix if present
                export IMAGE_TAG="${arg#v}"
            else
                DOCKER_ARGS+=("$arg")
            fi
        done
        
        # Pull images with the specified tag
        echo "📥 Pulling images with tag '$IMAGE_TAG' from ghcr.io..."
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" pull
        
        # Start services
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_OUTPUT_FILE" up "${DOCKER_ARGS[@]}"
        ;;
        
    "build")
        echo "🔨 Build mode: Starting all services with local builds..."
        
        # Parse arguments for force rebuild
        FORCE_REBUILD=false
        DOCKER_ARGS=()
        
        for arg in "$@"; do
            if [[ "$arg" == "--force-rebuild" ]]; then
                FORCE_REBUILD=true
            else
                DOCKER_ARGS+=("$arg")
            fi
        done
        
        # Execute with or without force rebuild
        if [[ "$FORCE_REBUILD" == true ]]; then
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

# --- Post-Start Instructions ---
if [[ "$MODE" != "dev" ]]; then
    NITRO_PORT=$(grep NITRO_PORT "$ENV_OUTPUT_FILE" 2>/dev/null | sed -E 's/^[^=]+=//; s/^[[:space:]]+//; s/[[:space:]]+$//' || echo "3000")
    echo "ℹ️ Post-Start Instructions:"
    echo "  📱 Access the application at: http://localhost:${NITRO_PORT}"
    echo "  🛑 To stop services: ./run.sh $MODE down"
    echo "  📋 To view logs: docker compose -f $COMPOSE_FILE --env-file "$ENV_OUTPUT_FILE" logs -f"
fi
