import logging

from database.pg.models import User
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def update_user_password(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, hashed_password: str
) -> None:
    """
    Updates the user's password in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (str): The ID of the user to update.
        new_password (str): The new password for the user.

    Returns:
        None
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            db_user = await session.get(User, user_id)

            if not db_user:
                raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

            db_user.password = hashed_password
            await session.commit()
