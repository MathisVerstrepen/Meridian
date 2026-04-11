import logging

from database.pg.token_ops.provider_token_crud import delete_provider_token, store_provider_token
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.inference import (
    ClaudeAgentTokenPayload,
    GeminiCliOAuthCredsPayload,
    InferenceProviderStatusResponse,
    ZAiCodingPlanApiKeyPayload,
)
from services.auth import get_current_user_id
from services.claude_agent import validate_claude_agent_token
from services.crypto import encrypt_api_key
from services.gemini_cli import validate_gemini_cli_oauth_creds_json
from services.inference import get_inference_provider_statuses
from services.providers.claude_agent_catalog import CLAUDE_AGENT_PROVIDER_KEY
from services.providers.gemini_cli_catalog import GEMINI_CLI_PROVIDER_KEY
from services.providers.z_ai_coding_plan_catalog import Z_AI_CODING_PLAN_PROVIDER_KEY
from services.z_ai_coding_plan import validate_z_ai_coding_plan_api_key

router = APIRouter(prefix="/inference/providers", tags=["inference-providers"])
logger = logging.getLogger("uvicorn.error")


@router.get("/status", response_model=InferenceProviderStatusResponse)
async def get_inference_statuses(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return InferenceProviderStatusResponse(
        providers=await get_inference_provider_statuses(request.app.state.pg_engine, user_id)
    )


@router.post("/claude-agent/token")
async def connect_claude_agent(
    request: Request,
    payload: ClaudeAgentTokenPayload,
    user_id: str = Depends(get_current_user_id),
):
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is required.")

    try:
        await validate_claude_agent_token(token)
        encrypted_token = await encrypt_api_key(token)
        if not encrypted_token:
            raise ValueError("Failed to encrypt Claude Agent token.")

        await store_provider_token(
            request.app.state.pg_engine,
            user_id,
            CLAUDE_AGENT_PROVIDER_KEY,
            encrypted_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to connect Claude Agent for user %s", user_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not validate or store the Claude Agent token.",
        ) from exc

    return {"message": "Claude Agent connected successfully."}


@router.delete("/claude-agent/token")
async def disconnect_claude_agent(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    await delete_provider_token(request.app.state.pg_engine, user_id, CLAUDE_AGENT_PROVIDER_KEY)
    return {"message": "Claude Agent disconnected successfully."}


@router.post("/z-ai-coding-plan/api-key")
async def connect_z_ai_coding_plan(
    request: Request,
    payload: ZAiCodingPlanApiKeyPayload,
    user_id: str = Depends(get_current_user_id),
):
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required.",
        )

    try:
        await validate_z_ai_coding_plan_api_key(
            api_key,
            http_client=request.app.state.http_client,
        )
        encrypted_api_key = await encrypt_api_key(api_key)
        if not encrypted_api_key:
            raise ValueError("Failed to encrypt Z.AI Coding Plan API key.")

        await store_provider_token(
            request.app.state.pg_engine,
            user_id,
            Z_AI_CODING_PLAN_PROVIDER_KEY,
            encrypted_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to connect Z.AI Coding Plan for user %s", user_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not validate or store the Z.AI Coding Plan API key.",
        ) from exc

    return {"message": "Z.AI Coding Plan connected successfully."}


@router.delete("/z-ai-coding-plan/api-key")
async def disconnect_z_ai_coding_plan(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    await delete_provider_token(
        request.app.state.pg_engine,
        user_id,
        Z_AI_CODING_PLAN_PROVIDER_KEY,
    )
    return {"message": "Z.AI Coding Plan disconnected successfully."}


@router.post("/gemini-cli/oauth-creds")
async def connect_gemini_cli(
    request: Request,
    payload: GeminiCliOAuthCredsPayload,
    user_id: str = Depends(get_current_user_id),
):
    oauth_creds_json = payload.oauth_creds_json.strip()
    if not oauth_creds_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth credentials JSON is required.",
        )

    try:
        normalized_oauth_creds_json = await validate_gemini_cli_oauth_creds_json(oauth_creds_json)
        encrypted_oauth_creds = await encrypt_api_key(normalized_oauth_creds_json)
        if not encrypted_oauth_creds:
            raise ValueError("Failed to encrypt Gemini CLI OAuth credentials.")

        await store_provider_token(
            request.app.state.pg_engine,
            user_id,
            GEMINI_CLI_PROVIDER_KEY,
            encrypted_oauth_creds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to connect Gemini CLI for user %s", user_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not validate or store the Gemini CLI OAuth credentials.",
        ) from exc

    return {"message": "Gemini CLI connected successfully."}


@router.delete("/gemini-cli/oauth-creds")
async def disconnect_gemini_cli(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    await delete_provider_token(request.app.state.pg_engine, user_id, GEMINI_CLI_PROVIDER_KEY)
    return {"message": "Gemini CLI disconnected successfully."}
