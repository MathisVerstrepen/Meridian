import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import FastAPI
from models.inference import (
    BillingTypeEnum,
    InferenceCredentials,
    InferenceProviderEnum,
    InferenceProviderStatus,
    ModelDiscoveryWarning,
    ModelInfo,
    ResponseModel,
)
from models.message import ToolEnum
from services.crypto import decrypt_api_key
from services.inference_cache import (
    ALIBABA_OFFICIAL_CATALOG_CACHE_VERSION,
    AlibabaOfficialVideoCatalogSnapshot,
    build_alibaba_subscription_models_key,
    build_subscription_models_key,
    delete_user_available_models,
    read_alibaba_official_snapshot,
    read_subscription_models,
    read_user_available_models,
    write_alibaba_official_snapshot,
    write_subscription_models,
    write_user_available_models,
)
from services.providers.alibaba_token_plan_catalog import (
    ALIBABA_TOKEN_PLAN_LABEL,
    ALIBABA_TOKEN_PLAN_MODEL_PREFIX,
    ALIBABA_TOKEN_PLAN_PROVIDER_KEY,
    ALIBABA_TOKEN_PLAN_SUPPORTED_TOOL_NAMES,
    build_alibaba_token_plan_models_from_models_dev,
    get_alibaba_token_plan_models,
)
from services.providers.alibaba_token_plan_official_catalog import (
    fetch_alibaba_token_plan_official_video_model_ids,
)
from services.providers.claude_agent_catalog import (
    CLAUDE_AGENT_LABEL,
    CLAUDE_AGENT_MODEL_PREFIX,
    CLAUDE_AGENT_PROVIDER_KEY,
    CLAUDE_AGENT_SUPPORTED_TOOL_NAMES,
    get_claude_agent_models,
)
from services.providers.gemini_cli_catalog import (
    GEMINI_CLI_LABEL,
    GEMINI_CLI_MODEL_PREFIX,
    GEMINI_CLI_PROVIDER_KEY,
    GEMINI_CLI_SUPPORTED_TOOL_NAMES,
    get_gemini_cli_models,
)
from services.providers.github_copilot_catalog import (
    GITHUB_COPILOT_LABEL,
    GITHUB_COPILOT_MODEL_PREFIX,
    GITHUB_COPILOT_PROVIDER_KEY,
    GITHUB_COPILOT_SUPPORTED_TOOL_NAMES,
)
from services.providers.openai_codex_catalog import (
    OPENAI_CODEX_LABEL,
    OPENAI_CODEX_MODEL_PREFIX,
    OPENAI_CODEX_PROVIDER_KEY,
    OPENAI_CODEX_SUPPORTED_TOOL_NAMES,
)
from services.providers.opencode_go_catalog import (
    OPENCODE_GO_LABEL,
    OPENCODE_GO_MODEL_PREFIX,
    OPENCODE_GO_PROVIDER_KEY,
    OPENCODE_GO_SUPPORTED_TOOL_NAMES,
    get_opencode_go_models,
)
from services.providers.z_ai_coding_plan_catalog import (
    Z_AI_CODING_PLAN_LABEL,
    Z_AI_CODING_PLAN_MODEL_PREFIX,
    Z_AI_CODING_PLAN_PROVIDER_KEY,
    Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES,
    get_z_ai_coding_plan_models,
)
from services.settings import get_user_settings
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

MERIDIAN_TOOL_NAMES = [tool.value for tool in ToolEnum]


def _copy_models(models: list[ModelInfo]) -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in models]


def _copy_response_model(response: ResponseModel) -> ResponseModel:
    return ResponseModel(
        data=_copy_models(response.data),
        warnings=[warning.model_copy(deep=True) for warning in response.warnings],
    )


def _get_subscription_model_inflight(
    app: FastAPI,
) -> dict[str, asyncio.Task[list[ModelInfo]]]:
    inflight = getattr(app.state, "subscription_provider_model_inflight", None)
    if inflight is None:
        inflight = {}
        app.state.subscription_provider_model_inflight = inflight
    return inflight


def _get_user_available_models_inflight(
    app: FastAPI,
) -> dict[str, asyncio.Task[ResponseModel]]:
    inflight = getattr(app.state, "user_available_models_inflight", None)
    if inflight is None:
        inflight = {}
        app.state.user_available_models_inflight = inflight
    return inflight


async def invalidate_user_available_models_cache(app: FastAPI, user_id: str) -> None:
    _get_user_available_models_inflight(app).pop(user_id, None)
    await delete_user_available_models(getattr(app.state, "redis_manager", None), user_id)


async def _get_cached_subscription_models(
    app: FastAPI,
    *,
    cache_key: str,
    loader: Callable[[], Awaitable[list[ModelInfo]]],
    cache_empty: bool = True,
) -> list[ModelInfo]:
    redis_manager = getattr(app.state, "redis_manager", None)
    cached_models = await read_subscription_models(redis_manager, cache_key)
    if cached_models is not None:
        return _copy_models(cached_models)

    inflight = _get_subscription_model_inflight(app)
    existing_task = inflight.get(cache_key)
    if existing_task is not None:
        return _copy_models(await asyncio.shield(existing_task))

    async def _load_models() -> list[ModelInfo]:
        models = await loader()
        if models or cache_empty:
            await write_subscription_models(redis_manager, cache_key, models)
        return models

    task = asyncio.create_task(_load_models())
    inflight[cache_key] = task
    task.add_done_callback(
        lambda _: inflight.pop(cache_key, None) if inflight.get(cache_key) is task else None
    )
    return _copy_models(await asyncio.shield(task))


def _build_alibaba_official_snapshot(
    model_ids: list[str], *, available: bool
) -> AlibabaOfficialVideoCatalogSnapshot:
    sorted_ids = tuple(sorted(model_ids))
    fingerprint_payload = "\0".join(
        [
            ALIBABA_OFFICIAL_CATALOG_CACHE_VERSION,
            "available" if available else "unavailable",
            *sorted_ids,
        ]
    )
    return AlibabaOfficialVideoCatalogSnapshot(
        model_ids=sorted_ids,
        available=available,
        fingerprint=hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
    )


async def _get_alibaba_official_video_catalog_snapshot(
    app: FastAPI,
) -> AlibabaOfficialVideoCatalogSnapshot:
    redis_manager = getattr(app.state, "redis_manager", None)
    cached_snapshot = await read_alibaba_official_snapshot(redis_manager)
    if cached_snapshot is not None:
        return cached_snapshot

    existing_task = getattr(
        app.state,
        "alibaba_token_plan_official_video_catalog_inflight",
        None,
    )
    if isinstance(existing_task, asyncio.Task):
        return await asyncio.shield(existing_task)

    async def _load_snapshot() -> AlibabaOfficialVideoCatalogSnapshot:
        try:
            model_ids = await fetch_alibaba_token_plan_official_video_model_ids(
                app.state.http_client
            )
            snapshot = _build_alibaba_official_snapshot(model_ids, available=True)
        except Exception as exc:
            logger.warning(
                "Alibaba Token Plan official video catalog discovery failed (%s).",
                type(exc).__name__,
            )
            snapshot = _build_alibaba_official_snapshot([], available=False)
        await write_alibaba_official_snapshot(redis_manager, snapshot)
        return snapshot

    task = asyncio.create_task(_load_snapshot())
    app.state.alibaba_token_plan_official_video_catalog_inflight = task

    def _clear_inflight(_: asyncio.Task[AlibabaOfficialVideoCatalogSnapshot]) -> None:
        if (
            getattr(
                app.state,
                "alibaba_token_plan_official_video_catalog_inflight",
                None,
            )
            is task
        ):
            app.state.alibaba_token_plan_official_video_catalog_inflight = None

    task.add_done_callback(_clear_inflight)
    return await asyncio.shield(task)


async def _get_cached_alibaba_token_plan_models(
    app: FastAPI,
    *,
    api_key: str,
) -> list[ModelInfo]:
    snapshot = await _get_alibaba_official_video_catalog_snapshot(app)
    return await _get_cached_subscription_models(
        app,
        cache_key=build_alibaba_subscription_models_key(api_key, snapshot.fingerprint),
        loader=lambda: get_alibaba_token_plan_models_safe(
            models_dev_catalog=getattr(app.state, "models_dev_catalog", None),
            api_key=api_key,
            http_client=app.state.http_client,
            official_video_model_ids=list(snapshot.model_ids),
        ),
        cache_empty=False,
    )


def resolve_model_provider(model_id: str) -> InferenceProviderEnum:
    if model_id.startswith(ALIBABA_TOKEN_PLAN_MODEL_PREFIX):
        return InferenceProviderEnum.ALIBABA_TOKEN_PLAN
    if model_id.startswith(Z_AI_CODING_PLAN_MODEL_PREFIX):
        return InferenceProviderEnum.Z_AI_CODING_PLAN
    if model_id.startswith(CLAUDE_AGENT_MODEL_PREFIX):
        return InferenceProviderEnum.CLAUDE_AGENT
    if model_id.startswith(GITHUB_COPILOT_MODEL_PREFIX):
        return InferenceProviderEnum.GITHUB_COPILOT
    if model_id.startswith(GEMINI_CLI_MODEL_PREFIX):
        return InferenceProviderEnum.GEMINI_CLI
    if model_id.startswith(OPENAI_CODEX_MODEL_PREFIX):
        return InferenceProviderEnum.OPENAI_CODEX
    if model_id.startswith(OPENCODE_GO_MODEL_PREFIX):
        return InferenceProviderEnum.OPENCODE_GO
    return InferenceProviderEnum.OPENROUTER


async def get_user_inference_credentials(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
) -> InferenceCredentials:
    settings = await get_user_settings(pg_engine, user_id)

    openrouter_api_key = await decrypt_api_key(
        db_payload=settings.account.openRouterApiKey or "",
    )
    claude_token_record = await get_provider_token(pg_engine, user_id, CLAUDE_AGENT_PROVIDER_KEY)
    claude_agent_oauth_token = None
    if claude_token_record is not None:
        claude_agent_oauth_token = await decrypt_api_key(claude_token_record.access_token)

    github_copilot_token_record = await get_provider_token(
        pg_engine,
        user_id,
        GITHUB_COPILOT_PROVIDER_KEY,
    )
    github_copilot_github_token = None
    if github_copilot_token_record is not None:
        github_copilot_github_token = await decrypt_api_key(
            github_copilot_token_record.access_token
        )

    z_ai_token_record = await get_provider_token(pg_engine, user_id, Z_AI_CODING_PLAN_PROVIDER_KEY)
    z_ai_coding_plan_api_key = None
    if z_ai_token_record is not None:
        z_ai_coding_plan_api_key = await decrypt_api_key(z_ai_token_record.access_token)

    gemini_token_record = await get_provider_token(pg_engine, user_id, GEMINI_CLI_PROVIDER_KEY)
    gemini_cli_oauth_creds_json = None
    if gemini_token_record is not None:
        gemini_cli_oauth_creds_json = await decrypt_api_key(gemini_token_record.access_token)

    openai_codex_token_record = await get_provider_token(
        pg_engine, user_id, OPENAI_CODEX_PROVIDER_KEY
    )
    openai_codex_auth_json = None
    if openai_codex_token_record is not None:
        openai_codex_auth_json = await decrypt_api_key(openai_codex_token_record.access_token)

    opencode_go_token_record = await get_provider_token(
        pg_engine, user_id, OPENCODE_GO_PROVIDER_KEY
    )
    opencode_go_api_key = None
    if opencode_go_token_record is not None:
        opencode_go_api_key = await decrypt_api_key(opencode_go_token_record.access_token)

    alibaba_token_record = await get_provider_token(
        pg_engine,
        user_id,
        ALIBABA_TOKEN_PLAN_PROVIDER_KEY,
    )
    alibaba_token_plan_api_key = None
    if alibaba_token_record is not None:
        alibaba_token_plan_api_key = await decrypt_api_key(alibaba_token_record.access_token)

    return InferenceCredentials(
        openrouter_api_key=openrouter_api_key,
        claude_agent_oauth_token=claude_agent_oauth_token,
        github_copilot_github_token=github_copilot_github_token,
        z_ai_coding_plan_api_key=z_ai_coding_plan_api_key,
        gemini_cli_oauth_creds_json=gemini_cli_oauth_creds_json,
        openai_codex_auth_json=openai_codex_auth_json,
        opencode_go_api_key=opencode_go_api_key,
        alibaba_token_plan_api_key=alibaba_token_plan_api_key,
    )


async def get_request_inference_credentials(req: Any) -> InferenceCredentials:
    pg_engine = getattr(req, "pg_engine", None)
    user_id = getattr(req, "user_id", None)
    if pg_engine is not None and user_id:
        try:
            return await get_user_inference_credentials(pg_engine, str(user_id))
        except Exception:
            logger.warning(
                "Falling back to request-scoped inference credentials for user %s",
                user_id,
                exc_info=True,
            )

    openrouter_api_key = str(getattr(req, "api_key", "") or "").strip() or None
    if openrouter_api_key is None:
        headers = getattr(req, "headers", None)
        if isinstance(headers, dict):
            authorization = str(headers.get("Authorization", "") or "")
            if authorization.startswith("Bearer "):
                openrouter_api_key = authorization[len("Bearer ") :].strip() or None

    claude_agent_oauth_token = str(getattr(req, "oauth_token", "") or "").strip() or None
    github_copilot_github_token = str(getattr(req, "github_token", "") or "").strip() or None
    z_ai_coding_plan_api_key = str(getattr(req, "z_ai_api_key", "") or "").strip() or None
    gemini_cli_oauth_creds_json = str(getattr(req, "oauth_creds_json", "") or "").strip() or None
    openai_codex_auth_json = str(getattr(req, "openai_codex_auth_json", "") or "").strip() or None
    opencode_go_api_key = str(getattr(req, "opencode_go_api_key", "") or "").strip() or None
    alibaba_token_plan_api_key = (
        str(getattr(req, "alibaba_token_plan_api_key", "") or "").strip() or None
    )
    return InferenceCredentials(
        openrouter_api_key=openrouter_api_key,
        claude_agent_oauth_token=claude_agent_oauth_token,
        github_copilot_github_token=github_copilot_github_token,
        z_ai_coding_plan_api_key=z_ai_coding_plan_api_key,
        gemini_cli_oauth_creds_json=gemini_cli_oauth_creds_json,
        openai_codex_auth_json=openai_codex_auth_json,
        opencode_go_api_key=opencode_go_api_key,
        alibaba_token_plan_api_key=alibaba_token_plan_api_key,
    )


async def is_claude_agent_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.claude_agent_oauth_token)


async def is_z_ai_coding_plan_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.z_ai_coding_plan_api_key)


async def is_github_copilot_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.github_copilot_github_token)


async def is_gemini_cli_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.gemini_cli_oauth_creds_json)


async def is_openai_codex_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.openai_codex_auth_json)


async def is_opencode_go_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.opencode_go_api_key)


async def is_alibaba_token_plan_connected(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.alibaba_token_plan_api_key)


async def get_inference_provider_statuses(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
) -> list[InferenceProviderStatus]:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return [
        InferenceProviderStatus(
            provider=InferenceProviderEnum.CLAUDE_AGENT,
            label=CLAUDE_AGENT_LABEL,
            isConnected=bool(credentials.claude_agent_oauth_token),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.Z_AI_CODING_PLAN,
            label=Z_AI_CODING_PLAN_LABEL,
            isConnected=bool(credentials.z_ai_coding_plan_api_key),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.GITHUB_COPILOT,
            label=GITHUB_COPILOT_LABEL,
            isConnected=bool(credentials.github_copilot_github_token),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.GEMINI_CLI,
            label=GEMINI_CLI_LABEL,
            isConnected=bool(credentials.gemini_cli_oauth_creds_json),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.OPENAI_CODEX,
            label=OPENAI_CODEX_LABEL,
            isConnected=bool(credentials.openai_codex_auth_json),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.OPENCODE_GO,
            label=OPENCODE_GO_LABEL,
            isConnected=bool(credentials.opencode_go_api_key),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.ALIBABA_TOKEN_PLAN,
            label=ALIBABA_TOKEN_PLAN_LABEL,
            isConnected=bool(credentials.alibaba_token_plan_api_key),
        ),
    ]


def normalize_openrouter_model(model: ModelInfo) -> ModelInfo:
    return model.model_copy(
        update={
            "provider": InferenceProviderEnum.OPENROUTER,
            "billingType": BillingTypeEnum.METERED,
            "requiresConnection": False,
            "supportsStructuredOutputs": True,
            "supportsMeridianTools": model.toolsSupport,
            "supportedMeridianToolNames": MERIDIAN_TOOL_NAMES if model.toolsSupport else [],
        }
    )


async def get_available_models_for_user(app: FastAPI, user_id: str) -> ResponseModel:
    redis_manager = getattr(app.state, "redis_manager", None)
    cached_response = await read_user_available_models(redis_manager, user_id)
    if cached_response is not None:
        return _copy_response_model(cached_response)

    user_inflight = _get_user_available_models_inflight(app)
    existing_task = user_inflight.get(user_id)
    if existing_task is not None:
        return _copy_response_model(await asyncio.shield(existing_task))

    async def _load_available_models() -> ResponseModel:
        response = await _build_available_models_for_user(app, user_id)
        await write_user_available_models(redis_manager, user_id, response)
        return response

    task = asyncio.create_task(_load_available_models())
    user_inflight[user_id] = task
    task.add_done_callback(
        lambda _: user_inflight.pop(user_id, None) if user_inflight.get(user_id) is task else None
    )
    response = await asyncio.shield(task)
    return _copy_response_model(response)


async def _build_available_models_for_user(app: FastAPI, user_id: str) -> ResponseModel:
    openrouter_models = getattr(app.state, "available_models", None)
    normalized_models: list[ModelInfo] = []
    warnings: list[ModelDiscoveryWarning] = []
    if openrouter_models is not None:
        normalized_models.extend(
            normalize_openrouter_model(model)
            for model in ResponseModel.model_validate(openrouter_models).data
        )

    credentials = await get_user_inference_credentials(app.state.pg_engine, user_id)
    provider_model_tasks: list[Awaitable[list[ModelInfo]]] = []
    alibaba_models_task: Awaitable[list[ModelInfo]] | None = None
    if credentials.claude_agent_oauth_token:
        claude_oauth_token = credentials.claude_agent_oauth_token
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=build_subscription_models_key(
                    CLAUDE_AGENT_PROVIDER_KEY,
                    claude_oauth_token,
                ),
                loader=lambda: get_claude_agent_models(oauth_token=claude_oauth_token),
            )
        )
    if credentials.github_copilot_github_token:
        github_copilot_token = credentials.github_copilot_github_token
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=build_subscription_models_key(
                    GITHUB_COPILOT_PROVIDER_KEY,
                    github_copilot_token,
                ),
                loader=lambda: get_github_copilot_models_safe(github_copilot_token),
            )
        )
    if credentials.z_ai_coding_plan_api_key:
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=build_subscription_models_key(
                    Z_AI_CODING_PLAN_PROVIDER_KEY,
                    credentials.z_ai_coding_plan_api_key,
                ),
                loader=lambda: get_z_ai_coding_plan_models(
                    getattr(app.state, "models_dev_catalog", None)
                ),
            )
        )
    if credentials.gemini_cli_oauth_creds_json:
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=build_subscription_models_key(
                    GEMINI_CLI_PROVIDER_KEY,
                    credentials.gemini_cli_oauth_creds_json,
                ),
                loader=get_gemini_cli_models,
            )
        )
    if credentials.openai_codex_auth_json:
        openai_codex_auth_json = credentials.openai_codex_auth_json
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=build_subscription_models_key(
                    OPENAI_CODEX_PROVIDER_KEY,
                    openai_codex_auth_json,
                ),
                loader=lambda: get_openai_codex_models_safe(
                    openai_codex_auth_json,
                    user_id=user_id,
                    pg_engine=app.state.pg_engine,
                    models_dev_catalog=getattr(app.state, "models_dev_catalog", None),
                    warnings=warnings,
                ),
                cache_empty=False,
            )
        )
    if credentials.opencode_go_api_key:
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=build_subscription_models_key(
                    OPENCODE_GO_PROVIDER_KEY,
                    credentials.opencode_go_api_key,
                ),
                loader=lambda: get_opencode_go_models(
                    getattr(app.state, "models_dev_catalog", None)
                ),
            )
        )
    if credentials.alibaba_token_plan_api_key:
        alibaba_api_key = credentials.alibaba_token_plan_api_key
        alibaba_models_task = _get_cached_alibaba_token_plan_models(
            app,
            api_key=alibaba_api_key,
        )
        provider_model_tasks.append(alibaba_models_task)

    if provider_model_tasks:
        provider_results = await asyncio.gather(*provider_model_tasks)
        for provider_models in provider_results:
            normalized_models.extend(provider_models)
        if alibaba_models_task is not None:
            alibaba_models = provider_results[provider_model_tasks.index(alibaba_models_task)]
            if not alibaba_models:
                warnings.append(
                    ModelDiscoveryWarning(
                        provider=InferenceProviderEnum.ALIBABA_TOKEN_PLAN,
                        title="Alibaba Token Plan models unavailable",
                        message=(
                            "Meridian could not load compatible models for this connection. "
                            "Try refreshing or reconnecting the provider."
                        ),
                        actionLabel="Open provider settings",
                        actionUrl="/settings?tab=providers",
                    )
                )

    return ResponseModel(data=normalized_models, warnings=warnings)


async def get_alibaba_token_plan_models_safe(
    *,
    models_dev_catalog: Any | None,
    api_key: str,
    http_client: Any,
    official_video_model_ids: list[str] | None = None,
) -> list[ModelInfo]:
    try:
        return await get_alibaba_token_plan_models(
            models_dev_catalog,
            api_key=api_key,
            http_client=http_client,
            official_video_model_ids=official_video_model_ids,
        )
    except Exception as exc:
        logger.warning(
            "Alibaba Token Plan model discovery failed; omitting models (%s).",
            type(exc).__name__,
        )
        return build_alibaba_token_plan_models_from_models_dev(
            models_dev_catalog,
            [],
            official_video_model_ids,
        )


async def get_github_copilot_models_safe(github_token: str) -> list[ModelInfo]:
    from services.github_copilot import list_github_copilot_models

    try:
        return await list_github_copilot_models(github_token)
    except Exception:
        logger.warning(
            "GitHub Copilot model discovery failed; omitting Copilot models for this request.",
            exc_info=True,
        )
        return []


async def get_openai_codex_models_safe(
    auth_json: str,
    *,
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    models_dev_catalog: Any | None = None,
    warnings: list[ModelDiscoveryWarning] | None = None,
) -> list[ModelInfo]:
    from services.openai_codex import list_openai_codex_models

    try:
        return await list_openai_codex_models(
            auth_json,
            user_id=user_id,
            pg_engine=pg_engine,
            models_dev_catalog=models_dev_catalog,
        )
    except Exception as exc:
        logger.warning(
            "OpenAI Codex model discovery failed; omitting Codex models for this request.",
            exc_info=True,
        )
        if warnings is not None:
            warnings.append(
                ModelDiscoveryWarning(
                    provider=InferenceProviderEnum.OPENAI_CODEX,
                    title="OpenAI Codex needs reconnecting",
                    message=str(exc),
                    actionLabel="Open provider settings",
                    actionUrl="/settings?tab=providers",
                )
            )
        return []


def model_supports_structured_outputs(
    model_id: str | None,
    available_models: list[dict[str, Any]] | list[ModelInfo] | None,
) -> bool:
    if not model_id or not available_models:
        return False

    model = next(
        (
            item
            for item in available_models
            if (
                (isinstance(item, dict) and item.get("id") == model_id)
                or (not isinstance(item, dict) and getattr(item, "id", None) == model_id)
            )
        ),
        None,
    )
    if model is None:
        return False
    if isinstance(model, dict):
        return bool(model.get("supportsStructuredOutputs", False))
    return bool(getattr(model, "supportsStructuredOutputs", False))


def model_supports_image_inspection(
    model_id: str | None,
    available_models: list[dict[str, Any]] | list[ModelInfo] | None,
) -> bool:
    if not model_id or not available_models:
        return False
    if resolve_model_provider(model_id) not in {
        InferenceProviderEnum.OPENROUTER,
        InferenceProviderEnum.GEMINI_CLI,
        InferenceProviderEnum.OPENAI_CODEX,
        InferenceProviderEnum.OPENCODE_GO,
    }:
        return False

    model = next(
        (
            item
            for item in available_models
            if (
                (isinstance(item, dict) and item.get("id") == model_id)
                or (not isinstance(item, dict) and getattr(item, "id", None) == model_id)
            )
        ),
        None,
    )
    if model is None:
        return False
    if isinstance(model, dict):
        architecture = model.get("architecture")
        modalities = (
            architecture.get("input_modalities", []) if isinstance(architecture, dict) else []
        )
        supports_tools = bool(model.get("supportsMeridianTools", False))
        tool_names = model.get("supportedMeridianToolNames", [])
    else:
        modalities = getattr(model.architecture, "input_modalities", [])
        supports_tools = bool(getattr(model, "supportsMeridianTools", False))
        tool_names = getattr(model, "supportedMeridianToolNames", [])
    return (
        "image" in modalities and supports_tools and ToolEnum.IMAGE_GENERATION.value in tool_names
    )


def get_supported_meridian_tool_names(model_id: str) -> list[str]:
    provider = resolve_model_provider(model_id)
    if provider == InferenceProviderEnum.CLAUDE_AGENT:
        return list(CLAUDE_AGENT_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.GITHUB_COPILOT:
        return list(GITHUB_COPILOT_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.Z_AI_CODING_PLAN:
        return list(Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.GEMINI_CLI:
        return list(GEMINI_CLI_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.OPENAI_CODEX:
        return list(OPENAI_CODEX_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.OPENCODE_GO:
        return list(OPENCODE_GO_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.ALIBABA_TOKEN_PLAN:
        return list(ALIBABA_TOKEN_PLAN_SUPPORTED_TOOL_NAMES)
    return list(MERIDIAN_TOOL_NAMES)
