import logging

from database.pg.models import User
from fastapi import HTTPException
from models.auth import ProviderEnum
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, or_
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


async def create_user_with_password(
    pg_engine: SQLAlchemyAsyncEngine,
    username: str,
    email: str,
    hashed_password: str,
) -> User:
    """
    Create a new user with a username and password (userpass provider).

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine.
        username (str): The username.
        email (str): The email address.
        hashed_password (str): The already hashed password.

    Returns:
        User: The created user.

    Raises:
        HTTPException: If username or email is already taken.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        async with session.begin():
            # Check for existing username or email
            stmt = select(User).where(
                or_(
                    and_(User.username == username, User.oauth_provider == "userpass"),
                    User.email == email,
                )
            )
            result = await session.exec(stmt)  # type: ignore
            existing_user_row = result.first()

            if existing_user_row:
                existing_user = existing_user_row[0]
                if existing_user.email == email:
                    raise HTTPException(status_code=409, detail="Email is already registered.")
                raise HTTPException(status_code=409, detail="Username is already taken.")

            user = User(
                username=username,
                email=email,
                password=hashed_password,
                oauth_provider="userpass",
                plan_type="free",
            )
            session.add(user)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise HTTPException(status_code=409, detail="Username or Email already exists.")
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


async def get_user_by_email(
    pg_engine: SQLAlchemyAsyncEngine, email: str, oauth_provider: str
) -> User | None:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        stmt = select(User).where(and_(User.email == email, User.oauth_provider == oauth_provider))
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


async def update_user_avatar_url(
    pg_engine: SQLAlchemyAsyncEngine, user_id: str, avatar_url: str
) -> None:
    """
    Update the avatar URL for a specific user.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = update(User).where(and_(User.id == user_id)).values(avatar_url=avatar_url)
        await session.exec(stmt)  # type: ignore
        await session.commit()


async def update_username(pg_engine: SQLAlchemyAsyncEngine, user_id: str, new_name: str) -> User:
    """
    Update the username for a specific user.
    If the user's provider is 'userpass', it enforces username uniqueness.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        # First, get the user to check their provider
        user = await get_user_by_id(pg_engine, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # If the user is a 'userpass' user, check for username uniqueness
        if user.oauth_provider == "userpass":
            existing_user_with_new_name = await get_user_by_username(pg_engine, new_name)
            if existing_user_with_new_name and str(existing_user_with_new_name.id) != user_id:
                raise HTTPException(status_code=409, detail="Username already taken")

        # Proceed with the update
        stmt = (
            update(User).where(and_(User.id == user_id)).values(username=new_name).returning(User)
        )
        result = await session.exec(stmt)  # type: ignore
        updated_user_data = result.scalar_one()
        await session.commit()
        updated_user = await session.get(User, updated_user_data.id)
        if not updated_user:
            raise HTTPException(status_code=404, detail="Updated user not found")
        return updated_user  # type: ignore


async def update_user_email(pg_engine: SQLAlchemyAsyncEngine, user_id: str, new_email: str) -> None:
    """
    Update the email for a specific user.
    Enforces email uniqueness for 'userpass' provider.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        stmt = select(User).where(and_(User.email == new_email, User.oauth_provider == "userpass"))
        result = await session.exec(stmt)  # type: ignore
        existing_user = result.first()

        if existing_user and str(existing_user[0].id) != user_id:
            raise HTTPException(status_code=409, detail="Email is already registered.")

        update_stmt = update(User).where(and_(User.id == user_id)).values(email=new_email)
        await session.exec(update_stmt)  # type: ignore
        await session.commit()


async def mark_user_as_welcomed(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> None:
    """
    Mark the user as having seen the welcome popup.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = update(User).where(and_(User.id == user_id)).values(has_seen_welcome=True)
        await session.exec(stmt)  # type: ignore
        await session.commit()


async def get_all_users_paginated(
    pg_engine: SQLAlchemyAsyncEngine, page: int, limit: int
) -> tuple[list[User], int]:
    """
    Retrieve all users paginated with total count.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): Async engine.
        page (int): Page number (1-based).
        limit (int): Items per page.

    Returns:
        tuple[list[User], int]: List of users and total count.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        count_stmt = select(func.count()).select_from(User)
        total = await session.scalar(count_stmt) or 0

        offset = (page - 1) * limit
        stmt = (
            select(User)
            .order_by(User.created_at.desc())  # type: ignore
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(stmt)  # type: ignore
        users = result.scalars().all()

        return list(users), total


async def delete_user_by_id(pg_engine: SQLAlchemyAsyncEngine, user_id: str) -> None:
    """
    Delete a user by ID.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): Async engine.
        user_id (str): User ID.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = delete(User).where(and_(User.id == user_id))
        await session.exec(stmt)  # type: ignore
        await session.commit()
