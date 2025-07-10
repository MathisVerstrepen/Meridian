from dotenv import load_dotenv
import logging
import os

from const.settings import DEFAULT_SETTINGS

logger = logging.getLogger("uvicorn.error")


def load_environment_variables():
    if os.getenv("ENV", "dev") == "dev":
        logger.info("Loading environment variables from @/docker/.env.local")
        env_file_path = "../../docker/env/.env.local"

        if not os.path.exists(env_file_path):
            raise FileNotFoundError(f"""Environment file {env_file_path} not found.\n
                    Please create a config.local.toml file in the docker folder and run ./run.sh dev -d""")

        load_dotenv("../../docker/env/.env.local")


DEFAULT_SETTINGS_DICT = DEFAULT_SETTINGS.model_dump()


def complete_settings_dict(settings_dict: dict) -> dict:
    """
    Ensures a settings dictionary has all required top-level keys,
    adding them from defaults if they are missing.

    Args:
        settings_dict (dict): The settings dictionary to complete.

    Returns:
        dict: The completed settings dictionary.
    """
    for key, default_value in DEFAULT_SETTINGS_DICT.items():
        if key not in settings_dict or not settings_dict.get(key):
            settings_dict[key] = default_value

    return settings_dict
