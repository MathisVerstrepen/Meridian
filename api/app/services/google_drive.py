import hashlib
import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any, Literal, Optional, cast

import httpx
from database.pg.models import ExternalFileRef, ProviderToken
from database.pg.token_ops.provider_token_crud import get_provider_token, store_provider_token
from fastapi import HTTPException, status
from services.crypto import decrypt_api_key, encrypt_api_key
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")

GOOGLE_DRIVE_PROVIDER = "google_drive"
GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GOOGLE_WORKSPACE_EXPORT_LIMIT_BYTES = 10 * 1024 * 1024
GOOGLE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
GoogleDriveSection = Literal["my_drive", "shared_with_me", "shared_drives"]

WORKSPACE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
}

DRIVE_FILE_FIELDS = ",".join(
    [
        "id",
        "name",
        "mimeType",
        "size",
        "modifiedTime",
        "md5Checksum",
        "webViewLink",
    ]
)


@dataclass(frozen=True)
class DownloadedDriveFile:
    filename: str
    content: bytes
    content_type: str
    content_hash: str


@dataclass(frozen=True)
class GoogleSharedDrive:
    id: str
    name: str


def get_google_drive_cache_ttl_hours() -> int:
    try:
        return max(1, int(os.getenv("GOOGLE_DRIVE_CACHE_TTL_HOURS") or "24"))
    except ValueError:
        return 24


def get_google_drive_cache_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=get_google_drive_cache_ttl_hours())


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_size(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_oauth_config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Drive OAuth is not configured on the server.",
        )
    return client_id, client_secret, redirect_uri


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def exchange_google_drive_code(
    http_client: httpx.AsyncClient,
    code: str,
) -> dict[str, Any]:
    client_id, client_secret, redirect_uri = _get_oauth_config()
    response = await http_client.post(
        GOOGLE_OAUTH_TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to exchange Google Drive code: {response.text}",
        )
    token_data = response.json()
    if not token_data.get("access_token"):
        raise HTTPException(status_code=400, detail="Google Drive did not return an access token.")
    return cast(dict[str, Any], token_data)


async def store_google_drive_token(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    token_data: dict[str, Any],
) -> ProviderToken:
    access_token = str(token_data.get("access_token") or "")
    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in") or 3600)
    scopes = str(token_data.get("scope") or GOOGLE_DRIVE_SCOPE)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    encrypted_access = await encrypt_api_key(access_token)
    encrypted_refresh = await encrypt_api_key(str(refresh_token)) if refresh_token else None
    if not encrypted_access:
        raise HTTPException(status_code=500, detail="Failed to secure Google Drive token.")

    token_record = await store_provider_token(
        pg_engine,
        user_id,
        GOOGLE_DRIVE_PROVIDER,
        encrypted_access,
        encrypted_refresh_token=encrypted_refresh,
        scopes=scopes,
        expires_at=expires_at,
    )
    return cast(ProviderToken, token_record)


async def _refresh_google_drive_token(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: str,
    token_record: ProviderToken,
) -> str:
    if not token_record.refresh_token:
        raise HTTPException(status_code=401, detail="Google Drive account must be reconnected.")

    refresh_token = await decrypt_api_key(token_record.refresh_token)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Google Drive account must be reconnected.")

    client_id, client_secret, _redirect_uri = _get_oauth_config()
    response = await http_client.post(
        GOOGLE_OAUTH_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail=f"Google Drive token refresh failed: {response.text}",
        )

    token_data = response.json()
    token_data["refresh_token"] = refresh_token
    await store_google_drive_token(pg_engine, user_id, token_data)
    return str(token_data["access_token"])


async def get_google_drive_access_token(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: str,
) -> str:
    token_record = await get_provider_token(pg_engine, user_id, GOOGLE_DRIVE_PROVIDER)
    if not token_record:
        raise HTTPException(status_code=401, detail="Google Drive is not connected.")

    now = datetime.now(timezone.utc)
    if token_record.expires_at and token_record.expires_at <= now + timedelta(minutes=5):
        return await _refresh_google_drive_token(pg_engine, http_client, user_id, token_record)

    access_token = await decrypt_api_key(token_record.access_token)
    if not access_token:
        raise HTTPException(status_code=401, detail="Google Drive account must be reconnected.")
    return access_token


async def get_google_drive_user_email(
    http_client: httpx.AsyncClient, access_token: str
) -> str | None:
    response = await http_client.get(
        f"{GOOGLE_DRIVE_API_BASE}/about",
        params={"fields": "user(emailAddress)"},
        headers=_auth_headers(access_token),
    )
    if response.status_code != 200:
        return None
    data = response.json()
    user = data.get("user") if isinstance(data, dict) else None
    if isinstance(user, dict):
        email = user.get("emailAddress")
        return str(email) if email else None
    return None


def _drive_query_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _drive_item_to_ref(user_id: uuid.UUID, item: dict[str, Any]) -> ExternalFileRef:
    return ExternalFileRef(
        user_id=user_id,
        provider=GOOGLE_DRIVE_PROVIDER,
        external_id=str(item["id"]),
        name=str(item.get("name") or "Untitled"),
        mime_type=item.get("mimeType"),
        size=_parse_size(item.get("size")),
        modified_time=_parse_datetime(item.get("modifiedTime")),
        md5_checksum=item.get("md5Checksum"),
        web_view_link=item.get("webViewLink"),
    )


async def upsert_external_file_ref(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    item: dict[str, Any],
) -> ExternalFileRef:
    async with AsyncSession(pg_engine) as session:
        stmt = select(ExternalFileRef).where(
            and_(
                ExternalFileRef.user_id == user_id,
                ExternalFileRef.provider == GOOGLE_DRIVE_PROVIDER,
                ExternalFileRef.external_id == str(item["id"]),
            )
        )
        result = await session.exec(stmt)  # type: ignore
        ref = result.scalar_one_or_none()
        if ref is None:
            ref = _drive_item_to_ref(user_id, item)
            session.add(ref)
        else:
            ref.name = str(item.get("name") or ref.name)
            ref.mime_type = item.get("mimeType")
            ref.size = _parse_size(item.get("size"))
            ref.modified_time = _parse_datetime(item.get("modifiedTime"))
            ref.md5_checksum = item.get("md5Checksum")
            ref.web_view_link = item.get("webViewLink")
        await session.commit()
        await session.refresh(ref)
        return cast(ExternalFileRef, ref)


async def get_external_file_ref(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    ref_id: uuid.UUID,
) -> ExternalFileRef | None:
    async with AsyncSession(pg_engine) as session:
        stmt = select(ExternalFileRef).where(
            and_(ExternalFileRef.user_id == user_id, ExternalFileRef.id == ref_id)
        )
        result = await session.exec(stmt)  # type: ignore
        return cast(ExternalFileRef | None, result.scalar_one_or_none())


async def list_google_drive_files(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: uuid.UUID,
    folder_id: str | None = None,
    page_token: str | None = None,
    section: GoogleDriveSection = "my_drive",
) -> tuple[list[ExternalFileRef], str | None, bool]:
    access_token = await get_google_drive_access_token(pg_engine, http_client, str(user_id))
    params = {
        "fields": f"nextPageToken,incompleteSearch,files({DRIVE_FILE_FIELDS})",
        "pageSize": "100",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if folder_id:
        params["q"] = f"'{_drive_query_literal(folder_id)}' in parents and trashed=false"
    elif section == "shared_with_me":
        params["corpora"] = "allDrives"
        params["q"] = "sharedWithMe = true and trashed=false"
    elif section == "shared_drives":
        params["corpora"] = "allDrives"
        params["q"] = "trashed=false"
    else:
        params["corpora"] = "user"
        params["q"] = "'root' in parents and trashed=false"
    if page_token:
        params["pageToken"] = page_token

    response = await http_client.get(
        f"{GOOGLE_DRIVE_API_BASE}/files",
        params=params,
        headers=_auth_headers(access_token),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    payload = response.json()
    refs = [
        await upsert_external_file_ref(pg_engine, user_id, item)
        for item in payload.get("files", [])
    ]
    return refs, payload.get("nextPageToken"), bool(payload.get("incompleteSearch", False))


async def list_google_shared_drives(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: uuid.UUID,
    page_token: str | None = None,
) -> tuple[list[GoogleSharedDrive], str | None]:
    access_token = await get_google_drive_access_token(pg_engine, http_client, str(user_id))
    params = {
        "fields": "nextPageToken,drives(id,name)",
        "pageSize": "100",
    }
    if page_token:
        params["pageToken"] = page_token

    response = await http_client.get(
        f"{GOOGLE_DRIVE_API_BASE}/drives",
        params=params,
        headers=_auth_headers(access_token),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    payload = response.json()
    drives = [
        GoogleSharedDrive(id=str(item["id"]), name=str(item.get("name") or "Shared drive"))
        for item in payload.get("drives", [])
    ]
    return drives, payload.get("nextPageToken")


async def search_google_drive_files(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: uuid.UUID,
    query: str,
    page_token: str | None = None,
    section: GoogleDriveSection = "my_drive",
) -> tuple[list[ExternalFileRef], str | None, bool]:
    access_token = await get_google_drive_access_token(pg_engine, http_client, str(user_id))
    search_query = _drive_query_literal(query.strip())
    params = {
        "fields": f"nextPageToken,incompleteSearch,files({DRIVE_FILE_FIELDS})",
        "pageSize": "100",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "q": f"name contains '{search_query}' and trashed=false",
    }
    if section == "shared_with_me":
        params["corpora"] = "allDrives"
        params["q"] = f"sharedWithMe = true and name contains '{search_query}' and trashed=false"
    elif section == "shared_drives":
        params["corpora"] = "allDrives"
    else:
        params["corpora"] = "user"
    if page_token:
        params["pageToken"] = page_token

    response = await http_client.get(
        f"{GOOGLE_DRIVE_API_BASE}/files",
        params=params,
        headers=_auth_headers(access_token),
    )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    payload = response.json()
    refs = [
        await upsert_external_file_ref(pg_engine, user_id, item)
        for item in payload.get("files", [])
    ]
    return refs, payload.get("nextPageToken"), bool(payload.get("incompleteSearch", False))


def is_google_drive_folder(ref: ExternalFileRef) -> bool:
    return ref.mime_type == GOOGLE_FOLDER_MIME_TYPE


def get_download_name_and_type(ref: ExternalFileRef) -> tuple[str, str]:
    if ref.mime_type in WORKSPACE_EXPORTS:
        content_type, extension = WORKSPACE_EXPORTS[ref.mime_type]
        name = ref.name if ref.name.lower().endswith(extension) else f"{ref.name}{extension}"
        return name, content_type
    return (
        ref.name,
        ref.mime_type or mimetypes.guess_type(ref.name)[0] or "application/octet-stream",
    )


async def download_google_drive_file(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: uuid.UUID,
    ref: ExternalFileRef,
) -> DownloadedDriveFile:
    if is_google_drive_folder(ref):
        raise HTTPException(status_code=400, detail="Google Drive folders cannot be downloaded.")

    access_token = await get_google_drive_access_token(pg_engine, http_client, str(user_id))
    filename, content_type = get_download_name_and_type(ref)
    if ref.mime_type in WORKSPACE_EXPORTS:
        url = f"{GOOGLE_DRIVE_API_BASE}/files/{ref.external_id}/export"
        params = {"mimeType": content_type}
    else:
        url = f"{GOOGLE_DRIVE_API_BASE}/files/{ref.external_id}"
        params = {"alt": "media", "supportsAllDrives": "true"}

    response = await http_client.get(url, params=params, headers=_auth_headers(access_token))
    if response.status_code != 200:
        if response.status_code == 403 and ref.mime_type in WORKSPACE_EXPORTS:
            raise HTTPException(
                status_code=403,
                detail="Google Workspace export failed. Exports are limited to 10 MB.",
            )
        raise HTTPException(status_code=response.status_code, detail=response.text)

    content = response.content
    if ref.mime_type in WORKSPACE_EXPORTS and len(content) > GOOGLE_WORKSPACE_EXPORT_LIMIT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Google Workspace export is too large. Google exports are limited to 10 MB.",
        )
    return DownloadedDriveFile(
        filename=PurePosixPath(filename).name,
        content=content,
        content_type=content_type,
        content_hash=hashlib.sha256(content).hexdigest(),
    )
