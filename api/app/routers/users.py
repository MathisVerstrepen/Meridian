from fastapi import APIRouter, Request
from pydantic import BaseModel
import uuid
import datetime
from typing import Optional

from database.pg.crud import (
    ProviderUserPayload,
    get_user_by_provider_id,
    create_user_from_provider,
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


@router.post("/auth/sync-user/{provider}")
async def sync_user(
    request: Request, provider: str, payload: ProviderUserPayload
) -> SyncUserResponse:
    """
    Receives user data from Nuxt after Provider OAuth.
    Creates the user if it doesn't exist
    """

    db_user = await get_user_by_provider_id(
        request.app.state.pg_engine, payload.oauth_id, provider
    )

    if not db_user:
        new_user = await create_user_from_provider(
            request.app.state.pg_engine, payload, provider
        )
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
        # TODO: check for update in provider username or avatar and update in db
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
