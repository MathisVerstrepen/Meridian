import json
import logging

from database.pg.token_ops.provider_token_crud import (
    delete_provider_token,
    get_provider_token,
    store_provider_token,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, constr
from services.auth import get_current_user_id
from services.crypto import encrypt_api_key

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


class GitLabConnectPayload(BaseModel):
    personal_access_token: constr(strip_whitespace=True, min_length=10)
    private_key: constr(strip_whitespace=True, min_length=50)


class GitLabStatusResponse(BaseModel):
    isConnected: bool


@router.post("/auth/gitlab/connect")
async def connect_gitlab_account(
    request: Request,
    payload: GitLabConnectPayload,
    user_id: str = Depends(get_current_user_id),
):
    """
    Connects a user's GitLab account by storing an encrypted Personal Access Token
    and an SSH private key.
    """
    if not payload.private_key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid SSH key format. Must be an OpenSSH private key.",
        )

    try:
        encrypted_pat = await encrypt_api_key(payload.personal_access_token)
        encrypted_ssh_key = await encrypt_api_key(payload.private_key)

        if not encrypted_pat or not encrypted_ssh_key:
            raise ValueError("Encryption failed for one or both keys.")

        # Store both encrypted keys in a single JSON object
        token_payload = json.dumps({"pat": encrypted_pat, "ssh_key": encrypted_ssh_key})

        await store_provider_token(
            request.app.state.pg_engine,
            user_id,
            "gitlab",
            token_payload,
        )
        return {"message": "GitLab account connected successfully."}
    except Exception as e:
        logger.error(f"Failed to connect GitLab account for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store GitLab credentials.",
        )


@router.post("/auth/gitlab/disconnect")
async def disconnect_gitlab_account(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Disconnects the user's GitLab account by deleting the stored credentials.
    """
    await delete_provider_token(request.app.state.pg_engine, user_id, "gitlab")
    return {"message": "GitLab account disconnected successfully."}


@router.get("/auth/gitlab/status", response_model=GitLabStatusResponse)
async def get_gitlab_connection_status(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    """
    Checks if the user has GitLab credentials stored.
    """
    token = await get_provider_token(request.app.state.pg_engine, user_id, "gitlab")
    return GitLabStatusResponse(isConnected=token is not None)
