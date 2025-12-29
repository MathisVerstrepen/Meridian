import logging
import os
from urllib.parse import urlencode

import httpx
from database.pg.token_ops.provider_token_crud import delete_provider_token, store_provider_token
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.github import GitHubIssue, GitHubStatusResponse, Repo
from pydantic import BaseModel, ValidationError
from services.auth import get_current_user_id
from services.crypto import encrypt_api_key
from services.github import get_github_access_token, list_repo_issues
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.responses import RedirectResponse

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger("uvicorn.error")


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

    params = {
        "client_id": github_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user repo",
    }

    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    return RedirectResponse(auth_url)


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
    Exchanges the temporary code for an OAuth access token and stores it.
    """
    github_client_id = os.getenv("GITHUB_CLIENT_ID")
    github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")

    if not github_client_id or not github_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth is not configured on the server.",
        )

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": github_client_id,
                "client_secret": github_client_secret,
                "code": payload.code,
            },
            headers={"Accept": "application/json"},
        )

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=token_response.status_code,
            detail=f"Failed to exchange code: {token_response.text}",
        )

    token_data = token_response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not retrieve access token: {token_data}",
        )

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        user_response = await client.get("https://api.github.com/user", headers=headers)

    if user_response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch GitHub user profile: {user_response.text}",
        )

    github_user = user_response.json()
    github_username = github_user.get("login")

    encrypted_token = await encrypt_api_key(access_token)
    if not encrypted_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to secure token."
        )

    await store_provider_token(request.app.state.pg_engine, user_id, "github", encrypted_token)

    return {
        "message": "GitHub account connected successfully.",
        "username": github_username,
    }


@router.post("/auth/github/disconnect")
async def disconnect_github_account(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Disconnects the user's GitHub account.
    """
    await delete_provider_token(request.app.state.pg_engine, user_id, "github")

    return {"message": "GitHub account disconnected successfully."}


@router.get("/auth/github/status", response_model=GitHubStatusResponse)
async def get_github_connection_status(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    """
    Checks if the user has a valid GitHub App token.
    """
    try:
        access_token = await get_github_access_token(request, user_id)
    except HTTPException:
        return GitHubStatusResponse(isConnected=False)

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Meridian Github Connector",
        }
        response = await client.get("https://api.github.com/user", headers=headers)

    if response.status_code == 200:
        github_user = response.json()
        return GitHubStatusResponse(isConnected=True, username=github_user.get("login"))
    else:
        return GitHubStatusResponse(isConnected=False)


@router.get("/github/repos", response_model=list[Repo])
async def get_github_repos(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    Fetches repositories using GitHub App permissions via the API.
    """
    access_token = await get_github_access_token(request, user_id)

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Meridian Github Connector",
        }

        params = {
            "per_page": "100",
            "sort": "updated",
            "visibility": "all",
        }

        response = await client.get(
            "https://api.github.com/user/repos", headers=headers, params=params
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch repositories: {response.text}",
        )

    repos_data = response.json()

    try:
        return [Repo.model_validate(repo) for repo in repos_data]
    except ValidationError as e:
        logger.error(f"Error parsing repository data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse repository data: {e}",
        )


@router.get("/github/issues", response_model=list[GitHubIssue])
async def get_github_issues(
    request: Request,
    repo_full_name: str,
    state: str = "open",
    user_id: str = Depends(get_current_user_id),
):
    """
    Fetches issues and pull requests for a specific repository.
    """
    access_token = await get_github_access_token(request, user_id)
    return await list_repo_issues(access_token, repo_full_name, state)
