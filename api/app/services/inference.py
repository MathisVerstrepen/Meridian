import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import FastAPI
from models.inference import (
    BillingTypeEnum,
    InferenceCredentials,
    InferenceProviderEnum,
    InferenceProviderStatus,
    ModelInfo,
    ResponseModel,
)
from models.message import ToolEnum
from services.crypto import decrypt_api_key
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
SUBSCRIPTION_MODEL_CACHE_TTL_SECONDS = 60 * 10
USER_AVAILABLE_MODELS_CACHE_TTL_SECONDS = 60


def _copy_models(models: list[ModelInfo]) -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in models]


def _copy_response_model(response: ResponseModel) -> ResponseModel:
    return ResponseModel(data=_copy_models(response.data))


def _get_subscription_model_cache(
    app: FastAPI,
) -> dict[str, tuple[float, list[ModelInfo]]]:
    cache = getattr(app.state, "subscription_provider_model_cache", None)
    if cache is None:
        cache = {}
        app.state.subscription_provider_model_cache = cache
    return cache


def _get_subscription_model_inflight(
    app: FastAPI,
) -> dict[str, asyncio.Task[list[ModelInfo]]]:
    inflight = getattr(app.state, "subscription_provider_model_inflight", None)
    if inflight is None:
        inflight = {}
        app.state.subscription_provider_model_inflight = inflight
    return inflight


def _get_user_available_models_cache(
    app: FastAPI,
) -> dict[str, tuple[float, ResponseModel]]:
    cache = getattr(app.state, "user_available_models_cache", None)
    if cache is None:
        cache = {}
        app.state.user_available_models_cache = cache
    return cache


def _get_user_available_models_inflight(
    app: FastAPI,
) -> dict[str, asyncio.Task[ResponseModel]]:
    inflight = getattr(app.state, "user_available_models_inflight", None)
    if inflight is None:
        inflight = {}
        app.state.user_available_models_inflight = inflight
    return inflight


def invalidate_user_available_models_cache(app: FastAPI, user_id: str) -> None:
    _get_user_available_models_cache(app).pop(user_id, None)
    _get_user_available_models_inflight(app).pop(user_id, None)


def _build_subscription_model_cache_key(provider_key: str, credential: str) -> str:
    return f"{provider_key}:{hashlib.sha256(credential.encode('utf-8')).hexdigest()}"


async def _get_cached_subscription_models(
    app: FastAPI,
    *,
    cache_key: str,
    loader: Callable[[], Awaitable[list[ModelInfo]]],
) -> list[ModelInfo]:
    cache = _get_subscription_model_cache(app)
    cached_entry = cache.get(cache_key)
    if cached_entry is not None:
        cached_at, cached_models = cached_entry
        if (time.monotonic() - cached_at) < SUBSCRIPTION_MODEL_CACHE_TTL_SECONDS:
            return _copy_models(cached_models)
        cache.pop(cache_key, None)

    inflight = _get_subscription_model_inflight(app)
    existing_task = inflight.get(cache_key)
    if existing_task is not None:
        return _copy_models(await asyncio.shield(existing_task))

    async def _load_models() -> list[ModelInfo]:
        models = await loader()
        cache[cache_key] = (time.monotonic(), _copy_models(models))
        return models

    task = asyncio.create_task(_load_models())
    inflight[cache_key] = task
    task.add_done_callback(
        lambda _: inflight.pop(cache_key, None) if inflight.get(cache_key) is task else None
    )
    return _copy_models(await asyncio.shield(task))


def resolve_model_provider(model_id: str) -> InferenceProviderEnum:
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

    return InferenceCredentials(
        openrouter_api_key=openrouter_api_key,
        claude_agent_oauth_token=claude_agent_oauth_token,
        github_copilot_github_token=github_copilot_github_token,
        z_ai_coding_plan_api_key=z_ai_coding_plan_api_key,
        gemini_cli_oauth_creds_json=gemini_cli_oauth_creds_json,
        openai_codex_auth_json=openai_codex_auth_json,
        opencode_go_api_key=opencode_go_api_key,
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
    return InferenceCredentials(
        openrouter_api_key=openrouter_api_key,
        claude_agent_oauth_token=claude_agent_oauth_token,
        github_copilot_github_token=github_copilot_github_token,
        z_ai_coding_plan_api_key=z_ai_coding_plan_api_key,
        gemini_cli_oauth_creds_json=gemini_cli_oauth_creds_json,
        openai_codex_auth_json=openai_codex_auth_json,
        opencode_go_api_key=opencode_go_api_key,
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
    user_cache = _get_user_available_models_cache(app)
    cached_response = user_cache.get(user_id)
    if cached_response is not None:
        cached_at, response = cached_response
        if (time.monotonic() - cached_at) < USER_AVAILABLE_MODELS_CACHE_TTL_SECONDS:
            return _copy_response_model(response)
        user_cache.pop(user_id, None)

    user_inflight = _get_user_available_models_inflight(app)
    existing_task = user_inflight.get(user_id)
    if existing_task is not None:
        return _copy_response_model(await asyncio.shield(existing_task))

    async def _load_available_models() -> ResponseModel:
        return await _build_available_models_for_user(app, user_id)

    task = asyncio.create_task(_load_available_models())
    user_inflight[user_id] = task
    task.add_done_callback(
        lambda _: user_inflight.pop(user_id, None) if user_inflight.get(user_id) is task else None
    )
    response = await asyncio.shield(task)
    user_cache[user_id] = (time.monotonic(), _copy_response_model(response))
    return _copy_response_model(response)


async def _build_available_models_for_user(app: FastAPI, user_id: str) -> ResponseModel:
    openrouter_models = getattr(app.state, "available_models", None)
    normalized_models: list[ModelInfo] = []
    if openrouter_models is not None:
        normalized_models.extend(
            normalize_openrouter_model(model)
            for model in ResponseModel.model_validate(openrouter_models).data
        )

    credentials = await get_user_inference_credentials(app.state.pg_engine, user_id)
    provider_model_tasks: list[Awaitable[list[ModelInfo]]] = []
    if credentials.claude_agent_oauth_token:
        claude_oauth_token = credentials.claude_agent_oauth_token
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=_build_subscription_model_cache_key(
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
                cache_key=_build_subscription_model_cache_key(
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
                cache_key=_build_subscription_model_cache_key(
                    Z_AI_CODING_PLAN_PROVIDER_KEY,
                    credentials.z_ai_coding_plan_api_key,
                ),
                loader=get_z_ai_coding_plan_models,
            )
        )
    if credentials.gemini_cli_oauth_creds_json:
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=_build_subscription_model_cache_key(
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
                cache_key=_build_subscription_model_cache_key(
                    OPENAI_CODEX_PROVIDER_KEY,
                    openai_codex_auth_json,
                ),
                loader=lambda: get_openai_codex_models_safe(
                    openai_codex_auth_json,
                    user_id=user_id,
                    pg_engine=app.state.pg_engine,
                ),
            )
        )
    if credentials.opencode_go_api_key:
        provider_model_tasks.append(
            _get_cached_subscription_models(
                app,
                cache_key=_build_subscription_model_cache_key(
                    OPENCODE_GO_PROVIDER_KEY,
                    credentials.opencode_go_api_key,
                ),
                loader=get_opencode_go_models,
            )
        )

    if provider_model_tasks:
        for provider_models in await asyncio.gather(*provider_model_tasks):
            normalized_models.extend(provider_models)

    return ResponseModel(data=normalized_models)


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
) -> list[ModelInfo]:
    from services.openai_codex import list_openai_codex_models

    try:
        return await list_openai_codex_models(auth_json, user_id=user_id, pg_engine=pg_engine)
    except Exception:
        logger.warning(
            "OpenAI Codex model discovery failed; omitting Codex models for this request.",
            exc_info=True,
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
    return list(MERIDIAN_TOOL_NAMES)
