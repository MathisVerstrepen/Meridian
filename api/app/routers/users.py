import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

import sentry_sdk
from const.settings import DEFAULT_ROUTE_GROUP, DEFAULT_SETTINGS
from database.pg.admin_ops.admin_usage_crud import get_admin_usage_dashboard
from database.pg.auth_ops.verification_crud import (
    delete_verification_tokens_for_user,
    get_verification_token,
    mark_user_as_verified,
)
from database.pg.models import QueryTypeEnum, User
from database.pg.settings_ops.settings_crud import update_settings
from database.pg.token_ops.refresh_token_crud import (
    delete_all_refresh_tokens_for_user,
    delete_db_refresh_token,
    get_db_refresh_token,
)
from database.pg.user_ops.storage_crud import get_storage_usage
from database.pg.user_ops.usage_crud import get_usage_record, reset_usage_record
from database.pg.user_ops.user_crud import (
    count_admin_users,
    create_user_from_provider,
    create_user_with_password,
    delete_user_by_id,
    get_all_users_paginated,
    get_user_by_email,
    get_user_by_id,
    get_user_by_provider_id,
    get_user_by_username,
    mark_user_as_welcomed,
    update_user_admin_status,
    update_user_avatar_url,
    update_user_email,
    update_user_plan,
    update_user_suspension,
    update_username,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse
from models.adminDTO import AdminUsageDashboardResponse, AdminUserListItem, AdminUserListResponse
from models.auth import OAuthLoginPayload, OAuthSyncResponse, ProviderEnum, UserRead
from models.usersDTO import SettingsDTO
from pydantic import BaseModel, EmailStr, Field, ValidationError
from services.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    handle_password_update,
    handle_refresh_token_theft,
    raise_if_user_suspended,
    trigger_user_verification,
)
from services.crypto import decrypt_api_key, encrypt_api_key, get_password_hash, verify_password
from services.files import (
    create_user_root_folder,
    delete_file_from_disk,
    delete_user_storage,
    get_user_storage_path,
    save_file_to_disk,
)
from services.oauth import verify_oauth_login
from services.rate_limit import limiter
from services.settings import get_user_settings

router = APIRouter()

AVATAR_SUBDIRECTORY = "profile_pictures"
MAX_AVATAR_SIZE_MB = 4
MAX_AVATAR_SIZE_BYTES = MAX_AVATAR_SIZE_MB * 1024 * 1024
ALLOWED_AVATAR_TYPES = ["image/png", "image/jpeg", "image/webp"]


async def _delete_user_account_data(request: Request, user_id: str) -> None:
    """
    Delete the user's database record and all on-disk storage.
    """
    pg_engine = request.app.state.pg_engine
    await delete_user_by_id(pg_engine, user_id)

    if not await delete_user_storage(user_id):
        sentry_sdk.capture_message(
            f"User {user_id} was deleted from the database but storage cleanup failed.",
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deleted, but storage cleanup failed.",
        )


async def require_admin(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> User:
    """Dependency to ensure the current user is an admin."""
    pg_engine = request.app.state.pg_engine
    user = await get_user_by_id(pg_engine, user_id)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return user


def _to_admin_user_list_item(user: User) -> AdminUserListItem:
    if not user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return AdminUserListItem(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        oauth_provider=user.oauth_provider,
        plan_type=user.plan_type,
        is_verified=user.is_verified,
        is_admin=user.is_admin,
        is_suspended=user.is_suspended,
        suspended_reason=user.suspended_reason,
        suspended_until=user.suspended_until,
        created_at=user.created_at or datetime.min,
    )


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


class UserRegisterPayload(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: Optional[str] = None


class QueryUsageResponse(BaseModel):
    used: int
    total: int
    billing_period_end: datetime


class StorageUsageBreakdownResponse(BaseModel):
    category: str
    used_bytes: int
    file_count: int


class StorageUsageResponse(BaseModel):
    used_bytes: int
    limit_bytes: int
    percentage: float
    breakdown: list[StorageUsageBreakdownResponse]


class AllUsageResponse(BaseModel):
    web_search: QueryUsageResponse
    link_extraction: QueryUsageResponse
    storage: StorageUsageResponse


class AdminUpdateUserPlanPayload(BaseModel):
    plan_type: Literal["free", "premium"]


class AdminUpdateUserSuspensionPayload(BaseModel):
    is_suspended: bool
    suspended_reason: str | None = Field(None, max_length=500)
    suspended_until: datetime | None = None


class AdminUpdateUserRolePayload(BaseModel):
    is_admin: bool


def _normalize_suspended_until(suspended_until: datetime | None) -> datetime | None:
    if suspended_until is None:
        return None

    if suspended_until.tzinfo is None:
        suspended_until = suspended_until.replace(tzinfo=timezone.utc)

    if suspended_until <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="suspended_until must be in the future",
        )

    return suspended_until


async def _get_usage_response(pg_engine, user: User) -> AllUsageResponse:
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

    storage_usage = await get_storage_usage(pg_engine, user)
    storage_response = StorageUsageResponse(
        used_bytes=storage_usage.used_bytes,
        limit_bytes=storage_usage.limit_bytes,
        percentage=storage_usage.percentage,
        breakdown=[
            StorageUsageBreakdownResponse(
                category=item.category,
                used_bytes=item.used_bytes,
                file_count=item.file_count,
            )
            for item in storage_usage.breakdown
        ],
    )

    return AllUsageResponse(
        web_search=web_search_response,
        link_extraction=link_extraction_response,
        storage=storage_response,
    )


class RefreshRequest(BaseModel):
    refreshToken: str


class VerifyEmailPayload(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationPayload(BaseModel):
    email: EmailStr


class UpdateUnverifiedEmailPayload(BaseModel):
    username: str
    password: str
    email: EmailStr


@router.post("/auth/register")
@limiter.limit("3/minute")
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Register a new user with username, email, and password.
    Now requires email verification before issuing tokens.
    """
    try:
        payload_data = await request.json()
        payload = UserRegisterPayload(**payload_data)
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

    pg_engine = request.app.state.pg_engine

    # Hash the password
    hashed_password = await get_password_hash(payload.password)

    # Create the user in DB (will raise 409 if exists)
    db_user = await create_user_with_password(
        pg_engine,
        username=payload.username,
        email=payload.email,
        hashed_password=hashed_password,
    )

    # Initialize user resources (folders, settings)
    await create_user_root_folder(pg_engine, db_user.id)
    await update_settings(
        pg_engine,
        db_user.id,
        DEFAULT_SETTINGS.model_dump(),
    )

    await trigger_user_verification(pg_engine, background_tasks, db_user.id, payload.email)

    return {"message": "Verification email sent"}


@router.post("/auth/verify-email")
@limiter.limit("5/minute")
async def verify_email(request: Request, payload: VerifyEmailPayload) -> TokenResponse:
    """
    Verifies the email address using the code sent.
    """
    pg_engine = request.app.state.pg_engine

    token_record = await get_verification_token(pg_engine, payload.email, payload.code)

    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    if token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired")

    db_user = await mark_user_as_verified(pg_engine, token_record.user_id)

    await delete_verification_tokens_for_user(pg_engine, token_record.user_id)

    raise_if_user_suspended(db_user)

    access_token = create_access_token(data={"sub": str(db_user.id)})
    refresh_token_val = await create_refresh_token(pg_engine, str(db_user.id))

    return TokenResponse(accessToken=access_token, refreshToken=refresh_token_val)


@router.post("/auth/resend-verification")
@limiter.limit("1/minute")
async def resend_verification_email(
    request: Request, payload: ResendVerificationPayload, background_tasks: BackgroundTasks
) -> dict:
    """
    Resends the verification email if the user exists and is not verified.
    """
    pg_engine = request.app.state.pg_engine

    user = await get_user_by_email(pg_engine, payload.email, "userpass")

    if not user:
        return {"message": "If the email exists, a code has been sent."}

    if user.is_verified:
        return {"message": "Account already verified."}

    await trigger_user_verification(pg_engine, background_tasks, user.id, payload.email)

    return {"message": "Verification code resent"}


@router.post("/auth/update-unverified-email")
@limiter.limit("3/minute")
async def update_unverified_user_email(
    request: Request, payload: UpdateUnverifiedEmailPayload, background_tasks: BackgroundTasks
) -> dict:
    """
    Updates the email for a user who is not yet verified or has no email.
    Verifies credentials, updates email, and triggers verification email.
    """
    pg_engine = request.app.state.pg_engine

    db_user = await get_user_by_username(pg_engine, payload.username)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    password_hash = (
        db_user.password
        if db_user.password
        else await get_password_hash("dummy_password_for_timing_attack_mitigation")
    )
    is_password_correct = await verify_password(payload.password, password_hash)

    if not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if db_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already verified",
        )

    if db_user.id is None:
        raise HTTPException(status_code=500, detail="User ID is None")

    await update_user_email(pg_engine, str(db_user.id), payload.email)

    await trigger_user_verification(pg_engine, background_tasks, db_user.id, payload.email)

    return {"message": "Email updated and verification code sent"}


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
        else await get_password_hash("dummy_password_for_timing_attack_mitigation")
    )

    is_password_correct = await verify_password(payload.password, password_hash)

    if not db_user or not is_password_correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    raise_if_user_suspended(db_user)

    if not db_user.is_verified and db_user.oauth_provider == "userpass":
        if not db_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email required",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
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

    db_user = await get_user_by_id(pg_engine, str(db_token.user_id))
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    raise_if_user_suspended(db_user)

    # Issue a new set of tokens
    new_access_token = create_access_token(data={"sub": str(db_token.user_id)})
    new_refresh_token = await create_refresh_token(pg_engine, str(db_token.user_id))

    return TokenResponse(accessToken=new_access_token, refreshToken=new_refresh_token)


@router.post("/auth/sync-user/{provider}", response_model=OAuthSyncResponse)
@limiter.limit("5/minute")
async def sync_user(
    request: Request, provider: ProviderEnum, payload: OAuthLoginPayload
) -> OAuthSyncResponse:
    """
    Verifies provider-issued OAuth credentials on the server.
    Creates the user if it doesn't exist.
    Returns a secure set of access and refresh tokens.
    """
    if provider == ProviderEnum.USERPASS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported OAuth provider.",
        )

    pg_engine = request.app.state.pg_engine
    verified_profile = await verify_oauth_login(provider, payload)
    db_user = await get_user_by_provider_id(pg_engine, verified_profile.oauth_id, provider)

    if not db_user:
        db_user = await create_user_from_provider(pg_engine, verified_profile, provider)
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
        # OAuth users are implicitly verified by the provider
        if not db_user.is_verified:
            if db_user.id is None:
                raise HTTPException(status_code=500, detail="User ID is None")
            await mark_user_as_verified(pg_engine, db_user.id)

    raise_if_user_suspended(db_user)

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
            is_verified=db_user.is_verified,
            has_seen_welcome=db_user.has_seen_welcome,
            oauth_provider=db_user.oauth_provider,
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
    if not await verify_password(payload.oldPassword, db_user.password if db_user.password else ""):
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
        settings.account.openRouterApiKey = await decrypt_api_key(
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

    settings.account.openRouterApiKey = await encrypt_api_key(
        settings.account.openRouterApiKey or ""
    )

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


@router.post("/user/ack-welcome")
async def ack_welcome(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Acknowledge that the user has seen the welcome popup.
    """
    pg_engine = request.app.state.pg_engine
    await mark_user_as_welcomed(pg_engine, user_id)
    return {"message": "Welcome acknowledged"}


@router.get("/user/avatar")
async def get_avatar(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Serve the user's profile picture.
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

    storage_usage = await get_storage_usage(pg_engine, user)
    storage_response = StorageUsageResponse(
        used_bytes=storage_usage.used_bytes,
        limit_bytes=storage_usage.limit_bytes,
        percentage=storage_usage.percentage,
        breakdown=[
            StorageUsageBreakdownResponse(
                category=item.category,
                used_bytes=item.used_bytes,
                file_count=item.file_count,
            )
            for item in storage_usage.breakdown
        ],
    )

    return AllUsageResponse(
        web_search=web_search_response,
        link_extraction=link_extraction_response,
        storage=storage_response,
    )


@router.delete("/user/me")
async def delete_me(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Allow the authenticated user to delete their own account.
    """
    await _delete_user_account_data(request, user_id)
    return {"message": "Account deleted successfully"}


@router.get("/admin/users", response_model=AdminUserListResponse)
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, min_length=1, max_length=255),
    provider: ProviderEnum | None = Query(None),
    plan_type: str | None = Query(None, pattern="^(free|premium)$"),
    is_verified: bool | None = Query(None),
    is_admin: bool | None = Query(None),
    is_suspended: bool | None = Query(None),
    joined_from: date | None = Query(None),
    joined_to: date | None = Query(None),
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: List all users with pagination.
    """
    if joined_from and joined_to and joined_from > joined_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="joined_from cannot be after joined_to",
        )

    pg_engine = request.app.state.pg_engine
    users, total = await get_all_users_paginated(
        pg_engine,
        page,
        limit,
        search=search.strip() if search else None,
        provider=provider.value if provider else None,
        plan_type=plan_type,
        is_verified=is_verified,
        is_admin=is_admin,
        is_suspended=is_suspended,
        joined_from=joined_from,
        joined_to=joined_to,
    )

    users_dto = [_to_admin_user_list_item(u) for u in users if u.id]

    return AdminUserListResponse(
        users=users_dto,
        total=total,
        page=page,
        page_size=limit,
    )


@router.get("/admin/usage-dashboard", response_model=AdminUsageDashboardResponse)
async def get_usage_dashboard(
    request: Request,
    active_days: int = Query(30, ge=1, le=365),
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Get high-level usage metrics for the application.
    """
    active_since = datetime.now(timezone.utc) - timedelta(days=active_days)
    return await get_admin_usage_dashboard(
        request.app.state.pg_engine,
        active_since=active_since,
        active_days=active_days,
    )


@router.get("/admin/users/{target_user_id}/usage", response_model=AllUsageResponse)
async def get_admin_user_usage(
    request: Request,
    target_user_id: str,
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Get a user's usage for all metered features.
    """
    pg_engine = request.app.state.pg_engine
    user = await get_user_by_id(pg_engine, target_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await _get_usage_response(pg_engine, user)


@router.post(
    "/admin/users/{target_user_id}/usage/{query_type}/reset",
    response_model=AllUsageResponse,
)
async def reset_admin_user_query_usage(
    request: Request,
    target_user_id: str,
    query_type: QueryTypeEnum,
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Reset a user's metered query usage for the current billing period.
    """
    pg_engine = request.app.state.pg_engine
    user = await get_user_by_id(pg_engine, target_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await reset_usage_record(pg_engine, user, query_type)
    return await _get_usage_response(pg_engine, user)


@router.patch("/admin/users/{target_user_id}/plan", response_model=AdminUserListItem)
async def update_admin_user_plan(
    request: Request,
    target_user_id: str,
    payload: AdminUpdateUserPlanPayload,
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Change a user's plan type.
    """
    pg_engine = request.app.state.pg_engine
    updated_user = await update_user_plan(pg_engine, target_user_id, payload.plan_type)
    return _to_admin_user_list_item(updated_user)


@router.patch("/admin/users/{target_user_id}/admin", response_model=AdminUserListItem)
async def update_admin_user_role(
    request: Request,
    target_user_id: str,
    payload: AdminUpdateUserRolePayload,
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Grant or revoke admin privileges for a user.
    """
    pg_engine = request.app.state.pg_engine
    target_user = await get_user_by_id(pg_engine, target_user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.is_admin and not payload.is_admin:
        if str(admin_user.id) == target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revoke your own admin access.",
            )

        if await count_admin_users(pg_engine) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revoke the last admin account.",
            )

    updated_user = await update_user_admin_status(pg_engine, target_user_id, payload.is_admin)
    return _to_admin_user_list_item(updated_user)


@router.patch("/admin/users/{target_user_id}/suspension", response_model=AdminUserListItem)
async def update_admin_user_suspension(
    request: Request,
    target_user_id: str,
    payload: AdminUpdateUserSuspensionPayload,
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Suspend or unsuspend a user account.
    """
    if payload.is_suspended and str(admin_user.id) == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own admin account.",
        )

    pg_engine = request.app.state.pg_engine
    suspended_until = (
        _normalize_suspended_until(payload.suspended_until) if payload.is_suspended else None
    )
    updated_user = await update_user_suspension(
        pg_engine,
        target_user_id,
        payload.is_suspended,
        payload.suspended_reason,
        suspended_until,
    )

    if payload.is_suspended:
        await delete_all_refresh_tokens_for_user(pg_engine, target_user_id)

    return _to_admin_user_list_item(updated_user)


@router.delete("/admin/users/{target_user_id}")
async def delete_user(
    request: Request,
    target_user_id: str,
    admin_user: User = Depends(require_admin),
):
    """
    Admin only: Delete a specific user by ID.
    Prevents self-deletion.
    """
    if str(admin_user.id) == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own admin account."
        )

    pg_engine = request.app.state.pg_engine
    exists = await get_user_by_id(pg_engine, target_user_id)
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await _delete_user_account_data(request, target_user_id)
    return {"message": "User deleted successfully"}
