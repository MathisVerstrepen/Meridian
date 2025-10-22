import logging
import uuid
from datetime import datetime, timezone

from const.plans import PLAN_LIMITS
from database.pg.models import QueryTypeEnum, User, UserQueryUsage
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


def _calculate_current_billing_period(
    user_created_at: datetime,
) -> tuple[datetime, datetime]:
    """
    Calculates the start and end of the current billing period based on the user's creation date.
    The billing cycle anchors to the day of the month the user was created, handling month-end correctly.
    """
    now = datetime.now(timezone.utc)

    # Calculate how many full months have passed since user creation.
    # This determines which billing cycle we are in.
    diff = relativedelta(now, user_created_at)
    months_offset = diff.years * 12 + diff.months

    # Calculate the potential start of the current billing cycle by adding months to the original creation date.
    # This correctly handles cases like being created on the 31st.
    potential_start = user_created_at + relativedelta(months=months_offset)

    # If 'now' is before this potential start, it means we are still in the previous billing cycle.
    if now < potential_start:
        months_offset -= 1

    # The definitive start date of the current billing period.
    start_date = user_created_at + relativedelta(months=months_offset)

    # The end date is the start of the next period, minus one second.
    next_period_start = user_created_at + relativedelta(months=months_offset + 1)
    end_date = next_period_start.replace(hour=0, minute=0, second=0, microsecond=0) - relativedelta(
        seconds=1
    )

    return start_date.replace(hour=0, minute=0, second=0, microsecond=0), end_date


async def _get_or_create_usage_record_internal(
    session: AsyncSession,
    user: User,
    query_type: QueryTypeEnum,
) -> UserQueryUsage:
    """
    Internal function to retrieve a usage record, creating or resetting it if necessary.
    Requires an active session.
    """
    stmt = select(UserQueryUsage).where(
        UserQueryUsage.user_id == user.id, UserQueryUsage.query_type == query_type.value
    )
    result = await session.execute(stmt)
    usage_record = result.scalar_one_or_none()

    start_date, end_date = _calculate_current_billing_period(user.created_at)

    if usage_record:
        if datetime.now(timezone.utc) > usage_record.billing_period_end:
            usage_record.used_queries = 0
            usage_record.billing_period_start = start_date
            usage_record.billing_period_end = end_date
            session.add(usage_record)
            await session.flush()
    else:
        usage_record = UserQueryUsage(
            user_id=user.id,
            query_type=query_type.value,
            used_queries=0,
            billing_period_start=start_date,
            billing_period_end=end_date,
        )
        session.add(usage_record)
        await session.flush()

    return usage_record


async def get_usage_record(
    pg_engine: SQLAlchemyAsyncEngine,
    user: User,
    query_type: QueryTypeEnum,
) -> UserQueryUsage:
    """
    Public function to retrieve a user's usage record for a specific query type.
    """
    async with AsyncSession(pg_engine) as session:
        return await _get_or_create_usage_record_internal(session, user, query_type)


async def check_and_increment_query_usage(
    pg_engine: SQLAlchemyAsyncEngine, user_id_str: str, query_type: QueryTypeEnum
):
    """
    Checks if a user can perform a query and atomically increments their usage count.
    Raises an HTTPException if the user has reached their query limit.
    """
    user_id = uuid.UUID(user_id_str)
    async with AsyncSession(pg_engine) as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        total_queries = PLAN_LIMITS.get(user.plan_type, {}).get(query_type.value, 0)
        usage_record = await _get_or_create_usage_record_internal(session, user, query_type)

        if usage_record.used_queries >= total_queries:
            logger.warning(
                f"User {user_id} exceeded query limit for {query_type.value}. "
                f"Used: {usage_record.used_queries}, Limit: {total_queries}"
            )
            raise HTTPException(
                status_code=429, detail="Query limit for this billing period has been reached."
            )

        usage_record.used_queries += 1
        session.add(usage_record)
        await session.commit()
