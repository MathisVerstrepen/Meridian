import logging
import uuid
from typing import List

from database.pg.models import PromptTemplate, User
from fastapi import HTTPException
from models.auth import ProviderEnum
from models.usersDTO import PromptTemplateCreate, PromptTemplateUpdate
from pydantic import BaseModel, Field
from sqlalchemy import select, update
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


async def create_prompt_template(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, template_data: PromptTemplateCreate
) -> PromptTemplate:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        db_template = PromptTemplate.model_validate(template_data, update={"user_id": user_id})
        session.add(db_template)
        await session.commit()
        await session.refresh(db_template)
        return db_template


async def get_all_prompt_templates_for_user(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> List[PromptTemplate]:
    async with AsyncSession(pg_engine) as session:
        stmt = select(PromptTemplate).where(and_(PromptTemplate.user_id == user_id))
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().all()  # type: ignore


async def get_public_prompt_templates(
    pg_engine: SQLAlchemyAsyncEngine, exclude_user_id: uuid.UUID | None = None
) -> List[PromptTemplate]:
    async with AsyncSession(pg_engine) as session:
        conditions = [PromptTemplate.is_public == True]
        if exclude_user_id:
            conditions.append(PromptTemplate.user_id != exclude_user_id)

        stmt = select(PromptTemplate).where(and_(*conditions))
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().all()  # type: ignore


async def get_prompt_template_by_id(
    pg_engine: SQLAlchemyAsyncEngine, template_id: uuid.UUID
) -> PromptTemplate | None:
    async with AsyncSession(pg_engine) as session:
        return await session.get(PromptTemplate, template_id)


async def update_prompt_template(
    db_template: PromptTemplate,
    template_data: PromptTemplateUpdate,
    pg_engine: SQLAlchemyAsyncEngine,
) -> PromptTemplate:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        update_data = template_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_template, key, value)
        session.add(db_template)
        await session.commit()
        await session.refresh(db_template)
        return db_template


async def delete_prompt_template(
    db_template: PromptTemplate, pg_engine: SQLAlchemyAsyncEngine
) -> None:
    async with AsyncSession(pg_engine) as session:
        await session.delete(db_template)
        await session.commit()
