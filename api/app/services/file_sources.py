import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, cast

import httpx
from database.pg.file_ops.file_crud import get_file_by_id
from database.pg.models import ExternalFileCache
from database.pg.user_ops.storage_crud import check_and_reserve_storage, release_storage
from fastapi import HTTPException
from services.files import get_or_calculate_file_hash, get_user_storage_path
from services.google_drive import (
    GOOGLE_DRIVE_PROVIDER,
    download_google_drive_file,
    get_external_file_ref,
    get_google_drive_cache_expires_at,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class MaterializedFile:
    source: str
    file_id: str
    path: Path
    storage_path: str
    name: str
    content_type: str
    size: int
    content_hash: str | None


def _safe_filename(name: str) -> str:
    filename = PurePosixPath(str(name or "file").replace("\\", "/")).name.strip()
    return filename or "file"


async def _materialize_meridian_file(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    file_info: dict[str, Any],
) -> MaterializedFile:
    file_id = str(file_info.get("id") or "").strip()
    if not file_id:
        raise HTTPException(status_code=404, detail="File not found.")

    file_record = await get_file_by_id(pg_engine, uuid.UUID(file_id), user_id)
    if not file_record or file_record.type != "file" or not file_record.file_path:
        raise HTTPException(status_code=404, detail="File not found.")

    disk_path = Path(get_user_storage_path(user_id)) / str(file_record.file_path)
    if not disk_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    content_hash = await get_or_calculate_file_hash(
        pg_engine, file_record.id, str(user_id), str(disk_path)
    )
    return MaterializedFile(
        source="meridian",
        file_id=str(file_record.id),
        path=disk_path,
        storage_path=str(file_record.file_path),
        name=str(file_record.name),
        content_type=str(
            file_record.content_type or file_info.get("content_type") or "application/octet-stream"
        ),
        size=int(file_record.size or disk_path.stat().st_size),
        content_hash=content_hash,
    )


async def _get_valid_cache(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    ref_id: uuid.UUID,
) -> ExternalFileCache | None:
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(ExternalFileCache)
            .where(
                and_(
                    ExternalFileCache.user_id == user_id,
                    ExternalFileCache.external_file_ref_id == ref_id,
                    ExternalFileCache.expires_at > datetime.now(timezone.utc),
                )
            )
            .order_by(ExternalFileCache.created_at.desc())  # type: ignore[attr-defined]
        )
        result = await session.exec(stmt)  # type: ignore
        cache = result.scalars().first()
        if cache:
            cache.last_accessed_at = datetime.now(timezone.utc)
            session.add(cache)
            await session.commit()
        return cast(ExternalFileCache | None, cache)


async def _write_cache_file(
    user_id: uuid.UUID, ref_id: uuid.UUID, filename: str, content: bytes
) -> str:
    storage_path = str(
        PurePosixPath(
            ".cache", "external", GOOGLE_DRIVE_PROVIDER, str(ref_id), _safe_filename(filename)
        )
    )
    full_path = Path(get_user_storage_path(user_id)) / storage_path
    await asyncio.to_thread(full_path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(full_path.write_bytes, content)
    return storage_path


async def _create_cache_row(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    ref_id: uuid.UUID,
    storage_path: str,
    size: int,
    content_type: str,
    content_hash: str,
) -> ExternalFileCache:
    async with AsyncSession(pg_engine) as session:
        cache = ExternalFileCache(
            external_file_ref_id=ref_id,
            user_id=user_id,
            storage_path=storage_path,
            size=size,
            content_type=content_type,
            content_hash=content_hash,
            expires_at=get_google_drive_cache_expires_at(),
            last_accessed_at=datetime.now(timezone.utc),
        )
        session.add(cache)
        await session.commit()
        await session.refresh(cache)
        return cache


async def _materialize_google_drive_file(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: uuid.UUID,
    file_info: dict[str, Any],
) -> MaterializedFile:
    raw_ref_id = file_info.get("external_ref_id") or file_info.get("id")
    ref_id = uuid.UUID(str(raw_ref_id))
    ref = await get_external_file_ref(pg_engine, user_id, ref_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Google Drive file reference not found.")

    cache = await _get_valid_cache(pg_engine, user_id, ref_id)
    if cache:
        disk_path = Path(get_user_storage_path(user_id)) / cache.storage_path
        if disk_path.is_file():
            return MaterializedFile(
                source=GOOGLE_DRIVE_PROVIDER,
                file_id=str(ref.id),
                path=disk_path,
                storage_path=cache.storage_path,
                name=ref.name,
                content_type=cache.content_type or ref.mime_type or "application/octet-stream",
                size=cache.size,
                content_hash=cache.content_hash,
            )

    downloaded = await download_google_drive_file(pg_engine, http_client, user_id, ref)
    size = len(downloaded.content)
    await check_and_reserve_storage(pg_engine, user_id, size)

    storage_path = ""
    try:
        storage_path = await _write_cache_file(
            user_id, ref_id, downloaded.filename, downloaded.content
        )
        cache = await _create_cache_row(
            pg_engine,
            user_id,
            ref_id,
            storage_path,
            size,
            downloaded.content_type,
            downloaded.content_hash,
        )
    except Exception:
        if storage_path:
            await asyncio.to_thread(os.remove, Path(get_user_storage_path(user_id)) / storage_path)
        await release_storage(pg_engine, user_id, size)
        raise

    return MaterializedFile(
        source=GOOGLE_DRIVE_PROVIDER,
        file_id=str(ref.id),
        path=Path(get_user_storage_path(user_id)) / cache.storage_path,
        storage_path=cache.storage_path,
        name=downloaded.filename,
        content_type=downloaded.content_type,
        size=cache.size,
        content_hash=cache.content_hash,
    )


async def materialize_attachment_file(
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
    user_id: uuid.UUID,
    file_info: dict[str, Any],
) -> MaterializedFile:
    source = str(file_info.get("source") or "meridian").strip().lower()
    if source == GOOGLE_DRIVE_PROVIDER:
        return await _materialize_google_drive_file(pg_engine, http_client, user_id, file_info)
    return await _materialize_meridian_file(pg_engine, user_id, file_info)
