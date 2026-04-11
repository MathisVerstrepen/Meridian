import logging
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


def resolve_model_provider(model_id: str) -> InferenceProviderEnum:
    if model_id.startswith(Z_AI_CODING_PLAN_MODEL_PREFIX):
        return InferenceProviderEnum.Z_AI_CODING_PLAN
    if model_id.startswith(CLAUDE_AGENT_MODEL_PREFIX):
        return InferenceProviderEnum.CLAUDE_AGENT
    if model_id.startswith(GEMINI_CLI_MODEL_PREFIX):
        return InferenceProviderEnum.GEMINI_CLI
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

    z_ai_token_record = await get_provider_token(pg_engine, user_id, Z_AI_CODING_PLAN_PROVIDER_KEY)
    z_ai_coding_plan_api_key = None
    if z_ai_token_record is not None:
        z_ai_coding_plan_api_key = await decrypt_api_key(z_ai_token_record.access_token)

    gemini_token_record = await get_provider_token(pg_engine, user_id, GEMINI_CLI_PROVIDER_KEY)
    gemini_cli_oauth_creds_json = None
    if gemini_token_record is not None:
        gemini_cli_oauth_creds_json = await decrypt_api_key(gemini_token_record.access_token)

    return InferenceCredentials(
        openrouter_api_key=openrouter_api_key,
        claude_agent_oauth_token=claude_agent_oauth_token,
        z_ai_coding_plan_api_key=z_ai_coding_plan_api_key,
        gemini_cli_oauth_creds_json=gemini_cli_oauth_creds_json,
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
    z_ai_coding_plan_api_key = str(getattr(req, "z_ai_api_key", "") or "").strip() or None
    gemini_cli_oauth_creds_json = (
        str(getattr(req, "gemini_oauth_creds_json", "") or "").strip() or None
    )
    return InferenceCredentials(
        openrouter_api_key=openrouter_api_key,
        claude_agent_oauth_token=claude_agent_oauth_token,
        z_ai_coding_plan_api_key=z_ai_coding_plan_api_key,
        gemini_cli_oauth_creds_json=gemini_cli_oauth_creds_json,
    )


async def is_claude_agent_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.claude_agent_oauth_token)


async def is_z_ai_coding_plan_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.z_ai_coding_plan_api_key)


async def is_gemini_cli_connected(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    credentials = await get_user_inference_credentials(pg_engine, user_id)
    return bool(credentials.gemini_cli_oauth_creds_json)


async def get_inference_provider_statuses(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
) -> list[InferenceProviderStatus]:
    return [
        InferenceProviderStatus(
            provider=InferenceProviderEnum.CLAUDE_AGENT,
            label=CLAUDE_AGENT_LABEL,
            isConnected=await is_claude_agent_connected(pg_engine, user_id),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.Z_AI_CODING_PLAN,
            label=Z_AI_CODING_PLAN_LABEL,
            isConnected=await is_z_ai_coding_plan_connected(pg_engine, user_id),
        ),
        InferenceProviderStatus(
            provider=InferenceProviderEnum.GEMINI_CLI,
            label=GEMINI_CLI_LABEL,
            isConnected=await is_gemini_cli_connected(pg_engine, user_id),
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
    openrouter_models = getattr(app.state, "available_models", None)
    normalized_models: list[ModelInfo] = []
    if openrouter_models is not None:
        normalized_models.extend(
            normalize_openrouter_model(model)
            for model in ResponseModel.model_validate(openrouter_models).data
        )

    credentials = await get_user_inference_credentials(app.state.pg_engine, user_id)
    if credentials.claude_agent_oauth_token:
        normalized_models.extend(
            await get_claude_agent_models(oauth_token=credentials.claude_agent_oauth_token)
        )
    if credentials.z_ai_coding_plan_api_key:
        normalized_models.extend(await get_z_ai_coding_plan_models())
    if credentials.gemini_cli_oauth_creds_json:
        normalized_models.extend(await get_gemini_cli_models())

    return ResponseModel(data=normalized_models)


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
    if provider == InferenceProviderEnum.Z_AI_CODING_PLAN:
        return list(Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES)
    if provider == InferenceProviderEnum.GEMINI_CLI:
        return list(GEMINI_CLI_SUPPORTED_TOOL_NAMES)
    return list(MERIDIAN_TOOL_NAMES)
