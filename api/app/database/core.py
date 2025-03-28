from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

import os


async def get_async_engine(echo: bool = False):
    """
    Create and return an asynchronous SQLModel engine.

    This function creates an asynchronous SQLModel engine using the database URL
    specified in the DATABASE_URL environment variable.

    Args:
        echo (bool): If True, the engine will log all statements. Defaults to False.

    Returns:
        AsyncEngine: A SQLModel async engine instance connected to the database.

    Raises:
        ValueError: If the DATABASE_URL environment variable is not set.

    Example:
        ```python
        engine = await get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        ```
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    if not any(
        driver in database_url
        for driver in ["+asyncpg", "+aiomysql", "+aiosqlite", "+asyncmy"]
    ):
        print(
            f"Warning: DATABASE_URL '{database_url}' does not seem to use a common async driver "
            "(e.g., +asyncpg, +aiomysql). Ensure it's configured for asyncio."
        )

    engine = create_async_engine(database_url, echo=echo)
    return engine


async def init_db(engine: SQLAlchemyAsyncEngine):
    """
    Initialize the database by creating all tables defined in SQLModel models.

    This function creates all tables in the database that are defined in the
    SQLModel models. It uses the provided engine to connect to the database.

    Args:
        engine (AsyncEngine): The SQLModel async engine instance connected to the database.

    Example:
        ```python
        from sqlmodel import SQLModel
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = await get_async_engine()
        await init_db(engine)
        ```
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
