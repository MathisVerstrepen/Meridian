from dotenv import load_dotenv
import logging
import os

logger = logging.getLogger("uvicorn.error")


def load_environment_variables():
    if os.getenv("ENV", "dev") == "dev":
        logger.info("Loading environment variables from @/docker/.env.local")
        env_file_path = "../../docker/env/.env.local"

        if not os.path.exists(env_file_path):
            raise FileNotFoundError(f"""Environment file {env_file_path} not found.\n
                    Please create a config.local.toml file in the docker folder and run ./run.sh dev -d""")

        load_dotenv("../../docker/env/.env.local")
