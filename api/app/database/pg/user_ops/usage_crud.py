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
    The billing cycle anchors to the day of the month the user was created.
    """
    now = datetime.now(timezone.utc)
    anchor_day = user_created_at.day

    # Determine the start of the current billing period
    # Handle cases where anchor_day is > days in current month (e.g., created on 31st)
    try:
        start_date_candidate = now.replace(day=anchor_day)
    except ValueError:
        # This month is shorter than the anchor day month, use last day of month
        last_day_of_month = (now + relativedelta(months=1, day=1)) - relativedelta(days=1)
        start_date_candidate = now.replace(day=last_day_of_month.day)

    if now >= start_date_candidate:
        start_date = start_date_candidate.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # We are in the period that started last month
        last_month = now - relativedelta(months=1)
        try:
            start_date = last_month.replace(
                day=anchor_day, hour=0, minute=0, second=0, microsecond=0
            )
        except ValueError:
            last_day_of_last_month = (last_month + relativedelta(months=1, day=1)) - relativedelta(
                days=1
            )
            start_date = last_month.replace(
                day=last_day_of_last_month.day, hour=0, minute=0, second=0, microsecond=0
            )

    # Determine the end of the current billing period
    end_date = (start_date + relativedelta(months=1)) - relativedelta(seconds=1)

    return start_date, end_date


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
