from neo4j import AsyncGraphDatabase
import os

async def get_neo4j_async_driver():
    """
    Create and return an asynchronous Neo4j driver.

    This function creates an asynchronous Neo4j driver using the database URL
    specified in the NEO4J_URL environment variable.

    Returns:
        AsyncGraphDatabase: An async Neo4j driver instance connected to the database.

    Raises:
        ValueError: If the NEO4J_URL environment variable is not set.

    Example:
        ```python
        driver = await get_neo4j_async_engine()
        async with driver.session() as session:
            # Perform operations with the session
        ```
    """
    neo4j_uri = os.getenv("NEO4J_URI")
    if not neo4j_uri:
        raise ValueError("NEO4J_URI environment variable not set")
    
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    if not neo4j_user or not neo4j_password:
        raise ValueError("NEO4J_USER and NEO4J_PASSWORD environment variables must be set")

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    return driver