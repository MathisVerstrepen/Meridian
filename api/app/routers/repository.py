import pybase64 as base64
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.github import GitHubIssue
from models.repository import GitCommitState, RepositoryInfo
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.rate_limit import limiter
from services.repository_clone_service import clone_repository
from services.repository_service import get_repository_branches
from services.repository_service import (
    get_repository_commit_state as get_repository_commit_state_service,
)
from services.repository_service import (
    get_repository_file_content,
    get_repository_issues,
    get_repository_tree,
)
from services.repository_service import (
    list_available_repositories as list_available_repositories_service,
)
from services.repository_service import pull_repository as pull_repository_service

router = APIRouter()


class ClonePayload(BaseModel):
    provider: str
    full_name: str
    clone_url: str
    clone_method: str


def decode_provider(encoded_provider: str) -> str:
    try:
        return base64.urlsafe_b64decode(encoded_provider).decode()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider encoding.",
        ) from exc


@router.get("/repositories", response_model=list[RepositoryInfo])
@limiter.limit("30/minute")
async def list_available_repositories(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    return await list_available_repositories_service(request, user_id)


@router.post("/repositories/clone", status_code=status.HTTP_201_CREATED)
@limiter.limit("2/minute")
async def clone_repository_endpoint(
    request: Request,
    payload: ClonePayload,
    user_id: str = Depends(get_current_user_id),
):
    return await clone_repository(
        request,
        user_id,
        payload.provider,
        payload.full_name,
        payload.clone_url,
        payload.clone_method,
    )


@router.get("/repositories/{encoded_provider}/{project_path:path}/branches")
@limiter.limit("10/minute")
async def get_repo_branches(
    encoded_provider: str,
    project_path: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await get_repository_branches(
        request, user_id, decode_provider(encoded_provider), project_path
    )


@router.get("/repositories/{encoded_provider}/{project_path:path}/tree")
@limiter.limit("30/minute")
async def get_repo_tree(
    encoded_provider: str,
    project_path: str,
    branch: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await get_repository_tree(
        request, user_id, decode_provider(encoded_provider), project_path, branch
    )


@router.get("/repositories/{encoded_provider}/{project_path:path}/content/{file_path:path}")
@limiter.limit("60/minute")
async def get_repo_file_content(
    encoded_provider: str,
    project_path: str,
    branch: str,
    file_path: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await get_repository_file_content(
        request,
        user_id,
        decode_provider(encoded_provider),
        project_path,
        branch,
        file_path,
    )


@router.post("/repositories/{encoded_provider}/{project_path:path}/pull")
@limiter.limit("5/minute")
async def pull_repository(
    encoded_provider: str,
    project_path: str,
    branch: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await pull_repository_service(
        request, user_id, decode_provider(encoded_provider), project_path, branch
    )


@router.get(
    "/repositories/{encoded_provider}/{project_path:path}/issues",
    response_model=list[GitHubIssue],
)
@limiter.limit("20/minute")
async def get_repo_issues(
    encoded_provider: str,
    project_path: str,
    request: Request,
    state: str = "open",
    user_id: str = Depends(get_current_user_id),
):
    return await get_repository_issues(
        request,
        user_id,
        decode_provider(encoded_provider),
        project_path,
        state,
    )


@router.get(
    "/repositories/{encoded_provider}/{project_path:path}/commit-state",
    response_model=GitCommitState,
)
@limiter.limit("20/minute")
async def get_repository_commit_state(
    encoded_provider: str,
    project_path: str,
    branch: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    return await get_repository_commit_state_service(
        request, user_id, decode_provider(encoded_provider), project_path, branch
    )
