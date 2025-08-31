import logging
import uuid
from datetime import datetime

from database.pg.models import RefreshToken, UsedRefreshToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

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


async def get_db_refresh_token(pg_engine: SQLAlchemyAsyncEngine, token: str) -> RefreshToken | None:
    async with AsyncSession(pg_engine) as session:
        stmt = select(RefreshToken).where(and_(RefreshToken.token == token))
        result = await session.exec(stmt)  # type: ignore
        res_token: RefreshToken = result.scalar_one_or_none()

        return res_token if res_token else None


async def delete_db_refresh_token(pg_engine: SQLAlchemyAsyncEngine, token: str):
    """
    Atomically moves a refresh token from the active table to the used table.
    This "deletes" the token from active use while preserving it for replay detection.
    """
    async with AsyncSession(pg_engine) as session:
        # Find the token to move
        stmt = select(RefreshToken).where(and_(RefreshToken.token == token))
        result = await session.exec(stmt)  # type: ignore
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


async def delete_all_refresh_tokens_for_user(pg_engine: SQLAlchemyAsyncEngine, user_id: str):
    """
    Deletes ALL refresh tokens (active and used) for a specific user.
    This is a critical security function to invalidate all sessions upon breach detection.
    """
    async with AsyncSession(pg_engine) as session:
        # Delete from the active tokens table
        stmt = delete(RefreshToken).where(and_(RefreshToken.user_id == user_id))
        await session.exec(stmt)  # type: ignore
        # Delete from the used tokens table to clean up
        stmt = delete(UsedRefreshToken).where(and_(UsedRefreshToken.user_id == user_id))
        await session.exec(stmt)  # type: ignore
        await session.commit()


async def find_user_id_by_used_token(
    pg_engine: SQLAlchemyAsyncEngine, token: str
) -> uuid.UUID | None:
    """
    Checks if a token exists in the used_refresh_tokens table.
    If found, it returns the associated user_id, indicating a potential replay attack.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(UsedRefreshToken.user_id).where(  # type: ignore
            and_(UsedRefreshToken.token == token)
        )
        result = await session.exec(stmt)
        token_user_id = result.scalar_one_or_none()
        return uuid.UUID(token_user_id) if token_user_id else None
