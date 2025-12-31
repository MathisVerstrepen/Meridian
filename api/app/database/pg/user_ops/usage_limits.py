from database.pg.models import Graph, User
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession


async def check_free_tier_canvas_limit(pg_engine: SQLAlchemyAsyncEngine, user_id: str):
    async with AsyncSession(pg_engine) as session:
        user = await session.get(User, user_id)

        if user and user.plan_type == "free":
            count_stmt = (
                select(func.count())
                .select_from(Graph)
                .where(and_(Graph.user_id == user_id, Graph.temporary == False))  # noqa: E712
            )
            count_result = await session.exec(count_stmt)  # type: ignore
            count = count_result.one()[0]

            if count >= 5:
                raise HTTPException(status_code=403, detail="FREE_TIER_CANVAS_LIMIT_REACHED")


async def validate_premium_nodes(pg_engine: SQLAlchemyAsyncEngine, user_id: str, nodes: list):
    async with AsyncSession(pg_engine) as session:
        user = await session.get(User, user_id)
        if user and user.plan_type == "free":
            for node in nodes:
                if node.type == "github":
                    raise HTTPException(status_code=403, detail="PREMIUM_FEATURE_GITHUB_NODE")
