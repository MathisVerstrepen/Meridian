import os
from dotenv import load_dotenv


def load_environment_variables():
    if os.getenv("ENV", "dev") == "dev":
        print("Loading environment variables from .env.local")
        load_dotenv("../.env.local")
