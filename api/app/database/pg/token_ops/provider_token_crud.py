import logging
from typing import Optional

from database.pg.models import ProviderToken
from services.crypto import decrypt_api_key
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def store_provider_token(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider: str, encrypted_token: str
):
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            and_(
                ProviderToken.user_id == user_id,
                ProviderToken.provider == provider,
            )
        )
        result = await session.exec(stmt)  # type: ignore
        db_token = result.scalar_one_or_none()
        if db_token is None:
            db_token = ProviderToken(
                user_id=user_id,
                provider=provider,
                access_token=encrypted_token,
            )
            session.add(db_token)
        else:
            db_token.access_token = encrypted_token
        await session.commit()
        await session.refresh(db_token)
        return db_token


async def store_provider_token_if_current_matches(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider: str,
    current_token: str,
    encrypted_token: str,
) -> bool:
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(ProviderToken)
            .where(
                and_(
                    ProviderToken.user_id == user_id,
                    ProviderToken.provider == provider,
                )
            )
            .with_for_update()
        )
        result = await session.exec(stmt)  # type: ignore
        db_token = result.scalar_one_or_none()
        if db_token is None:
            return False

        stored_token = await decrypt_api_key(db_token.access_token)
        if stored_token != current_token:
            return False

        db_token.access_token = encrypted_token
        await session.commit()
        await session.refresh(db_token)
        return True


async def get_provider_token(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider: str
) -> Optional[ProviderToken]:
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            and_(
                ProviderToken.user_id == user_id,
                ProviderToken.provider == provider,
            )
        )
        result = await session.exec(stmt)  # type: ignore
        provider_token: ProviderToken = result.scalar_one_or_none()
        return provider_token if provider_token else None


async def get_provider_tokens_by_prefix(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider_prefix: str
) -> list[ProviderToken]:
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            and_(
                ProviderToken.user_id == user_id,
                ProviderToken.provider.like(f"{provider_prefix}%"),  # type: ignore
            )
        )
        result = await session.exec(stmt)  # type: ignore
        return list(result.scalars().all())


async def delete_provider_token(pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider: str):
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            and_(
                ProviderToken.user_id == user_id,
                ProviderToken.provider == provider,
            )
        )
        result = await session.exec(stmt)  # type: ignore
        token = result.scalar_one_or_none()
        if token:
            await session.delete(token)
            await session.commit()


async def delete_provider_tokens_by_prefix(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, provider_prefix: str
):
    async with AsyncSession(pg_engine) as session:
        stmt = select(ProviderToken).where(
            and_(
                ProviderToken.user_id == user_id,
                ProviderToken.provider.like(f"{provider_prefix}%"),  # type: ignore
            )
        )
        result = await session.exec(stmt)  # type: ignore
        tokens = list(result.scalars().all())
        for token in tokens:
            await session.delete(token)
        if tokens:
            await session.commit()
