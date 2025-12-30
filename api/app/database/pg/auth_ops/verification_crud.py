import datetime
import uuid
from datetime import timezone

from database.pg.models import User, VerificationToken
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_verification_token(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, email: str, code: str
) -> VerificationToken:
    """
    Creates a new verification token for a user.
    """
    expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=15)

    async with AsyncSession(pg_engine) as session:
        await delete_verification_tokens_for_user(pg_engine, user_id)

        token = VerificationToken(user_id=user_id, email=email, code=code, expires_at=expires_at)
        session.add(token)
        await session.commit()
        await session.refresh(token)
        return token


async def get_verification_token(
    pg_engine: SQLAlchemyAsyncEngine, email: str, code: str
) -> VerificationToken | None:
    """
    Retrieves a verification token by email and code.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(VerificationToken).where(
            and_(VerificationToken.email == email, VerificationToken.code == code)
        )
        result = await session.exec(stmt)  # type: ignore
        return result.scalars().one_or_none()  # type: ignore


async def delete_verification_tokens_for_user(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> None:
    """
    Deletes all verification tokens for a specific user.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = delete(VerificationToken).where(and_(VerificationToken.user_id == user_id))
        await session.exec(stmt)
        await session.commit()


async def mark_user_as_verified(pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID) -> User:
    """
    Updates the user's status to verified.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = update(User).where(and_(User.id == user_id)).values(is_verified=True).returning(User)
        result = await session.exec(stmt)
        user = result.scalar_one()
        await session.commit()
        await session.refresh(user)
        return user  # type: ignore
