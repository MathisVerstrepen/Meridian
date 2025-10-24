import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from const.plans import PLAN_LIMITS
from const.settings import DEFAULT_ROUTE_GROUP, DEFAULT_SETTINGS
from database.pg.models import QueryTypeEnum
from database.pg.settings_ops.settings_crud import update_settings
from database.pg.token_ops.refresh_token_crud import (
    delete_all_refresh_tokens_for_user,
    delete_db_refresh_token,
    get_db_refresh_token,
)
from database.pg.user_ops.usage_crud import get_usage_record
from database.pg.user_ops.user_crud import (
    ProviderUserPayload,
    create_user_from_provider,
    get_user_by_id,
    get_user_by_provider_id,
    get_user_by_username,
    update_user_avatar_url,
    update_username,
)
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from models.auth import OAuthSyncResponse, ProviderEnum, UserRead
from models.usersDTO import SettingsDTO
from pydantic import BaseModel, Field, ValidationError
from services.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    handle_password_update,
    handle_refresh_token_theft,
)
from services.crypto import decrypt_api_key, encrypt_api_key, get_password_hash, verify_password
from services.files import (
    create_user_root_folder,
    delete_file_from_disk,
    get_user_storage_path,
    save_file_to_disk,
)
from services.settings import get_user_settings
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)

AVATAR_SUBDIRECTORY = "profile_pictures"
MAX_AVATAR_SIZE_MB = 4
MAX_AVATAR_SIZE_BYTES = MAX_AVATAR_SIZE_MB * 1024 * 1024
ALLOWED_AVATAR_TYPES = ["image/png", "image/jpeg", "image/webp"]


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


class QueryUsageResponse(BaseModel):
    used: int
    total: int
    billing_period_end: datetime


class AllUsageResponse(BaseModel):
    web_search: QueryUsageResponse
    link_extraction: QueryUsageResponse


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
        await create_user_root_folder(pg_engine, db_user.id)
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
            is_admin=db_user.is_admin,
            plan_type=db_user.plan_type,
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
async def req_get_user_settings(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> SettingsDTO:
    """
    Get user settings.

    This endpoint retrieves the user settings from the database.

    Returns:
        SettingsDTO: The user settings.
    """

    settings = await get_user_settings(request.app.state.pg_engine, user_id)

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


@router.post("/user/avatar")
async def upload_avatar(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    file: UploadFile = File(...),
):
    """
    Upload a new profile picture for the user.
    """
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types are: {', '.join(ALLOWED_AVATAR_TYPES)}",
        )

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the limit of {MAX_AVATAR_SIZE_MB}MB.",
        )

    pg_engine = request.app.state.pg_engine
    user = await get_user_by_id(pg_engine, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # If there's an old avatar that is locally stored, delete it.
    old_avatar_filename = user.avatar_url
    if old_avatar_filename and not old_avatar_filename.startswith("http"):
        await delete_file_from_disk(
            uuid.UUID(user_id), old_avatar_filename, subdirectory=AVATAR_SUBDIRECTORY
        )

    # Save the new file
    unique_filename = await save_file_to_disk(
        user_id=uuid.UUID(user_id),
        file_contents=contents,
        original_filename=file.filename or "avatar.png",
        subdirectory=AVATAR_SUBDIRECTORY,
    )

    # Update the user's record
    await update_user_avatar_url(pg_engine, user_id, unique_filename)

    return {"avatarUrl": f"/api/user/avatar?v={uuid.uuid4()}"}  # Return a unique URL


class UpdateUsernamePayload(BaseModel):
    newName: str = Field(
        ..., min_length=3, max_length=50, description="The new username for the user."
    )


@router.post("/user/update-name", response_model=UserRead)
async def req_update_username(
    request: Request,
    payload: UpdateUsernamePayload,
    user_id: str = Depends(get_current_user_id),
):
    """
    Update the current user's username.
    """
    pg_engine = request.app.state.pg_engine
    updated_user = await update_username(pg_engine, user_id, payload.newName)
    return updated_user


@router.get("/user/avatar")
async def get_avatar(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Serve the user's profile picture.
    - If it's an external URL (OAuth), redirect to it.
    - If it's a locally uploaded file, serve it.
    - If no avatar is set, return 404.
    """
    pg_engine = request.app.state.pg_engine
    user = await get_user_by_id(pg_engine, user_id)

    if not user or not user.avatar_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    avatar_url = user.avatar_url
    if avatar_url.startswith("http"):
        return RedirectResponse(url=avatar_url)

    # It's a local file, serve it from the dedicated directory
    user_storage_path = get_user_storage_path(uuid.UUID(user_id))
    avatar_path = os.path.join(user_storage_path, AVATAR_SUBDIRECTORY, avatar_url)

    if not os.path.exists(avatar_path):
        # This case could happen if the file was deleted manually from disk
        # or if there's a data inconsistency.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Avatar file not found on disk"
        )

    return FileResponse(path=avatar_path)


@router.get("/user/usage", response_model=AllUsageResponse)
async def get_user_query_usage(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get the user's query usage for all metered features for the current billing period.
    """

    pg_engine = request.app.state.pg_engine
    user = await get_user_by_id(pg_engine, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    web_search_usage = await get_usage_record(pg_engine, user, QueryTypeEnum.WEB_SEARCH)
    web_search_response = QueryUsageResponse(
        used=web_search_usage.used_queries,
        total=web_search_usage.limit,
        billing_period_end=web_search_usage.billing_period_end,
    )

    link_extraction_usage = await get_usage_record(pg_engine, user, QueryTypeEnum.LINK_EXTRACTION)
    link_extraction_response = QueryUsageResponse(
        used=link_extraction_usage.used_queries,
        total=link_extraction_usage.limit,
        billing_period_end=link_extraction_usage.billing_period_end,
    )

    return AllUsageResponse(
        web_search=web_search_response, link_extraction=link_extraction_response
    )
