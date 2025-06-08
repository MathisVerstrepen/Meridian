from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
import uuid
import datetime
from typing import Optional

from database.pg.crud import (
    GitHubUserPayload,
    create_github_user,
    get_user_by_github_id,
)

router = APIRouter()


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime.datetime


class SyncUserResponse(BaseModel):
    status: str
    user: UserRead


@router.post("/auth/sync-user")
async def sync_user(request: Request, payload: GitHubUserPayload) -> SyncUserResponse:
    """
    Receives user data from Nuxt after GitHub OAuth.
    Creates the user if it doesn't exist
    """

    db_user = await get_user_by_github_id(
        request.app.state.pg_engine, payload.github_id
    )

    if not db_user:
        new_user = await create_github_user(request.app.state.pg_engine, payload)
        return SyncUserResponse(
            status="created",
            user=UserRead(
                id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                avatar_url=new_user.avatar_url,
                created_at=new_user.created_at,
            ),
        )
    else:
        # TODO: check for update in github username or avatar and update in db
        return SyncUserResponse(
            status="exists",
            user=UserRead(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                avatar_url=db_user.avatar_url,
                created_at=db_user.created_at,
            ),
        )
