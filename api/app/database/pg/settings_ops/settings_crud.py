import json
import logging
import uuid

from database.pg.models import Settings, User
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def update_settings(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID | None, settings_data: dict
) -> User:
    """
    Update user settings in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user whose settings are to be updated.
        settings_data (str): A JSON string containing the settings to update.

    Returns:
        User: The updated User object.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    if user_id is None:
        raise HTTPException(status_code=400, detail="User ID is required")

    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            user = await session.get(User, user_id)

            if not isinstance(user, User):
                raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

            # Update or create settings for the user
            stmt = select(Settings).where(and_(Settings.user_id == user_id))
            result = await session.exec(stmt)  # type: ignore
            settings_row = result.one_or_none()

            if not settings_row:
                settings = Settings(user_id=user_id)
                session.add(settings)
            else:
                settings = settings_row[0]

            settings.settings_data = settings_data
            await session.commit()

            return user


async def get_settings(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> dict:
    """
    Retrieve user settings from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (str): The UUID of the user whose settings are to be retrieved.

    Returns:
        Settings: The Settings object containing the user's settings.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(Settings).where(and_(Settings.user_id == user_id))
        result = await session.exec(stmt)  # type: ignore
        settings = result.one_or_none()

        if not settings:
            raise HTTPException(status_code=404, detail=f"Settings for user {user_id} not found")

        raw_settings: Settings = settings[0]

        settings_data = raw_settings.settings_data
        if isinstance(raw_settings.settings_data, str):
            settings_data = json.loads(raw_settings.settings_data)

        return settings_data
