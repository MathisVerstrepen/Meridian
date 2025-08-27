from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
import logging
import uuid

from database.pg.models import RefreshToken, UsedRefreshToken

logger = logging.getLogger("uvicorn.error")


async def create_db_refresh_token(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, token: str, expires_at: datetime
) -> RefreshToken:
    async with AsyncSession(pg_engine) as session:
        db_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        session.add(db_token)
        await session.commit()
        await session.refresh(db_token)
        return db_token


async def get_db_refresh_token(
    pg_engine: SQLAlchemyAsyncEngine, token: str
) -> RefreshToken | None:
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()


async def delete_db_refresh_token(pg_engine: SQLAlchemyAsyncEngine, token: str):
    """
    Atomically moves a refresh token from the active table to the used table.
    This "deletes" the token from active use while preserving it for replay detection.
    """
    async with AsyncSession(pg_engine) as session:
        # Find the token to move
        result = await session.exec(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        db_token = result.scalar_one_or_none()

        if db_token:
            # Create a record in the used tokens table to log its use
            used_token = UsedRefreshToken(
                token=db_token.token,
                user_id=db_token.user_id,
                expires_at=db_token.expires_at,
            )
            session.add(used_token)

            # Delete the original token from the active table
            await session.delete(db_token)

            await session.commit()


async def delete_all_refresh_tokens_for_user(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str
):
    """
    Deletes ALL refresh tokens (active and used) for a specific user.
    This is a critical security function to invalidate all sessions upon breach detection.
    """
    async with AsyncSession(pg_engine) as session:
        # Delete from the active tokens table
        await session.exec(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        # Delete from the used tokens table to clean up
        await session.exec(
            delete(UsedRefreshToken).where(UsedRefreshToken.user_id == user_id)
        )
        await session.commit()


async def find_user_id_by_used_token(
    pg_engine: SQLAlchemyAsyncEngine, token: str
) -> uuid.UUID | None:
    """
    Checks if a token exists in the used_refresh_tokens table.
    If found, it returns the associated user_id, indicating a potential replay attack.
    """
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(UsedRefreshToken.user_id).where(UsedRefreshToken.token == token)
        )
        return result.scalar_one_or_none()
