import ast
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.inference import Architecture, ModelInfo, Pricing, ResponseModel
from services import inference, inference_cache


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.delete_calls: list[str] = []
        self.fail_operations: set[str] = set()

    async def get(self, key: str) -> str | None:
        if "get" in self.fail_operations:
            raise RuntimeError("redis get unavailable")
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        if "set" in self.fail_operations:
            raise RuntimeError("redis set unavailable")
        self.values[key] = value
        self.set_calls.append((key, value, ex))

    async def delete(self, key: str) -> None:
        if "delete" in self.fail_operations:
            raise RuntimeError("redis delete unavailable")
        self.values.pop(key, None)
        self.delete_calls.append(key)


def _manager(redis: FakeRedis) -> Any:
    return SimpleNamespace(client=redis)


def _model(model_id: str = "provider/model") -> ModelInfo:
    return ModelInfo(
        id=model_id,
        name=model_id,
        architecture=Architecture(
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="unknown",
        ),
        pricing=Pricing(prompt="0", completion="0"),
    )


def test_inference_redis_adapter_round_trips_values_with_exact_keys_and_ttls() -> None:
    async def run() -> None:
        redis = FakeRedis()
        manager = _manager(redis)
        credential = "credential-secret"
        user_id = "user-sensitive-id"
        credential_hash = hashlib.sha256(credential.encode()).hexdigest()
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()
        provider_key = inference_cache.build_subscription_models_key("claude-agent", credential)
        response = ResponseModel(data=[_model()])
        available_snapshot = inference_cache.AlibabaOfficialVideoCatalogSnapshot(
            model_ids=("happyhorse-t2v",),
            available=True,
            fingerprint="available-fingerprint",
        )
        unavailable_snapshot = inference_cache.AlibabaOfficialVideoCatalogSnapshot(
            model_ids=(),
            available=False,
            fingerprint="unavailable-fingerprint",
        )

        assert provider_key == (
            "inference:model-catalog:v1:provider:claude-agent:" f"{credential_hash}"
        )
        assert credential not in provider_key
        await inference_cache.write_subscription_models(manager, provider_key, response.data)
        assert (
            await inference_cache.read_subscription_models(manager, provider_key) == response.data
        )

        await inference_cache.write_user_available_models(manager, user_id, response)
        user_key = f"inference:model-catalog:v1:user:{user_hash}"
        assert user_id not in user_key
        assert await inference_cache.read_user_available_models(manager, user_id) == response

        await inference_cache.write_alibaba_official_snapshot(manager, available_snapshot)
        assert await inference_cache.read_alibaba_official_snapshot(manager) == available_snapshot
        await inference_cache.write_alibaba_official_snapshot(manager, unavailable_snapshot)
        assert await inference_cache.read_alibaba_official_snapshot(manager) == unavailable_snapshot

        assert [(key, ex) for key, _, ex in redis.set_calls] == [
            (provider_key, 600),
            (user_key, 60),
            (
                "inference:model-catalog:v1:alibaba-official:official-video-v1",
                600,
            ),
            (
                "inference:model-catalog:v1:alibaba-official:official-video-v1",
                60,
            ),
        ]
        assert credential not in "".join(redis.values)
        assert user_id not in "".join(redis.values)

        await inference_cache.delete_user_available_models(manager, user_id)
        assert redis.delete_calls == [user_key]
        assert await inference_cache.read_user_available_models(manager, user_id) is None

    asyncio.run(run())


def test_inference_redis_alibaba_provider_key_is_hashed_and_versioned() -> None:
    credential = "sk-sp-sensitive"
    credential_hash = hashlib.sha256(credential.encode()).hexdigest()

    key = inference_cache.build_alibaba_subscription_models_key(
        credential,
        "snapshot-fingerprint",
    )

    assert key == (
        "inference:model-catalog:v1:provider:alibaba-token-plan:official-video-v1:"
        f"{credential_hash}:snapshot-fingerprint"
    )
    assert credential not in key


def test_inference_redis_adapter_malformed_and_unavailable_operations_fail_open(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def run() -> None:
        redis = FakeRedis()
        manager = _manager(redis)
        subscription_key = inference_cache.build_subscription_models_key(
            "provider",
            "credential-secret",
        )
        user_key = (
            "inference:model-catalog:v1:user:" + hashlib.sha256(b"user-sensitive-id").hexdigest()
        )
        snapshot_key = "inference:model-catalog:v1:alibaba-official:official-video-v1"
        redis.values[subscription_key] = json.dumps({"not": "models"})
        redis.values[user_key] = "not-json"
        redis.values[snapshot_key] = json.dumps(
            {"model_ids": [1], "available": "yes", "fingerprint": 4}
        )

        assert await inference_cache.read_subscription_models(manager, subscription_key) is None
        assert (
            await inference_cache.read_user_available_models(manager, "user-sensitive-id") is None
        )
        assert await inference_cache.read_alibaba_official_snapshot(manager) is None

        redis.fail_operations = {"get", "set", "delete"}
        assert await inference_cache.read_subscription_models(manager, subscription_key) is None
        await inference_cache.write_subscription_models(manager, subscription_key, [_model()])
        await inference_cache.delete_user_available_models(manager, "user-sensitive-id")

        assert await inference_cache.read_subscription_models(None, subscription_key) is None
        await inference_cache.write_subscription_models(None, subscription_key, [_model()])
        await inference_cache.delete_user_available_models(None, "user-sensitive-id")

    asyncio.run(run())
    assert "credential-secret" not in caplog.text
    assert "user-sensitive-id" not in caplog.text
    assert "inference:model-catalog" not in caplog.text


def test_inference_redis_subscription_values_are_shared_and_empty_policy_is_preserved() -> None:
    async def run() -> None:
        redis = FakeRedis()
        first_app = FastAPI()
        second_app = FastAPI()
        first_app.state.redis_manager = _manager(redis)
        second_app.state.redis_manager = _manager(redis)
        cache_key = inference_cache.build_subscription_models_key(
            "provider",
            "credential-secret",
        )
        first_loader = AsyncMock(return_value=[_model("provider/shared")])
        second_loader = AsyncMock(return_value=[_model("provider/unexpected")])

        first = await inference._get_cached_subscription_models(
            first_app,
            cache_key=cache_key,
            loader=first_loader,
        )
        first[0].name = "mutated"
        second = await inference._get_cached_subscription_models(
            second_app,
            cache_key=cache_key,
            loader=second_loader,
        )

        assert first_loader.await_count == 1
        second_loader.assert_not_awaited()
        assert second[0].id == "provider/shared"
        assert second[0].name == "provider/shared"

        empty_key = inference_cache.build_subscription_models_key("empty", "credential-secret")
        empty_loader = AsyncMock(return_value=[])
        await inference._get_cached_subscription_models(
            first_app,
            cache_key=empty_key,
            loader=empty_loader,
            cache_empty=False,
        )
        assert empty_key not in redis.values

    asyncio.run(run())


def test_inference_redis_user_values_share_across_apps_and_invalidation_rebuilds() -> None:
    async def run() -> None:
        redis = FakeRedis()
        first_app = FastAPI()
        second_app = FastAPI()
        first_app.state.redis_manager = _manager(redis)
        second_app.state.redis_manager = _manager(redis)
        first_response = ResponseModel(data=[_model("provider/first")])
        rebuilt_response = ResponseModel(data=[_model("provider/rebuilt")])
        builder = AsyncMock(side_effect=[first_response, rebuilt_response])

        with patch("services.inference._build_available_models_for_user", new=builder):
            first = await inference.get_available_models_for_user(first_app, "user-sensitive-id")
            shared = await inference.get_available_models_for_user(second_app, "user-sensitive-id")
            await inference.invalidate_user_available_models_cache(
                first_app,
                "user-sensitive-id",
            )
            rebuilt = await inference.get_available_models_for_user(
                second_app,
                "user-sensitive-id",
            )

        assert first.data[0].id == "provider/first"
        assert shared.data[0].id == "provider/first"
        assert rebuilt.data[0].id == "provider/rebuilt"
        assert builder.await_count == 2
        assert not hasattr(first_app.state, "user_available_models_cache")
        assert not hasattr(second_app.state, "user_available_models_cache")

    asyncio.run(run())


def test_inference_redis_malformed_or_unavailable_cache_still_runs_loader() -> None:
    async def run() -> None:
        redis = FakeRedis()
        app = FastAPI()
        app.state.redis_manager = _manager(redis)
        cache_key = inference_cache.build_subscription_models_key(
            "provider",
            "credential-secret",
        )
        redis.values[cache_key] = "malformed"
        redis.fail_operations.add("set")
        loader = AsyncMock(return_value=[_model("provider/fresh")])

        models = await inference._get_cached_subscription_models(
            app,
            cache_key=cache_key,
            loader=loader,
        )

        assert [model.id for model in models] == ["provider/fresh"]
        loader.assert_awaited_once()

        redis.fail_operations = {"get", "set"}
        second_loader = AsyncMock(return_value=[_model("provider/fallback")])
        fallback = await inference._get_cached_subscription_models(
            app,
            cache_key=inference_cache.build_subscription_models_key(
                "provider",
                "second-credential",
            ),
            loader=second_loader,
        )
        assert [model.id for model in fallback] == ["provider/fallback"]

    asyncio.run(run())


def test_inference_redis_local_singleflight_shields_subscription_loader_from_cancellation() -> None:
    async def run() -> None:
        app = FastAPI()
        app.state.redis_manager = _manager(FakeRedis())
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def loader() -> list[ModelInfo]:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return [_model("provider/shared")]

        cache_key = inference_cache.build_subscription_models_key("provider", "credential")
        cancelled_waiter = asyncio.create_task(
            inference._get_cached_subscription_models(
                app,
                cache_key=cache_key,
                loader=loader,
            )
        )
        await started.wait()
        surviving_waiter = asyncio.create_task(
            inference._get_cached_subscription_models(
                app,
                cache_key=cache_key,
                loader=loader,
            )
        )
        await asyncio.sleep(0)
        cancelled_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_waiter
        release.set()
        models = await surviving_waiter
        await asyncio.sleep(0)

        assert calls == 1
        assert [model.id for model in models] == ["provider/shared"]
        assert inference._get_subscription_model_inflight(app) == {}

    asyncio.run(run())


def test_inference_redis_all_provider_invalidation_callers_await() -> None:
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "inference_providers.py"
    tree = ast.parse(router_path.read_text())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "invalidate_user_available_models_cache"
    ]
    awaited_calls = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call)
    }

    assert len(calls) == 14
    assert all(id(call) in awaited_calls for call in calls)
