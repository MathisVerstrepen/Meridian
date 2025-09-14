import logging
import os

from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger("uvicorn.error")


async def get_pg_async_engine() -> SQLAlchemyAsyncEngine:
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
    pool_size = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))

    db = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")

    if not db or not user or not password:
        raise ValueError(
            "POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD must be set in config.toml"
        )

    database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    if not any(
        driver in database_url for driver in ["+asyncpg", "+aiomysql", "+aiosqlite", "+asyncmy"]
    ):
        logger.warning(
            f"Warning: DATABASE_URL '{database_url}' does not seem to use a common async driver "
            "(e.g., +asyncpg, +aiomysql). Ensure it's configured for asyncio."
        )

    logger.info(
        f"Creating postgres async engine with pool_size={pool_size}, max_overflow={max_overflow}"
    )

    engine = create_async_engine(
        database_url,
        echo=echo,
        query_cache_size=0,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )
    return engine
