import logging
import uuid

from const.plans import PLAN_LIMITS
from database.pg.models import ExternalFileCache, Files, User, UserStorageUsage
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


class StorageUsageBreakdownItem(BaseModel):
    category: str
    used_bytes: int
    file_count: int


class StorageUsageInfo(BaseModel):
    used_bytes: int
    limit_bytes: int
    percentage: float
    breakdown: list[StorageUsageBreakdownItem]


DOCUMENT_CONTENT_TYPES = {
    "application/msword",
    "application/pdf",
    "application/rtf",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

STORAGE_BREAKDOWN_CATEGORIES = (
    "external_cache",
    "generated_images",
    "generated_videos",
    "artifacts",
    "videos",
    "images",
    "documents",
    "uploads",
    "other",
)


def _classify_storage_usage_item(file_path: str | None, content_type: str | None) -> str:
    normalized_path = (file_path or "").replace("\\", "/").lower().lstrip("/")
    media_type = (content_type or "").split(";", 1)[0].strip().lower()

    if normalized_path.startswith(".cache/external/"):
        return "external_cache"
    if normalized_path.startswith("generated_images/"):
        return "generated_images"
    if normalized_path.startswith("generated_videos/"):
        return "generated_videos"
    if normalized_path.startswith("generated_files/"):
        return "artifacts"
    if media_type.startswith("video/"):
        return "videos"
    if media_type.startswith("image/"):
        return "images"
    if media_type.startswith("text/") or media_type in DOCUMENT_CONTENT_TYPES:
        return "documents"
    if normalized_path:
        return "uploads"

    return "other"


async def _calculate_storage_breakdown(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[int, list[StorageUsageBreakdownItem]]:
    stmt = select(Files).where(and_(Files.user_id == user_id, Files.type == "file"))
    result = await session.exec(stmt)  # type: ignore

    usage_by_category = {
        category: StorageUsageBreakdownItem(category=category, used_bytes=0, file_count=0)
        for category in STORAGE_BREAKDOWN_CATEGORIES
    }

    for file_record in result.scalars().all():
        size_bytes = int(file_record.size or 0)
        category = _classify_storage_usage_item(file_record.file_path, file_record.content_type)
        item = usage_by_category[category]
        item.used_bytes += size_bytes
        item.file_count += 1

    cache_stmt = select(ExternalFileCache).where(and_(ExternalFileCache.user_id == user_id))
    cache_result = await session.exec(cache_stmt)  # type: ignore
    for cache_record in cache_result.scalars().all():
        item = usage_by_category["external_cache"]
        item.used_bytes += int(cache_record.size or 0)
        item.file_count += 1

    total_bytes = sum(item.used_bytes for item in usage_by_category.values())
    breakdown = [item for item in usage_by_category.values() if item.used_bytes > 0]

    return total_bytes, breakdown


async def _sync_storage_usage(session: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Recalculates the total storage usage from the Files table and updates the usage record.
    Returns the calculated total.
    """
    stmt = select(func.sum(Files.size)).where(and_(Files.user_id == user_id, Files.type == "file"))
    result = await session.exec(stmt)  # type: ignore
    total_bytes = int(result.scalar() or 0)
    cache_stmt = select(func.sum(ExternalFileCache.size)).where(
        and_(ExternalFileCache.user_id == user_id)
    )
    cache_result = await session.exec(cache_stmt)  # type: ignore
    total_bytes += int(cache_result.scalar() or 0)

    usage_stmt = select(UserStorageUsage).where(and_(UserStorageUsage.user_id == user_id))
    result = await session.exec(usage_stmt)  # type: ignore
    record = result.scalar_one_or_none()

    if record:
        record.total_bytes_used = total_bytes
        session.add(record)
    else:
        record = UserStorageUsage(user_id=user_id, total_bytes_used=total_bytes)
        session.add(record)

    await session.flush()
    return total_bytes


async def get_storage_usage(pg_engine: SQLAlchemyAsyncEngine, user: User) -> StorageUsageInfo:
    """
    Retrieves the current storage usage for a user.
    """
    if not user.id:
        raise ValueError("User ID is missing")

    async with AsyncSession(pg_engine) as session:
        calculated_bytes, breakdown = await _calculate_storage_breakdown(session, user.id)

        stmt = select(UserStorageUsage).where(and_(UserStorageUsage.user_id == user.id))
        result = await session.exec(stmt)  # type: ignore
        record = result.scalar_one_or_none()

        if record:
            used_bytes = record.total_bytes_used
        else:
            used_bytes = calculated_bytes
            record = UserStorageUsage(user_id=user.id, total_bytes_used=used_bytes)
            session.add(record)
            await session.commit()

        unclassified_bytes = used_bytes - sum(item.used_bytes for item in breakdown)
        if unclassified_bytes > 0:
            other_usage = next((item for item in breakdown if item.category == "other"), None)
            if other_usage:
                other_usage.used_bytes += unclassified_bytes
            else:
                breakdown.append(
                    StorageUsageBreakdownItem(
                        category="other",
                        used_bytes=unclassified_bytes,
                        file_count=0,
                    )
                )

        limit = PLAN_LIMITS.get(user.plan_type, {}).get("storage", 0)

        percentage = 0.0
        if limit > 0:
            percentage = min((used_bytes / limit) * 100, 100.0)

        return StorageUsageInfo(
            used_bytes=used_bytes,
            limit_bytes=limit,
            percentage=percentage,
            breakdown=breakdown,
        )


async def check_and_reserve_storage(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, file_size_bytes: int
) -> None:
    """
    Atomically checks if the user has enough space and reserves it.
    Raises HTTPException(403) if limit is exceeded.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            # Get user plan
            user = await session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            limit = PLAN_LIMITS.get(user.plan_type, {}).get("storage", 0)

            # Lock the usage row
            stmt = (
                select(UserStorageUsage)
                .where(and_(UserStorageUsage.user_id == user_id))
                .with_for_update()
            )
            result = await session.exec(stmt)  # type: ignore
            record = result.scalar_one_or_none()

            current_usage = 0
            if record:
                current_usage = record.total_bytes_used
            else:
                # Fallback sync inside transaction (will lock implicitly via sync logic if
                # we were to lock files, but here we just calculate and insert)
                current_usage = await _sync_storage_usage(session, user_id)
                # Re-fetch to get the object attached to session if _sync created new one
                stmt = select(UserStorageUsage).where(and_(UserStorageUsage.user_id == user_id))
                result = await session.exec(stmt)  # type: ignore
                record = result.scalar_one()

            if (current_usage + file_size_bytes) > limit:
                raise HTTPException(
                    status_code=403,
                    detail=f"Storage limit exceeded. Plan limit: {limit / 1024 / 1024:.2f} MB.",
                )

            record.total_bytes_used += file_size_bytes
            session.add(record)


async def release_storage(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, file_size_bytes: int
) -> None:
    """
    Decrements the storage usage. Safe to call even if it results in negative (clamped to 0).
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            stmt = (
                select(UserStorageUsage)
                .where(and_(UserStorageUsage.user_id == user_id))
                .with_for_update()
            )
            result = await session.exec(stmt)  # type: ignore
            record = result.scalar_one_or_none()

            if record:
                record.total_bytes_used = max(0, record.total_bytes_used - file_size_bytes)
                session.add(record)


async def get_recursive_item_size(
    pg_engine: SQLAlchemyAsyncEngine, item_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """
    Calculates the total size of an item (file or folder) recursively.
    """
    async with AsyncSession(pg_engine) as session:
        file_stmt = select(Files).where(and_(Files.id == item_id, Files.user_id == user_id))
        result = await session.exec(file_stmt)  # type: ignore
        item = result.scalar_one_or_none()

        if not item:
            return 0

        if item.type == "file":
            return item.size or 0

        cte = (
            select(Files.id, Files.size, Files.type)  # type: ignore
            .where(Files.id == item_id)
            .cte(name="folder_tree", recursive=True)
        )

        recursive_part = select(Files.id, Files.size, Files.type).join(  # type: ignore
            cte, Files.parent_id == cte.c.id
        )

        cte = cte.union_all(recursive_part)

        stmt = select(func.sum(cte.c.size)).where(cte.c.type == "file")
        result = await session.exec(stmt)  # type: ignore
        total_size = result.scalar() or 0

        return int(total_size)
