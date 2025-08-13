from fastapi import APIRouter, Depends, Request, UploadFile, File
import uuid
import json
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from services.crypto import verify_password
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.usersDTO import SettingsDTO
from models.auth import ProviderEnum, SyncUserResponse, UserRead
from services.files import save_file
from const.settings import DEFAULT_SETTINGS, DEFAULT_ROUTE_GROUP
from services.crypto import store_api_key, db_payload_to_cryptojs_encrypt
from services.auth import (
    create_access_token,
    get_current_user_id,
    handle_password_update,
)
from utils.helpers import complete_settings_dict

from database.pg.crud import (
    ProviderUserPayload,
    get_user_by_provider_id,
    create_user_from_provider,
    update_settings,
    get_settings,
    add_user_file,
    get_user_by_username,
    get_user_by_id,
)

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


class UserPasswordLoginPayload(BaseModel):
    username: str
    password: str
    rememberMe: bool


@router.post("/auth/login")
@limiter.limit("3/minute")
async def login_for_access_token(
    request: Request,
) -> SyncUserResponse:
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

    if not db_user or not db_user.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not verify_password(payload.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    return SyncUserResponse(
        status="authenticated",
        token=create_access_token(
            data={"sub": str(db_user.id)}, stay_signed_in=payload.rememberMe
        ),
        user=UserRead(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            avatar_url=db_user.avatar_url,
            created_at=db_user.created_at,
        ),
    )


@router.post("/auth/sync-user/{provider}")
@limiter.limit("5/minute")
async def sync_user(
    request: Request, provider: ProviderEnum, payload: ProviderUserPayload
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
                general=DEFAULT_SETTINGS.general,
                account=DEFAULT_SETTINGS.account,
                appearance=DEFAULT_SETTINGS.appearance,
                models=DEFAULT_SETTINGS.models,
                block=DEFAULT_SETTINGS.block,
                modelsDropdown=DEFAULT_SETTINGS.modelsDropdown,
                blockParallelization=DEFAULT_SETTINGS.blockParallelization,
                blockRouting=DEFAULT_SETTINGS.blockRouting,
            ).model_dump_json(),
        )
        return SyncUserResponse(
            status="created",
            token=create_access_token(data={"sub": str(new_user.id)}),
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
            token=create_access_token(data={"sub": str(db_user.id)}),
            user=UserRead(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                avatar_url=db_user.avatar_url,
                created_at=db_user.created_at,
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
) -> None:
    """
    Resets the user's password.

    This endpoint allows the user to reset their password.

    Args:
        payload (ResetPasswordPayload): The payload containing the new password.

    Returns:
        None
    """

    db_user = await get_user_by_id(request.app.state.pg_engine, user_id)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify old password
    if not verify_password(payload.oldPassword, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect old password",
        )

    await handle_password_update(
        request.app.state.pg_engine, user_id, payload.newPassword
    )


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
    settings_db = await get_settings(request.app.state.pg_engine, user_id_uuid)

    settings_data_dict = json.loads(settings_db.settings_data)

    completed_dict = complete_settings_dict(settings_data_dict)

    settings = SettingsDTO.model_validate(completed_dict)

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

        settings.account.openRouterApiKey = db_payload_to_cryptojs_encrypt(
            db_payload=settings.account.openRouterApiKey,
            user_id=str(user_id),
        )
    else:
        settings = SettingsDTO(
            user_id=user_id,
            settings_data=json.dumps(DEFAULT_SETTINGS.model_dump()),
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

    settings.account.openRouterApiKey = store_api_key(
        frontend_encrypted_key=settings.account.openRouterApiKey,
        user_id=user_id,
    )

    user_id = uuid.UUID(user_id)
    await update_settings(
        request.app.state.pg_engine, user_id, settings.model_dump_json()
    )


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
    user_id = uuid.UUID(user_id)

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
