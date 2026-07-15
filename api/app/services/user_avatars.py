import logging
import os
import uuid
import warnings
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urljoin, urlsplit

import httpx
from database.pg.models import User
from database.pg.user_ops.user_crud import update_user_avatar_url
from models.auth import ProviderEnum
from PIL import Image, UnidentifiedImageError
from services.files import delete_file_from_disk, save_file_to_disk
from services.oauth import PROVIDER_HTTP_TIMEOUT
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

AVATAR_SUBDIRECTORY = "profile_pictures"
MAX_AVATAR_SIZE_MB = 4
MAX_AVATAR_SIZE_BYTES = MAX_AVATAR_SIZE_MB * 1024 * 1024
ALLOWED_AVATAR_TYPES = ("image/png", "image/jpeg", "image/webp")
PROVIDER_AVATAR_HOSTS: dict[ProviderEnum, tuple[str, ...]] = {
    ProviderEnum.GOOGLE: ("googleusercontent.com",),
    ProviderEnum.GITHUB: (
        "avatars.githubusercontent.com",
        "private-avatars.githubusercontent.com",
    ),
}
_FORMAT_DETAILS = {
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "WEBP": ("image/webp", "webp"),
}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5


class AvatarDownloadError(Exception):
    """Raised for expected provider-avatar download and validation failures."""


@dataclass(frozen=True)
class DownloadedAvatar:
    contents: bytes
    content_type: str
    filename: str


def _host_is_allowed(hostname: str, allowed_hosts: tuple[str, ...]) -> bool:
    return any(hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts)


def _validate_provider_avatar_url(provider: ProviderEnum, url: str) -> str:
    if provider not in PROVIDER_AVATAR_HOSTS:
        raise AvatarDownloadError("unsupported provider")

    try:
        parsed = urlsplit(url)
        parsed.port
    except ValueError as exc:
        raise AvatarDownloadError("invalid provider avatar URL") from exc

    hostname = parsed.hostname.lower() if parsed.hostname else None
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or not _host_is_allowed(hostname, PROVIDER_AVATAR_HOSTS[provider])
    ):
        raise AvatarDownloadError("provider avatar URL is not allowed")

    return url


async def _read_bounded_avatar_response(response: httpx.Response) -> tuple[bytes, str]:
    declared_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if declared_type not in ALLOWED_AVATAR_TYPES:
        raise AvatarDownloadError("provider avatar content type is not allowed")

    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            expected_size = int(content_length)
        except ValueError as exc:
            raise AvatarDownloadError("provider avatar content length is invalid") from exc
        if expected_size < 0 or expected_size > MAX_AVATAR_SIZE_BYTES:
            raise AvatarDownloadError("provider avatar exceeds size limit")

    chunks: list[bytes] = []
    total_size = 0
    async for chunk in response.aiter_bytes():
        total_size += len(chunk)
        if total_size > MAX_AVATAR_SIZE_BYTES:
            raise AvatarDownloadError("provider avatar exceeds size limit")
        chunks.append(chunk)

    return b"".join(chunks), declared_type


def _validate_avatar_bytes(contents: bytes, declared_type: str) -> DownloadedAvatar:
    if not contents:
        raise AvatarDownloadError("provider avatar is empty")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contents)) as image:
                image_format = image.format
                image.verify()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
    ) as exc:
        raise AvatarDownloadError("provider avatar image is invalid") from exc

    format_details = _FORMAT_DETAILS.get(image_format or "")
    if not format_details or format_details[0] != declared_type:
        raise AvatarDownloadError("provider avatar image format does not match content type")

    return DownloadedAvatar(
        contents=contents,
        content_type=format_details[0],
        filename=f"avatar.{format_details[1]}",
    )


async def _download_provider_avatar(provider: ProviderEnum, url: str) -> DownloadedAvatar:
    current_url = _validate_provider_avatar_url(provider, url)

    async with httpx.AsyncClient(
        timeout=PROVIDER_HTTP_TIMEOUT,
        follow_redirects=False,
    ) as client:
        for redirect_count in range(_MAX_REDIRECTS + 1):
            async with client.stream("GET", current_url) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    if redirect_count == _MAX_REDIRECTS:
                        raise AvatarDownloadError("provider avatar exceeded redirect limit")
                    location = response.headers.get("Location")
                    if not location:
                        raise AvatarDownloadError("provider avatar redirect has no location")
                    current_url = _validate_provider_avatar_url(
                        provider, urljoin(current_url, location)
                    )
                    continue

                if response.status_code != 200:
                    raise AvatarDownloadError("provider avatar response was unsuccessful")

                contents, declared_type = await _read_bounded_avatar_response(response)
                return _validate_avatar_bytes(contents, declared_type)

    raise AvatarDownloadError("provider avatar download did not complete")


def is_external_avatar_reference(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def is_local_avatar_reference(value: str | None) -> bool:
    return bool(
        isinstance(value, str)
        and value
        and value not in {".", ".."}
        and os.path.basename(value) == value
        and "/" not in value
        and "\\" not in value
        and "\x00" not in value
    )


def safe_avatar_reference(value: str | None) -> str | None:
    return value if is_local_avatar_reference(value) else None


async def _clear_unsafe_avatar_reference(pg_engine: SQLAlchemyAsyncEngine, user: User) -> None:
    if not user.avatar_url or is_local_avatar_reference(user.avatar_url):
        return
    try:
        await update_user_avatar_url(pg_engine, str(user.id), None)
    except Exception as exc:
        logger.warning(
            "Unable to clear unsafe avatar reference for user=%s (%s)",
            user.id,
            type(exc).__name__,
        )


async def sync_provider_avatar(
    pg_engine: SQLAlchemyAsyncEngine,
    user: User,
    provider: ProviderEnum,
    provider_avatar_url: str | None,
) -> str | None:
    """Best-effort local storage for a verified provider avatar source."""
    if is_local_avatar_reference(user.avatar_url):
        return user.avatar_url

    if not provider_avatar_url:
        await _clear_unsafe_avatar_reference(pg_engine, user)
        return None

    try:
        downloaded_avatar = await _download_provider_avatar(provider, provider_avatar_url)
        filename = await save_file_to_disk(
            user_id=uuid.UUID(str(user.id)),
            file_contents=downloaded_avatar.contents,
            original_filename=downloaded_avatar.filename,
            subdirectory=AVATAR_SUBDIRECTORY,
        )
    except Exception as exc:
        logger.warning(
            "Provider avatar sync failed for provider=%s user=%s (%s)",
            provider.value,
            user.id,
            type(exc).__name__,
        )
        await _clear_unsafe_avatar_reference(pg_engine, user)
        return None

    try:
        await update_user_avatar_url(pg_engine, str(user.id), filename)
    except Exception as exc:
        logger.warning(
            "Provider avatar database update failed for provider=%s user=%s (%s)",
            provider.value,
            user.id,
            type(exc).__name__,
        )
        try:
            deleted = await delete_file_from_disk(
                uuid.UUID(str(user.id)), filename, subdirectory=AVATAR_SUBDIRECTORY
            )
            if not deleted:
                logger.error("Provider avatar cleanup failed for user=%s", user.id)
        except Exception as cleanup_exc:
            logger.error(
                "Provider avatar cleanup raised for user=%s (%s)",
                user.id,
                type(cleanup_exc).__name__,
            )
        await _clear_unsafe_avatar_reference(pg_engine, user)
        return None

    return filename
