from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
import logging
import uuid

from database.pg.models import User, Settings

logger = logging.getLogger("uvicorn.error")


async def update_settings(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, settings_data: dict
) -> User:
    """
    Update user settings in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user whose settings are to be updated.
        settings_data (dict): A dictionary containing the settings to update.

    Returns:
        User: The updated User object.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            user = await session.get(User, user_id)

            if not user:
                raise HTTPException(
                    status_code=404, detail=f"User with id {user_id} not found"
                )

            # Update or create settings for the user
            stmt = select(Settings).where(Settings.user_id == user_id)
            result = await session.exec(stmt)
            settings_row = result.one_or_none()

            if not settings_row:
                settings = Settings(user_id=user_id)
                session.add(settings)
            else:
                settings = settings_row[0]

            settings.settings_data = settings_data
            await session.commit()

            return user


async def get_settings(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> Settings:
    """
    Retrieve user settings from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user whose settings are to be retrieved.

    Returns:
        Settings: The Settings object containing the user's settings.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(Settings).where(Settings.user_id == user_id)
        result = await session.exec(stmt)
        settings = result.one_or_none()

        if not settings:
            raise HTTPException(
                status_code=404, detail=f"Settings for user {user_id} not found"
            )

        return settings[0]
