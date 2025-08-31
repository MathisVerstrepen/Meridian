import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from const.settings import DEFAULT_ROUTE_GROUP, DEFAULT_SETTINGS
from database.pg.file_ops.file_crud import add_user_file
from database.pg.settings_ops.settings_crud import get_settings, update_settings
from database.pg.token_ops.refresh_token_crud import (
    delete_all_refresh_tokens_for_user,
    delete_db_refresh_token,
    get_db_refresh_token,
)
from database.pg.user_ops.user_crud import (
    ProviderUserPayload,
    create_user_from_provider,
    get_user_by_id,
    get_user_by_provider_id,
    get_user_by_username,
)
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from models.auth import OAuthSyncResponse, ProviderEnum, UserRead
from models.usersDTO import SettingsDTO
from pydantic import BaseModel, ValidationError
from services.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    handle_password_update,
    handle_refresh_token_theft,
)
from services.crypto import decrypt_api_key, encrypt_api_key, get_password_hash, verify_password
from services.files import save_file
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


@router.get("/users/me", response_model=UserRead)
async def read_users_me(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get the profile for the currently authenticated user.
    """
    user = await get_user_by_id(request.app.state.pg_engine, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


class UserPasswordLoginPayload(BaseModel):
    username: str
    password: str
    rememberMe: bool


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: Optional[str] = None


class RefreshRequest(BaseModel):
    refreshToken: str


@router.post("/auth/login")
@limiter.limit("3/minute")
async def login_for_access_token(
    request: Request,
) -> TokenResponse:
    """
    Handles username & password login.
    """
    try:
        payload_data = await request.json()
        payload = UserPasswordLoginPayload(**payload_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or malformed JSON body.",
        )

    db_user = await get_user_by_username(request.app.state.pg_engine, payload.username)

    password_hash = (
        db_user.password
        if db_user and db_user.password
        else get_password_hash("dummy_password_for_timing_attack_mitigation")
    )

    is_password_correct = verify_password(payload.password, password_hash)

    if not db_user or not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Create a short-lived access token
    access_token = create_access_token(data={"sub": str(db_user.id)})

    refresh_token_val = None
    if payload.rememberMe:
        # Create a long-lived refresh token
        refresh_token_val = await create_refresh_token(request.app.state.pg_engine, str(db_user.id))

    return TokenResponse(accessToken=access_token, refreshToken=refresh_token_val)


@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("5/minute")
async def refresh_access_token(
    request: Request,
    body: RefreshRequest,
) -> TokenResponse:
    """
    Exchanges a valid refresh token for a new access and refresh token.
    This implements refresh token rotation for enhanced security.
    """
    pg_engine = request.app.state.pg_engine
    token_str = body.refreshToken

    db_token = await get_db_refresh_token(pg_engine, token_str)

    # Immediately delete the used token to prevent reuse
    if db_token:
        await delete_db_refresh_token(pg_engine, token_str)

    if not db_token or db_token.expires_at < datetime.now(timezone.utc):
        await handle_refresh_token_theft(pg_engine, token_str)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Issue a new set of tokens
    new_access_token = create_access_token(data={"sub": str(db_token.user_id)})
    new_refresh_token = await create_refresh_token(pg_engine, str(db_token.user_id))

    return TokenResponse(accessToken=new_access_token, refreshToken=new_refresh_token)


@router.post("/auth/sync-user/{provider}", response_model=OAuthSyncResponse)
@limiter.limit("5/minute")
async def sync_user(
    request: Request, provider: ProviderEnum, payload: ProviderUserPayload
) -> OAuthSyncResponse:
    """
    Receives user data from Nuxt after Provider OAuth.
    Creates the user if it doesn't exist.
    Returns a secure set of access and refresh tokens.
    """
    pg_engine = request.app.state.pg_engine
    db_user = await get_user_by_provider_id(pg_engine, payload.oauth_id, provider)

    if not db_user:
        db_user = await create_user_from_provider(pg_engine, payload, provider)
        await update_settings(
            pg_engine,
            db_user.id,
            SettingsDTO(
                general=DEFAULT_SETTINGS.general,
                account=DEFAULT_SETTINGS.account,
                appearance=DEFAULT_SETTINGS.appearance,
                models=DEFAULT_SETTINGS.models,
                block=DEFAULT_SETTINGS.block,
                modelsDropdown=DEFAULT_SETTINGS.modelsDropdown,
                blockParallelization=DEFAULT_SETTINGS.blockParallelization,
                blockRouting=DEFAULT_SETTINGS.blockRouting,
            ).model_dump(),
        )

    # Generate both an access token and a refresh token for the session.
    access_token = create_access_token(data={"sub": str(db_user.id)})
    refresh_token = await create_refresh_token(pg_engine, str(db_user.id))

    return OAuthSyncResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        user=UserRead(
            id=db_user.id if db_user.id is not None else uuid.UUID(int=0),
            username=db_user.username,
            email=db_user.email,
            avatar_url=db_user.avatar_url,
            created_at=db_user.created_at if db_user.created_at is not None else datetime.min,
        ),
    )


class ResetPasswordPayload(BaseModel):
    newPassword: str
    oldPassword: str


@router.post("/auth/reset-password")
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    payload: ResetPasswordPayload,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Resets the user's password.

    This endpoint allows the user to reset their password.

    Args:
        payload (ResetPasswordPayload): The payload containing the new password.

    Returns:
        dict: A message indicating the result of the password reset.
    """

    pg_engine = request.app.state.pg_engine
    db_user = await get_user_by_id(pg_engine, user_id)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify old password
    if not verify_password(payload.oldPassword, db_user.password if db_user.password else ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect old password",
        )

    await handle_password_update(pg_engine, user_id, payload.newPassword)

    await delete_all_refresh_tokens_for_user(pg_engine, user_id)

    return {"message": "Password updated successfully and all other sessions logged out."}


@router.get("/user/settings")
async def get_user_settings(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> SettingsDTO:
    """
    Get user settings.

    This endpoint retrieves the user settings from the database.

    Returns:
        SettingsDTO: The user settings.
    """

    user_id_uuid = uuid.UUID(user_id)
    settings_db = await get_settings(request.app.state.pg_engine, str(user_id_uuid))

    settings = SettingsDTO.model_validate(settings_db)

    if settings:
        defaultRouteGroupId = DEFAULT_ROUTE_GROUP.id
        found = False
        for i, group in enumerate(settings.blockRouting.routeGroups):
            if group.id == defaultRouteGroupId:
                settings.blockRouting.routeGroups[i] = DEFAULT_ROUTE_GROUP
            found = True
            break
        if not found:
            settings.blockRouting.routeGroups.insert(0, DEFAULT_ROUTE_GROUP)

        if settings.account.openRouterApiKey:
            settings.account.openRouterApiKey = decrypt_api_key(
                db_payload=settings.account.openRouterApiKey
            )
    else:
        settings = DEFAULT_SETTINGS

    return settings


@router.post("/user/settings")
async def update_user_settings(
    request: Request,
    settings: SettingsDTO,
    user_id: str = Depends(get_current_user_id),
) -> None:
    """
    Update user settings.

    This endpoint updates the user settings in the database.

    Args:
        user_id (uuid.UUID): The ID of the user to update.
        settings (dict): The settings to update.

    Returns:
        UserRead: The updated User object.
    """

    settings.account.openRouterApiKey = encrypt_api_key(settings.account.openRouterApiKey or "")

    user_uuid = uuid.UUID(user_id)
    await update_settings(request.app.state.pg_engine, user_uuid, settings.model_dump())


@router.post("/user/upload-file")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Upload a file for the user.

    This endpoint allows the user to upload a file.

    Args:
        file (UploadFile): The file to upload.

    Returns:
        dict: Information about the uploaded file.
    """
    user_uuid = uuid.UUID(user_id)

    contents = await file.read()

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    if not file.content_type:
        raise HTTPException(status_code=400, detail="Content type is required.")

    id, file_path = await save_file(
        contents,
        file.filename,
    )

    await add_user_file(
        request.app.state.pg_engine,
        id,
        user_uuid,
        file.filename,
        file_path,
        len(contents),
        file.content_type,
    )

    return {
        "id": str(id),
    }
