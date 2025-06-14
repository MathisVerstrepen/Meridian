from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from typing import Optional
from pydantic import BaseModel
import datetime
import uuid
import json

from models.usersDTO import SettingsDTO
from services.files import save_file
from const.settings import DEFAULT_SETTINGS

from database.pg.crud import (
    ProviderUserPayload,
    get_user_by_provider_id,
    create_user_from_provider,
    update_settings,
    get_settings,
    add_user_file,
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
        await update_settings(
            request.app.state.pg_engine,
            new_user.id,
            SettingsDTO(
                user_id=new_user.id,
                general=DEFAULT_SETTINGS.general,
                models=DEFAULT_SETTINGS.models,
                modelsDropdown=DEFAULT_SETTINGS.modelsDropdown,
                blockParallelization=DEFAULT_SETTINGS.blockParallelization,
            ).model_dump_json(),
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


@router.get("/user/settings")
async def get_user_settings(request: Request) -> SettingsDTO:
    """
    Get user settings.

    This endpoint retrieves the user settings from the database.

    Returns:
        SettingsDTO: The user settings.
    """

    user_id_header = request.headers.get("X-User-ID")

    if not user_id_header:
        raise ValueError("X-User-ID header is required")

    user_id = uuid.UUID(user_id_header)
    settings = await get_settings(request.app.state.pg_engine, user_id)

    return (
        SettingsDTO.model_validate_json(settings.settings_data)
        if settings
        else SettingsDTO(user_id=user_id, settings_data=json.dumps({}))
    )


@router.post("/user/settings")
async def update_user_settings(request: Request, settings: SettingsDTO) -> None:
    """
    Update user settings.

    This endpoint updates the user settings in the database.

    Args:
        user_id (uuid.UUID): The ID of the user to update.
        settings (dict): The settings to update.

    Returns:
        UserRead: The updated User object.
    """

    user_id_header = request.headers.get("X-User-ID")

    if not user_id_header:
        raise ValueError("X-User-ID header is required")

    user_id = uuid.UUID(user_id_header)
    await update_settings(
        request.app.state.pg_engine, user_id, settings.model_dump_json()
    )


@router.post("/user/upload-file")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload a file for the user.

    This endpoint allows the user to upload a file.

    Args:
        file (UploadFile): The file to upload.

    Returns:
        dict: Information about the uploaded file.
    """
    user_id_header = request.headers.get("X-User-ID")
    if not user_id_header:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    user_id = uuid.UUID(user_id_header)

    contents = await file.read()

    id, file_path = await save_file(
        contents,
        file.filename,
    )

    await add_user_file(
        request.app.state.pg_engine,
        id,
        user_id,
        file.filename,
        file_path,
        len(contents),
        file.content_type,
    )

    return {
        "id": str(id),
    }
