from fastapi import APIRouter, HTTPException, status, Depends, Request
import os
from starlette.responses import RedirectResponse
from pydantic import BaseModel
import httpx
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.auth import get_current_user_id
from services.crypto import encrypt_api_key
from database.pg.token_ops.provider_token_crud import store_github_token_for_user

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


@router.get("/auth/github/login")
async def github_login():
    """
    Redirects the user to GitHub to authorize the application.
    This is the first step in the OAuth flow.
    """
    github_client_id = os.getenv("GITHUB_CLIENT_ID")
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI")

    if not github_client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth is not configured on the server.",
        )

    scopes = "repo read:user"

    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={github_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&response_type=code"
    )

    return RedirectResponse(url=auth_url)


class GitHubCallbackPayload(BaseModel):
    code: str


@router.post("/auth/github/callback")
@limiter.limit("5/minute")
async def github_callback(
    request: Request,
    payload: GitHubCallbackPayload,
    user_id: str = Depends(get_current_user_id),
):
    """
    Handles the callback from GitHub after user authorization.
    Exchanges the temporary code for a permanent access token and stores it.
    """
    github_client_id = os.getenv("GITHUB_CLIENT_ID")
    github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")

    if not github_client_id or not github_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth is not configured on the server.",
        )

    # Exchange the code for an access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": github_client_id,
                "client_secret": github_client_secret,
                "code": payload.code,
            },
            headers={"Accept": "application/json"},
        )

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange code for access token.",
        )

    token_data = token_response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not retrieve access token from GitHub. Response: {token_data.get('error_description')}",
        )

    # Encrypt and store the token for the user
    encrypted_token = encrypt_api_key(access_token)
    user_id_uuid = uuid.UUID(user_id)

    await store_github_token_for_user(
        request.app.state.pg_engine, user_id_uuid, encrypted_token
    )

    return {"message": "GitHub account connected successfully."}
