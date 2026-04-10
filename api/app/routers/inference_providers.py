import logging

from database.pg.token_ops.provider_token_crud import delete_provider_token, store_provider_token
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.inference import ClaudeAgentTokenPayload, InferenceProviderStatusResponse
from services.auth import get_current_user_id
from services.claude_agent import validate_claude_agent_token
from services.crypto import encrypt_api_key
from services.inference import CLAUDE_AGENT_PROVIDER_KEY, get_inference_provider_statuses

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
