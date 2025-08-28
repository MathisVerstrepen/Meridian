#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
ENV_MODE="$1"

if [[ "$ENV_MODE" == "dev" ]]; then
    TOML_CONFIG_FILE="config.local.toml"
    ENV_OUTPUT_FILE="env/.env.local"
else
    TOML_CONFIG_FILE="config.toml"
    ENV_OUTPUT_FILE="env/.env.prod"
fi

export DOCKER_ENV_FILE="$ENV_OUTPUT_FILE"

# --- Stop Docker Compose services if 'down' argument is provided ---
if [[ "$1" == "down" || "$2" == "down" ]]; then
    echo "🛑 Stopping Docker Compose services..."
    if [[ "$2" == "-v" || "$3" == "-v" ]]; then
        docker compose --env-file "$ENV_OUTPUT_FILE" down -v
    else
        docker compose --env-file "$ENV_OUTPUT_FILE" down
    fi
    echo "✅ Docker Compose services stopped."
    exit 0
fi

# --- Ensure yq is installed ---
if ! command -v yq &>/dev/null || ! yq --version | grep -q "mikefarah"; then
    echo "Error: The required version of 'yq' (from Mike Farah) is not installed."
    echo "Please visit https://github.com/mikefarah/yq/#install to install it."
    echo " - Common commands:"
    echo " - macOS (Homebrew): brew install yq"
    echo " - Linux (Snap): snap install yq"
    echo " - (First, you may need to 'pip uninstall yq')"
    exit 1
fi

# --- Generate the .env file from TOML ---
echo "⚙️ Generating '$ENV_OUTPUT_FILE' from '$TOML_CONFIG_FILE'..."

mkdir -p "$(dirname "$ENV_OUTPUT_FILE")"

yq eval '.[]' "$TOML_CONFIG_FILE" -o=props >"$ENV_OUTPUT_FILE"

echo "✅ Generation complete."
echo ""

if [[ "$ENV_MODE" == "dev" ]]; then
    echo "⚙️ Dev mode: Starting only 'db' and 'neo4j' containers..."
    if [[ "$2" == "-d" ]]; then
        docker compose --env-file "$ENV_OUTPUT_FILE" up --build db neo4j -d
    else
        docker compose --env-file "$ENV_OUTPUT_FILE" up --build db neo4j
    fi
    exit 0
fi

# --- Start Docker Compose ---
echo "🚀 Starting Docker Compose services..."

shift


# --- Argument parsing for force rebuild ---
BUILD_FLAGS="--build"
DOCKER_ARGS=()

for arg in "$@"; do
  if [[ "$arg" == "--force-rebuild" ]]; then
    # If --force-rebuild is found, add --no-cache to the build flags
    echo "⚡ Force rebuild requested. Disabling cache..."
    BUILD_FLAGS="--build --no-cache"
  else
    # Otherwise, add the argument to the list for docker compose
    DOCKER_ARGS+=("$arg")
  fi
done

docker compose --env-file "$ENV_OUTPUT_FILE" up ${BUILD_FLAGS} "${DOCKER_ARGS[@]}"

echo "✅ Docker Compose services started."
echo ""

# --- Post-Start Instructions ---
echo "ℹ️ Post-Start Instructions:"
echo " - Access the application at: http://localhost:3000"
echo " - To stop the services, run: ./run.sh down"
echo " - To view logs, run: docker compose logs -f"
echo " - To force a rebuild (no cache), run: ./run.sh --force-rebuild"
