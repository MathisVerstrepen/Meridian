import os
from urllib.parse import quote

from slowapi import Limiter
from slowapi.util import get_remote_address


def build_redis_storage_uri(host: str, port: int, password: str | None) -> str:
    credentials = f":{quote(password, safe='')}@" if password is not None else ""
    return f"redis://{credentials}{host}:{port}"


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=build_redis_storage_uri(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD"),
    ),
)
