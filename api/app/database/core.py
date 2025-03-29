from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

import os


async def get_async_engine() -> SQLAlchemyAsyncEngine:
    """
    Create and return an asynchronous SQLAlchemy engine.

    This function creates an asynchronous SQLAlchemy engine using the database URL
    specified in the DATABASE_URL environment variable.

    Returns:
        SQLAlchemyAsyncEngine: An async engine instance connected to the database.

    Raises:
        ValueError: If the DATABASE_URL environment variable is not set.

    Example:
        ```python
        engine = await get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        ```
    """
    echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"
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

    engine = create_async_engine(database_url, echo=echo, query_cache_size=0)
    return engine
