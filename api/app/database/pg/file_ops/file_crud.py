import logging
import uuid

from database.pg.models import Files, User
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def add_user_file(
    pg_engine: SQLAlchemyAsyncEngine,
    id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    file_path: str,
    size: int,
    content_type: str,
) -> None:
    """
    Add a file path to the user's files in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user to whom the file belongs.
        file_path (str): The path of the file to add.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            user = await session.get(User, user_id)

            if not user:
                raise HTTPException(status_code=404, detail=f"User with id {user_id} not found")

            file_record = Files(
                id=id,
                user_id=user_id,
                filename=filename,
                file_path=file_path,
                size=size,
                content_type=content_type,
            )
            session.add(file_record)
            await session.commit()


async def get_file_by_id(pg_engine: SQLAlchemyAsyncEngine, file_id: uuid.UUID) -> Files:
    """
    Retrieve a file by its ID from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        file_id (uuid.UUID): The UUID of the file to retrieve.

    Returns:
        Files: The Files object if found, otherwise None.

    Raises:
        HTTPException: Status 404 if the file with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        file_record = await session.get(Files, file_id)

        if not file_record:
            raise HTTPException(status_code=404, detail=f"File with id {file_id} not found")

        return file_record
