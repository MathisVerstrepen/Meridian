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
from pydantic import BaseModel


logger = logging.getLogger("uvicorn.error")


class UserUsageInfo(BaseModel):
    """Data Transfer Object for returning usage info safely to the API layer."""

    used_queries: int
    limit: int
    billing_period_start: datetime
    billing_period_end: datetime


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


async def _get_or_create_and_reset_record(
    session: AsyncSession, user: User, query_type: QueryTypeEnum, for_update: bool = False
) -> UserQueryUsage:
    """
    Retrieves a usage record, creating or resetting it if necessary.
    Can lock the row for an atomic update if `for_update` is True.
    """
    stmt = select(UserQueryUsage).where(
        UserQueryUsage.user_id == user.id, UserQueryUsage.query_type == query_type.value
    )
    if for_update:
        stmt = stmt.with_for_update()

    result = await session.execute(stmt)
    usage_record = result.scalar_one_or_none()

    start_date, end_date = _calculate_current_billing_period(user.created_at)

    if usage_record:
        # If the record is outside the current billing period, reset it
        if datetime.now(timezone.utc) > usage_record.billing_period_end:
            usage_record.used_queries = 0
            usage_record.billing_period_start = start_date
            usage_record.billing_period_end = end_date
            session.add(usage_record)
            await session.flush()
    else:
        # Create a new record if one doesn't exist
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
) -> UserUsageInfo:
    """
    Public function to retrieve a user's usage record for a specific query type.
    Returns a safe DTO instead of an ORM model.
    """
    async with AsyncSession(pg_engine) as session:
        usage_record = await _get_or_create_and_reset_record(session, user, query_type)
        limit = PLAN_LIMITS.get(user.plan_type, {}).get(query_type.value, 0)

        usage_info = UserUsageInfo(
            used_queries=usage_record.used_queries,
            limit=limit,
            billing_period_start=usage_record.billing_period_start,
            billing_period_end=usage_record.billing_period_end,
        )
        await session.commit()
        return usage_info


async def check_and_increment_query_usage(
    pg_engine: SQLAlchemyAsyncEngine, user_id_str: str, query_type: QueryTypeEnum
):
    """
    Atomically checks if a user can perform a query and increments their usage count.
    This operation is safe from race conditions.
    Raises an HTTPException if the user has reached their query limit.
    """
    user_id = uuid.UUID(user_id_str)
    async with AsyncSession(pg_engine) as session:
        async with session.begin():  # Start a transaction
            user = await session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Get the record with a lock to ensure atomicity
            usage_record = await _get_or_create_and_reset_record(
                session, user, query_type, for_update=True
            )

            limit = PLAN_LIMITS.get(user.plan_type, {}).get(query_type.value, 0)

            if usage_record.used_queries >= limit:
                logger.warning(
                    f"User {user_id} exceeded query limit for {query_type.value}. "
                    f"Used: {usage_record.used_queries}, Limit: {limit}"
                )
                raise HTTPException(
                    status_code=429, detail="Query limit for this billing period has been reached."
                )

            usage_record.used_queries += 1
            session.add(usage_record)
