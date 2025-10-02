import json
import logging
import os
from typing import Any

import redis.asyncio as redis
import sentry_sdk

logger = logging.getLogger("uvicorn.error")

# Default TTL for cached annotations: 30 days
ANNOTATIONS_TTL_SECONDS = int(os.getenv("REDIS_ANNOTATIONS_TTL_SECONDS", 30 * 24 * 60 * 60))


class RedisManager:
    """A manager class for handling asynchronous Redis operations."""

    def __init__(self, host: str, port: int, password: str | None):
        """
        Initializes the RedisManager and creates a connection pool.

        Args:
            host (str): The Redis server host.
            port (int): The Redis server port.
            password (str | None): The Redis server password.
        """
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                auto_close_connection_pool=False,
                decode_responses=True,  # Decode responses to UTF-8
            )

            logger.info(f"Redis client initialized for host: {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            sentry_sdk.capture_exception(e)
            raise

    async def close(self):
        """Closes the Redis client connection pool."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection pool closed.")

    async def get_annotation(self, remote_hash: str) -> dict[str, Any] | None:
        """
        Retrieves a single file annotation from Redis using OpenRouter's remote hash.

        Args:
            remote_hash (str): The hash of the file content as provided by OpenRouter.

        Returns:
            dict[str, Any] | None: The deserialized annotation, or None if not found.
        """
        if not remote_hash:
            return None
        key = f"annotation:{remote_hash}"
        try:
            cached_data = await self.client.get(key)
            if cached_data:
                return json.loads(cached_data)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Redis GET (annotation) failed for key {key}: {e}")
            sentry_sdk.capture_exception(e)
        return None

    async def set_annotation(self, remote_hash: str, annotation: dict[str, Any]):
        """
        Serializes and stores a single file annotation in Redis.

        Args:
            remote_hash (str): The hash of the file content as provided by OpenRouter.
            annotation (dict[str, Any]): The annotation data to cache.
        """
        if not remote_hash:
            return
        key = f"annotation:{remote_hash}"
        try:
            serialized_data = json.dumps(annotation)
            await self.client.set(key, serialized_data, ex=ANNOTATIONS_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Redis SET (annotation) failed for key {key}: {e}")
            sentry_sdk.capture_exception(e)

    async def get_remote_hash(self, local_hash: str) -> str | None:
        """
        Retrieves the remote hash using the local hash from the map.

        Args:
            local_hash (str): The locally computed SHA-256 hash of the file.

        Returns:
            str | None: The corresponding remote hash, or None if not found.
        """
        if not local_hash:
            return None
        key = f"hash_map:{local_hash}"
        try:
            result = await self.client.get(key)
            return result if result is None else str(result)
        except Exception as e:
            logger.error(f"Redis GET (hash_map) failed for key {key}: {e}")
            sentry_sdk.capture_exception(e)
        return None

    async def set_hash_mapping(self, local_hash: str, remote_hash: str):
        """
        Stores the mapping from a local hash to a remote hash.

        Args:
            local_hash (str): The locally computed SHA-256 hash of the file.
            remote_hash (str): The hash provided by OpenRouter.
        """
        if not local_hash or not remote_hash:
            return
        key = f"hash_map:{local_hash}"
        try:
            await self.client.set(key, remote_hash, ex=ANNOTATIONS_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Redis SET (hash_map) failed for key {key}: {e}")
            sentry_sdk.capture_exception(e)
