import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from database.redis.redis_ops import RedisManager
from models.inference import ModelInfo, ResponseModel
from pydantic import TypeAdapter

logger = logging.getLogger("uvicorn.error")

SUBSCRIPTION_MODEL_CACHE_TTL_SECONDS = 60 * 10
USER_AVAILABLE_MODELS_CACHE_TTL_SECONDS = 60
ALIBABA_OFFICIAL_CATALOG_SUCCESS_TTL_SECONDS = 60 * 10
ALIBABA_OFFICIAL_CATALOG_FAILURE_TTL_SECONDS = 60
ALIBABA_OFFICIAL_CATALOG_CACHE_VERSION = "official-video-v1"

_CACHE_NAMESPACE = "inference:model-catalog:v1"
_SUBSCRIPTION_MODELS_ADAPTER = TypeAdapter(list[ModelInfo])


@dataclass(frozen=True)
class AlibabaOfficialVideoCatalogSnapshot:
    model_ids: tuple[str, ...]
    available: bool
    fingerprint: str


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_subscription_models_key(provider_key: str, credential: str) -> str:
    return f"{_CACHE_NAMESPACE}:provider:{provider_key}:{_sha256_hex(credential)}"


def build_alibaba_subscription_models_key(
    credential: str,
    snapshot_fingerprint: str,
) -> str:
    return (
        f"{_CACHE_NAMESPACE}:provider:alibaba-token-plan:"
        f"{ALIBABA_OFFICIAL_CATALOG_CACHE_VERSION}:{_sha256_hex(credential)}:"
        f"{snapshot_fingerprint}"
    )


def _user_available_models_key(user_id: str) -> str:
    return f"{_CACHE_NAMESPACE}:user:{_sha256_hex(user_id)}"


def _alibaba_official_snapshot_key() -> str:
    return f"{_CACHE_NAMESPACE}:alibaba-official:" f"{ALIBABA_OFFICIAL_CATALOG_CACHE_VERSION}"


def _log_cache_failure(cache_kind: str, operation: str, exc: Exception) -> None:
    logger.warning(
        "Inference Redis cache %s %s failed (%s).",
        cache_kind,
        operation,
        type(exc).__name__,
    )


async def _read_json(
    redis_manager: RedisManager | None,
    *,
    key: str,
    cache_kind: str,
) -> Any | None:
    if redis_manager is None:
        return None
    try:
        payload = await redis_manager.client.get(key)
        if payload is None:
            return None
        return json.loads(payload)
    except Exception as exc:
        _log_cache_failure(cache_kind, "GET", exc)
        return None


async def _write_json(
    redis_manager: RedisManager | None,
    *,
    key: str,
    value: Any,
    ttl_seconds: int,
    cache_kind: str,
) -> None:
    if redis_manager is None:
        return
    try:
        await redis_manager.client.set(
            key,
            json.dumps(value),
            ex=ttl_seconds,
        )
    except Exception as exc:
        _log_cache_failure(cache_kind, "SET", exc)


async def read_subscription_models(
    redis_manager: RedisManager | None,
    cache_key: str,
) -> list[ModelInfo] | None:
    payload = await _read_json(
        redis_manager,
        key=cache_key,
        cache_kind="subscription models",
    )
    if payload is None:
        return None
    try:
        return _SUBSCRIPTION_MODELS_ADAPTER.validate_python(payload)
    except Exception as exc:
        _log_cache_failure("subscription models", "validation", exc)
        return None


async def write_subscription_models(
    redis_manager: RedisManager | None,
    cache_key: str,
    models: list[ModelInfo],
) -> None:
    await _write_json(
        redis_manager,
        key=cache_key,
        value=[model.model_dump(mode="json") for model in models],
        ttl_seconds=SUBSCRIPTION_MODEL_CACHE_TTL_SECONDS,
        cache_kind="subscription models",
    )


async def read_user_available_models(
    redis_manager: RedisManager | None,
    user_id: str,
) -> ResponseModel | None:
    payload = await _read_json(
        redis_manager,
        key=_user_available_models_key(user_id),
        cache_kind="user models",
    )
    if payload is None:
        return None
    try:
        return ResponseModel.model_validate(payload)
    except Exception as exc:
        _log_cache_failure("user models", "validation", exc)
        return None


async def write_user_available_models(
    redis_manager: RedisManager | None,
    user_id: str,
    response: ResponseModel,
) -> None:
    await _write_json(
        redis_manager,
        key=_user_available_models_key(user_id),
        value=response.model_dump(mode="json"),
        ttl_seconds=USER_AVAILABLE_MODELS_CACHE_TTL_SECONDS,
        cache_kind="user models",
    )


async def delete_user_available_models(
    redis_manager: RedisManager | None,
    user_id: str,
) -> None:
    if redis_manager is None:
        return
    try:
        await redis_manager.client.delete(_user_available_models_key(user_id))
    except Exception as exc:
        _log_cache_failure("user models", "DEL", exc)


async def read_alibaba_official_snapshot(
    redis_manager: RedisManager | None,
) -> AlibabaOfficialVideoCatalogSnapshot | None:
    payload = await _read_json(
        redis_manager,
        key=_alibaba_official_snapshot_key(),
        cache_kind="Alibaba official snapshot",
    )
    if payload is None:
        return None
    try:
        if not isinstance(payload, dict):
            raise TypeError("snapshot must be an object")
        model_ids = payload.get("model_ids")
        available = payload.get("available")
        fingerprint = payload.get("fingerprint")
        if not isinstance(model_ids, list) or not all(
            isinstance(model_id, str) for model_id in model_ids
        ):
            raise TypeError("model_ids must be strings")
        if not isinstance(available, bool):
            raise TypeError("available must be boolean")
        if not isinstance(fingerprint, str):
            raise TypeError("fingerprint must be a string")
        return AlibabaOfficialVideoCatalogSnapshot(
            model_ids=tuple(model_ids),
            available=available,
            fingerprint=fingerprint,
        )
    except Exception as exc:
        _log_cache_failure("Alibaba official snapshot", "validation", exc)
        return None


async def write_alibaba_official_snapshot(
    redis_manager: RedisManager | None,
    snapshot: AlibabaOfficialVideoCatalogSnapshot,
) -> None:
    ttl_seconds = (
        ALIBABA_OFFICIAL_CATALOG_SUCCESS_TTL_SECONDS
        if snapshot.available
        else ALIBABA_OFFICIAL_CATALOG_FAILURE_TTL_SECONDS
    )
    await _write_json(
        redis_manager,
        key=_alibaba_official_snapshot_key(),
        value={
            "model_ids": list(snapshot.model_ids),
            "available": snapshot.available,
            "fingerprint": snapshot.fingerprint,
        },
        ttl_seconds=ttl_seconds,
        cache_kind="Alibaba official snapshot",
    )
