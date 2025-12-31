import logging
import uuid

from const.plans import PLAN_LIMITS
from database.pg.models import Files, User, UserStorageUsage
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


class StorageUsageInfo(BaseModel):
    used_bytes: int
    limit_bytes: int
    percentage: float


async def _sync_storage_usage(session: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Recalculates the total storage usage from the Files table and updates the usage record.
    Returns the calculated total.
    """
    stmt = select(func.sum(Files.size)).where(and_(Files.user_id == user_id, Files.type == "file"))
    result = await session.exec(stmt)  # type: ignore
    total_bytes = result.scalar() or 0
    total_bytes = int(total_bytes)

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
        stmt = select(UserStorageUsage).where(and_(UserStorageUsage.user_id == user.id))
        result = await session.exec(stmt)  # type: ignore
        record = result.scalar_one_or_none()

        used_bytes = 0
        if record:
            used_bytes = record.total_bytes_used
        else:
            # If no record exists, sync it
            used_bytes = await _sync_storage_usage(session, user.id)
            await session.commit()

        limit = PLAN_LIMITS.get(user.plan_type, {}).get("storage", 0)

        percentage = 0.0
        if limit > 0:
            percentage = min((used_bytes / limit) * 100, 100.0)

        return StorageUsageInfo(used_bytes=used_bytes, limit_bytes=limit, percentage=percentage)


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
