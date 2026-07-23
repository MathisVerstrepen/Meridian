from datetime import datetime
from typing import Iterable, cast

from database.pg.models import Repository
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, col
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_owned_repository(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider: str,
    repo_name: str,
) -> Repository | None:
    async with AsyncSession(pg_engine) as session:
        statement = select(Repository).where(
            and_(
                Repository.user_id == user_id,
                Repository.provider == provider,
                Repository.repo_name == repo_name,
            )
        )
        result = await session.exec(statement)  # type: ignore
        return cast(Repository | None, result.scalar_one_or_none())


async def get_owned_repositories(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    identities: Iterable[tuple[str, str]],
) -> dict[tuple[str, str], Repository]:
    unique_identities = list(dict.fromkeys(identities))
    if not unique_identities:
        return {}

    async with AsyncSession(pg_engine) as session:
        statement = select(Repository).where(
            and_(
                Repository.user_id == user_id,
                tuple_(col(Repository.provider), col(Repository.repo_name)).in_(unique_identities),
            )
        )
        result = await session.exec(statement)  # type: ignore
        repositories = result.scalars().all()
        return {
            (repository.provider, repository.repo_name): repository for repository in repositories
        }


async def reserve_owned_repository(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider: str,
    repo_name: str,
    clone_url: str,
) -> Repository:
    existing = await get_owned_repository(pg_engine, user_id, provider, repo_name)
    if existing is not None:
        return existing

    async with AsyncSession(pg_engine) as session:
        repository = Repository(
            user_id=user_id,  # type: ignore[arg-type]
            provider=provider,
            repo_name=repo_name,
            clone_url=clone_url,
        )
        session.add(repository)
        try:
            await session.commit()
            await session.refresh(repository)
            return repository
        except IntegrityError:
            await session.rollback()

    concurrent = await get_owned_repository(pg_engine, user_id, provider, repo_name)
    if concurrent is None:
        raise RuntimeError("Repository reservation conflict could not be resolved.")
    return concurrent


async def update_owned_repository_status(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider: str,
    repo_name: str,
    repository_status: str,
    *,
    error_message: str | None,
    last_pulled_at: datetime | None = None,
) -> Repository | None:
    async with AsyncSession(pg_engine) as session:
        statement = select(Repository).where(
            and_(
                Repository.user_id == user_id,
                Repository.provider == provider,
                Repository.repo_name == repo_name,
            )
        )
        result = await session.exec(statement)  # type: ignore
        repository = cast(Repository | None, result.scalar_one_or_none())
        if repository is None:
            return None

        repository.status = repository_status
        repository.error_message = error_message
        if last_pulled_at is not None:
            repository.last_pulled_at = last_pulled_at
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository


async def update_owned_repository_clone_url(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider: str,
    repo_name: str,
    clone_url: str,
) -> Repository | None:
    async with AsyncSession(pg_engine) as session:
        statement = select(Repository).where(
            and_(
                Repository.user_id == user_id,
                Repository.provider == provider,
                Repository.repo_name == repo_name,
            )
        )
        result = await session.exec(statement)  # type: ignore
        repository = cast(Repository | None, result.scalar_one_or_none())
        if repository is None:
            return None
        repository.clone_url = clone_url
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository
