from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
import logging

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
