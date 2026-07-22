import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger("uvicorn.error")


def load_environment_variables():
    if os.getenv("ENV", "dev") == "dev":
        logger.info("Loading environment variables from @/docker/.env.local")
        env_file_path = "../../docker/env/.env.local"

        if not os.path.exists(env_file_path):
            raise FileNotFoundError(
                f"""Environment file {env_file_path} not found.\n
                    Please create docker/config/secrets/local.env from its safe template,
                    then run ./docker/run.sh dev --config-only (or ./run.sh dev -d from docker)."""
            )

        load_dotenv("../../docker/env/.env.local")
