import logging
import uuid

from database.pg.models import User
from fastapi import HTTPException
from models.auth import ProviderEnum
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


class ProviderUserPayload(BaseModel):
    oauth_id: int = Field(..., alias="oauthId")
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = Field(None, alias="avatarUrl")
    password: str | None = None


async def create_user_from_provider(
    pg_engine: SQLAlchemyAsyncEngine,
    payload: ProviderUserPayload,
    provider: ProviderEnum,
) -> User:
    """
    Create a new user in the database from OAuth provider data.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        payload (ProviderUserPayload): The payload containing user data from the OAuth provider.
        provider (str): The name of the OAuth provider (e.g., "github", "google").

    Returns:
        User: The newly created User object.

    Raises:
        HTTPException: If a user with the same OAuth ID already exists.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        async with session.begin():
            existing_user = await get_user_by_provider_id(pg_engine, payload.oauth_id, provider)

            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail=f"User with Provider ID {payload.oauth_id} already exists",
                )

            user = User(
                username=payload.name or f"user_{payload.oauth_id}",
                email=payload.email,
                avatar_url=payload.avatar_url,
                oauth_provider=provider,
                oauth_id=str(payload.oauth_id),
            )
            session.add(user)
            await session.commit()
            return user


async def get_user_by_provider_id(
    pg_engine: SQLAlchemyAsyncEngine, oauth_id: int, provider: ProviderEnum
) -> User | None:
    """
    Retrieve a user by their OAuth ID and provider from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        oauth_id (str): The OAuth ID of the user.
        provider (str): The name of the OAuth provider (e.g., "github", "google").

    Returns:
        User: The User object if found, otherwise None.

    Raises:
        HTTPException: Status 404 if the user with the given OAuth ID and provider is not found.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(User).where(
            and_(User.oauth_id == str(oauth_id), User.oauth_provider == provider)
        )
        result = await session.exec(stmt)  # type: ignore
        user: User = result.scalars().one_or_none()

        if not user:
            return None

        return user


async def get_user_by_username(pg_engine: SQLAlchemyAsyncEngine, username: str) -> User | None:
    """
    Retrieve a user by their username for password-based login.
    This assumes password-based users have 'userpass' as their provider.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        stmt = select(User).where(
            and_(User.username == username, User.oauth_provider == "userpass")
        )
        result = await session.exec(stmt)  # type: ignore
        user_row = result.one_or_none()

        return user_row[0] if user_row else None


async def get_user_by_id(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> User | None:
    """
    Retrieve a user by their ID from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (str): The UUID of the user to retrieve.

    Returns:
        User | None: The User object if found, otherwise None.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        stmt = select(User).where(and_(User.id == user_id))
        result = await session.exec(stmt)  # type: ignore
        user_row = result.one_or_none()
        return user_row[0] if user_row else None


async def does_user_exist(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> bool:
    """
    Check if a user exists in the database by their ID.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (str): The UUID of the user to check.

    Returns:
        bool: True if the user exists, False otherwise.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(User).where(and_(User.id == user_id))
        result = await session.exec(stmt)  # type: ignore
        return result.one_or_none() is not None
