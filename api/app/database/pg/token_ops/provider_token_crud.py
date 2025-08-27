from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select
import logging
from typing import Optional

from database.pg.models import ProviderToken

logger = logging.getLogger("uvicorn.error")


async def store_github_token_for_user(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, encrypted_token: str
):
    async with AsyncSession(pg_engine) as session:
        db_token = ProviderToken(
            user_id=user_id, provider="github", access_token=encrypted_token
        )
        session.add(db_token)
        await session.commit()
        await session.refresh(db_token)
        return db_token


async def get_provider_token(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider: str
) -> Optional[ProviderToken]:
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            ProviderToken.user_id == user_id, ProviderToken.provider == provider
        )
        result = await session.exec(stmt)
        return result.scalar_one_or_none()


async def delete_provider_token(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider: str
):
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            ProviderToken.user_id == user_id, ProviderToken.provider == provider
        )
        result = await session.exec(stmt)
        token = result.scalar_one_or_none()
        if token:
            await session.delete(token)
            await session.commit()
