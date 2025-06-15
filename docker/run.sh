#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Stop Docker Compose services if 'down' argument is provided ---
if [[ "$1" == "down" ]]; then
    echo "🛑 Stopping Docker Compose services..."
    if [[ "$2" == "-v" ]]; then
        docker compose down -v
    else
        docker compose down
    fi
    echo "✅ Docker Compose services stopped."
    exit 0
fi

# --- Configuration ---
TOML_CONFIG_FILE="config.toml"
ENV_OUTPUT_FILE="env/.env.prod"

# --- Ensure yq is installed ---
if ! command -v yq &>/dev/null || ! yq --version | grep -q "mikefarah"; then
    echo "Error: The required version of 'yq' (from Mike Farah) is not installed."
    echo "The installed 'yq' is the incompatible Python wrapper."
    echo "Please visit https://github.com/mikefarah/yq/#install to install it."
    echo "  - Common commands:"
    echo "    - macOS (Homebrew):   brew install yq"
    echo "    - Linux (Snap):       snap install yq"
    echo "    - (First, you may need to 'pip uninstall yq')"
    exit 1
fi

# --- Generate the .env file from TOML ---
echo "⚙️  Generating '$ENV_OUTPUT_FILE' from '$TOML_CONFIG_FILE'..."

mkdir -p "$(dirname "$ENV_OUTPUT_FILE")"

yq eval '.[]' "$TOML_CONFIG_FILE" -o=props >"$ENV_OUTPUT_FILE"

echo "✅ Generation complete."
echo ""

# --- Start Docker Compose ---
echo "🚀 Starting Docker Compose services..."

docker compose up --build "$@"

echo "✅ Docker Compose services started."
echo ""

# --- Post-Start Instructions ---
echo "ℹ️  Post-Start Instructions:"
echo "  - Access the application at: http://localhost:3000"
echo "  - To stop the services, run: ./run.sh down"
echo "  - To view logs, run: docker compose logs -f"
echo "  - To rebuild the images, run: ./run.sh --build"
