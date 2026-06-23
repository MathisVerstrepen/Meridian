import os
import uuid
from datetime import datetime, timezone
from typing import cast
from urllib.parse import urlencode

from database.pg.token_ops.provider_token_crud import delete_provider_token
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from models.google_drive import (
    GoogleDriveCallbackPayload,
    GoogleDriveFile,
    GoogleDriveListResponse,
    GoogleDriveStatusResponse,
)
from services.auth import get_current_user_id
from services.file_sources import materialize_attachment_file
from services.google_drive import (
    GOOGLE_DRIVE_PROVIDER,
    GOOGLE_DRIVE_SCOPE,
    GoogleDriveSection,
    exchange_google_drive_code,
    get_download_name_and_type,
    get_google_drive_access_token,
    get_google_drive_user_email,
    is_google_drive_folder,
    list_google_drive_files,
    list_google_shared_drives,
    search_google_drive_files,
    store_google_drive_token,
)
from services.rate_limit import limiter

router = APIRouter(tags=["google-drive"])


def _to_drive_file(ref) -> GoogleDriveFile:
    file_type = "folder" if is_google_drive_folder(ref) else "file"
    filename, content_type = get_download_name_and_type(ref)
    return GoogleDriveFile(
        id=ref.id,
        external_id=ref.external_id,
        name=ref.name,
        path=f"/Google Drive/{ref.name}",
        type=file_type,
        mime_type=ref.mime_type,
        content_type=content_type if file_type == "file" else ref.mime_type,
        size=ref.size,
        modified_time=ref.modified_time,
        web_view_link=ref.web_view_link,
        downloadable=file_type == "file",
        created_at=ref.created_at,
        updated_at=ref.updated_at,
    )


def _to_shared_drive_folder(drive) -> GoogleDriveFile:
    now = datetime.now(timezone.utc)
    return GoogleDriveFile(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"google-drive-shared-drive:{drive.id}"),
        external_id=drive.id,
        name=drive.name,
        path=f"/Google Drive/Shared drives/{drive.name}",
        type="folder",
        mime_type="application/vnd.google-apps.folder",
        content_type="application/vnd.google-apps.folder",
        downloadable=False,
        created_at=now,
        updated_at=now,
    )


@router.get("/auth/google-drive/login")
async def google_drive_login():
    client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Drive OAuth is not configured on the server.",
        )

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_DRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.post("/auth/google-drive/callback")
@limiter.limit("5/minute")
async def google_drive_callback(
    request: Request,
    payload: GoogleDriveCallbackPayload,
    user_id: str = Depends(get_current_user_id),
):
    token_data = await exchange_google_drive_code(request.app.state.http_client, payload.code)
    await store_google_drive_token(request.app.state.pg_engine, user_id, token_data)
    access_token = str(token_data["access_token"])
    email = await get_google_drive_user_email(request.app.state.http_client, access_token)
    return {"message": "Google Drive account connected successfully.", "email": email}


@router.get("/auth/google-drive/status", response_model=GoogleDriveStatusResponse)
async def get_google_drive_connection_status(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    try:
        access_token = await get_google_drive_access_token(
            request.app.state.pg_engine, request.app.state.http_client, user_id
        )
        email = await get_google_drive_user_email(request.app.state.http_client, access_token)
    except HTTPException:
        return GoogleDriveStatusResponse(isConnected=False)
    return GoogleDriveStatusResponse(isConnected=True, email=email)


@router.post("/auth/google-drive/disconnect")
async def disconnect_google_drive(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    await delete_provider_token(request.app.state.pg_engine, user_id, GOOGLE_DRIVE_PROVIDER)
    return {"message": "Google Drive account disconnected successfully."}


@router.get("/google-drive/files", response_model=GoogleDriveListResponse)
async def get_google_drive_files(
    request: Request,
    folder_id: str | None = Query(None),
    page_token: str | None = Query(None),
    section: str = Query("my_drive", pattern="^(my_drive|shared_with_me|shared_drives)$"),
    user_id_str: str = Depends(get_current_user_id),
):
    user_id = uuid.UUID(user_id_str)
    drive_section = cast(GoogleDriveSection, section)
    if section == "shared_drives" and not folder_id:
        drives, next_page_token = await list_google_shared_drives(
            request.app.state.pg_engine,
            request.app.state.http_client,
            user_id,
            page_token=page_token,
        )
        return GoogleDriveListResponse(
            files=[_to_shared_drive_folder(drive) for drive in drives],
            next_page_token=next_page_token,
            incomplete_search=False,
        )

    refs, next_page_token, incomplete_search = await list_google_drive_files(
        request.app.state.pg_engine,
        request.app.state.http_client,
        user_id,
        folder_id=folder_id,
        page_token=page_token,
        section=drive_section,
    )
    return GoogleDriveListResponse(
        files=[_to_drive_file(ref) for ref in refs],
        next_page_token=next_page_token,
        incomplete_search=incomplete_search,
    )


@router.get("/google-drive/search", response_model=GoogleDriveListResponse)
async def search_google_drive(
    request: Request,
    q: str = Query(..., min_length=1),
    page_token: str | None = Query(None),
    section: str = Query("my_drive", pattern="^(my_drive|shared_with_me|shared_drives)$"),
    user_id_str: str = Depends(get_current_user_id),
):
    user_id = uuid.UUID(user_id_str)
    drive_section = cast(GoogleDriveSection, section)
    refs, next_page_token, incomplete_search = await search_google_drive_files(
        request.app.state.pg_engine,
        request.app.state.http_client,
        user_id,
        q,
        page_token=page_token,
        section=drive_section,
    )
    return GoogleDriveListResponse(
        files=[_to_drive_file(ref) for ref in refs],
        next_page_token=next_page_token,
        incomplete_search=incomplete_search,
    )


@router.get("/google-drive/view/{external_ref_id}")
async def view_google_drive_file(
    request: Request,
    external_ref_id: uuid.UUID,
    download: bool = False,
    user_id_str: str = Depends(get_current_user_id),
):
    user_id = uuid.UUID(user_id_str)
    materialized = await materialize_attachment_file(
        request.app.state.pg_engine,
        request.app.state.http_client,
        user_id,
        {"source": "google_drive", "id": str(external_ref_id)},
    )
    return FileResponse(
        path=materialized.path,
        media_type=materialized.content_type,
        filename=materialized.name,
        content_disposition_type="attachment" if download else "inline",
    )
