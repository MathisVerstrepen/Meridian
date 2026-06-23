import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from database.pg.models import ExternalFileCache
from database.pg.user_ops.storage_crud import release_storage
from services.files import get_user_storage_path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def cleanup_expired_external_file_cache(pg_engine: SQLAlchemyAsyncEngine) -> int:
    now = datetime.now(timezone.utc)
    async with AsyncSession(pg_engine) as session:
        stmt = select(ExternalFileCache).where(and_(ExternalFileCache.expires_at <= now))
        result = await session.exec(stmt)  # type: ignore
        expired = list(result.scalars().all())

    deleted = 0
    for cache in expired:
        disk_path = Path(get_user_storage_path(cache.user_id)) / cache.storage_path
        try:
            if disk_path.exists():
                await asyncio.to_thread(disk_path.unlink)
        except OSError as exc:
            logger.warning("Failed to delete expired external cache file %s: %s", disk_path, exc)

        async with AsyncSession(pg_engine) as session:
            db_cache = await session.get(ExternalFileCache, cache.id)
            if db_cache:
                await session.delete(db_cache)
                await session.commit()
                await release_storage(pg_engine, cache.user_id, cache.size)
                deleted += 1

    return deleted
