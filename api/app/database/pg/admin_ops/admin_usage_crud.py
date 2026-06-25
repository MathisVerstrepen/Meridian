import uuid
from datetime import datetime
from typing import Any, cast

from database.pg.models import (
    Graph,
    ImageGenerationJob,
    QueryTypeEnum,
    ToolCall,
    User,
    UserQueryUsage,
    UserStorageUsage,
)
from models.adminDTO import (
    AdminGraphUsageStats,
    AdminMediaGenerationUsage,
    AdminQueryUsageStats,
    AdminStorageUsageStats,
    AdminUsageDashboardResponse,
    AdminUserUsageStats,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

MEDIA_JOB_STATUSES = ("pending", "processing", "retrying", "completed", "failed", "cancelled")


def _build_media_usage(
    status_counts: dict[str, int], recent_counts: dict[str, int]
) -> AdminMediaGenerationUsage:
    return AdminMediaGenerationUsage(
        total=sum(status_counts.values()),
        recent_total=sum(recent_counts.values()),
        pending=status_counts.get("pending", 0),
        processing=status_counts.get("processing", 0),
        retrying=status_counts.get("retrying", 0),
        completed=status_counts.get("completed", 0),
        failed=status_counts.get("failed", 0),
        cancelled=status_counts.get("cancelled", 0),
    )


async def get_admin_usage_dashboard(
    pg_engine: SQLAlchemyAsyncEngine,
    active_since: datetime,
    active_days: int,
) -> AdminUsageDashboardResponse:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        total_users = await session.scalar(select(func.count()).select_from(User)) or 0
        new_users = (
            await session.scalar(
                select(func.count())
                .select_from(User)
                .where(cast(Any, User.created_at) >= active_since)
            )
            or 0
        )
        verified_users = (
            await session.scalar(
                select(func.count()).select_from(User).where(cast(Any, User.is_verified).is_(True))
            )
            or 0
        )
        admin_users = (
            await session.scalar(
                select(func.count()).select_from(User).where(cast(Any, User.is_admin).is_(True))
            )
            or 0
        )
        suspended_users = (
            await session.scalar(
                select(func.count()).select_from(User).where(cast(Any, User.is_suspended).is_(True))
            )
            or 0
        )
        free_plan_users = (
            await session.scalar(
                select(func.count()).select_from(User).where(cast(Any, User.plan_type) == "free")
            )
            or 0
        )
        premium_plan_users = (
            await session.scalar(
                select(func.count()).select_from(User).where(cast(Any, User.plan_type) == "premium")
            )
            or 0
        )

        graph_count = (
            await session.scalar(
                select(func.count()).select_from(Graph).where(col(Graph.temporary).is_(False))
            )
            or 0
        )
        active_graph_count = (
            await session.scalar(
                select(func.count())
                .select_from(Graph)
                .where(
                    col(Graph.temporary).is_(False),
                    cast(Any, Graph.updated_at) >= active_since,
                )
            )
            or 0
        )
        created_graph_count = (
            await session.scalar(
                select(func.count())
                .select_from(Graph)
                .where(
                    col(Graph.temporary).is_(False),
                    cast(Any, Graph.created_at) >= active_since,
                )
            )
            or 0
        )
        pinned_graph_count = (
            await session.scalar(
                select(func.count())
                .select_from(Graph)
                .where(col(Graph.temporary).is_(False), cast(Any, Graph.pinned).is_(True))
            )
            or 0
        )
        temporary_graph_count = (
            await session.scalar(
                select(func.count()).select_from(Graph).where(col(Graph.temporary).is_(True))
            )
            or 0
        )

        active_user_ids: set[uuid.UUID] = set()

        graph_users_result = await session.execute(
            select(cast(Any, Graph.user_id)).where(
                col(Graph.user_id).is_not(None),
                col(Graph.temporary).is_(False),
                cast(Any, Graph.updated_at) >= active_since,
            )
        )
        active_user_ids.update(user_id for user_id in graph_users_result.scalars().all() if user_id)

        media_users_result = await session.execute(
            select(cast(Any, ImageGenerationJob.user_id)).where(
                cast(Any, ImageGenerationJob.created_at) >= active_since
            )
        )
        active_user_ids.update(media_users_result.scalars().all())

        tool_users_result = await session.execute(
            select(cast(Any, ToolCall.user_id)).where(
                cast(Any, ToolCall.created_at) >= active_since
            )
        )
        active_user_ids.update(tool_users_result.scalars().all())

        web_search_usage = (
            await session.scalar(
                select(func.coalesce(func.sum(cast(Any, UserQueryUsage.used_queries)), 0))
                .select_from(UserQueryUsage)
                .where(cast(Any, UserQueryUsage.query_type) == QueryTypeEnum.WEB_SEARCH.value)
            )
            or 0
        )
        link_extraction_usage = (
            await session.scalar(
                select(func.coalesce(func.sum(cast(Any, UserQueryUsage.used_queries)), 0))
                .select_from(UserQueryUsage)
                .where(cast(Any, UserQueryUsage.query_type) == QueryTypeEnum.LINK_EXTRACTION.value)
            )
            or 0
        )
        web_search_users = (
            await session.scalar(
                select(func.count())
                .select_from(UserQueryUsage)
                .where(cast(Any, UserQueryUsage.query_type) == QueryTypeEnum.WEB_SEARCH.value)
            )
            or 0
        )
        link_extraction_users = (
            await session.scalar(
                select(func.count())
                .select_from(UserQueryUsage)
                .where(cast(Any, UserQueryUsage.query_type) == QueryTypeEnum.LINK_EXTRACTION.value)
            )
            or 0
        )
        storage_used_bytes = (
            await session.scalar(
                select(
                    func.coalesce(func.sum(cast(Any, UserStorageUsage.total_bytes_used)), 0)
                ).select_from(UserStorageUsage)
            )
            or 0
        )
        storage_users = (
            await session.scalar(
                select(func.count())
                .select_from(UserStorageUsage)
                .where(cast(Any, UserStorageUsage.total_bytes_used) > 0)
            )
            or 0
        )

        media_counts: dict[str, dict[str, int]] = {
            "image": {status: 0 for status in MEDIA_JOB_STATUSES},
            "video": {status: 0 for status in MEDIA_JOB_STATUSES},
        }
        recent_media_counts: dict[str, dict[str, int]] = {
            "image": {status: 0 for status in MEDIA_JOB_STATUSES},
            "video": {status: 0 for status in MEDIA_JOB_STATUSES},
        }
        media_usage_result = await session.execute(
            select(
                cast(Any, ImageGenerationJob.media_type),
                cast(Any, ImageGenerationJob.status),
                func.count(),
            )
            .select_from(ImageGenerationJob)
            .group_by(
                cast(Any, ImageGenerationJob.media_type), cast(Any, ImageGenerationJob.status)
            )
        )

        for media_type, status, count in media_usage_result.all():
            if media_type not in media_counts:
                media_counts[media_type] = {}
            media_counts[media_type][status] = int(count)

        recent_media_usage_result = await session.execute(
            select(
                cast(Any, ImageGenerationJob.media_type),
                cast(Any, ImageGenerationJob.status),
                func.count(),
            )
            .select_from(ImageGenerationJob)
            .where(cast(Any, ImageGenerationJob.created_at) >= active_since)
            .group_by(
                cast(Any, ImageGenerationJob.media_type), cast(Any, ImageGenerationJob.status)
            )
        )

        for media_type, status, count in recent_media_usage_result.all():
            if media_type not in recent_media_counts:
                recent_media_counts[media_type] = {}
            recent_media_counts[media_type][status] = int(count)

        return AdminUsageDashboardResponse(
            total_users=total_users,
            active_users=len(active_user_ids),
            active_days=active_days,
            graph_count=graph_count,
            users=AdminUserUsageStats(
                total=total_users,
                active=len(active_user_ids),
                active_days=active_days,
                new_users=new_users,
                verified=verified_users,
                unverified=max(total_users - verified_users, 0),
                admins=admin_users,
                suspended=suspended_users,
                free_plan=free_plan_users,
                premium_plan=premium_plan_users,
            ),
            graphs=AdminGraphUsageStats(
                total=graph_count,
                active=active_graph_count,
                active_days=active_days,
                created=created_graph_count,
                pinned=pinned_graph_count,
                temporary=temporary_graph_count,
            ),
            query_usage=AdminQueryUsageStats(
                web_search_used=web_search_usage,
                link_extraction_used=link_extraction_usage,
                users_with_web_search_usage=web_search_users,
                users_with_link_extraction_usage=link_extraction_users,
            ),
            storage=AdminStorageUsageStats(
                used_bytes=storage_used_bytes,
                users_with_storage=storage_users,
            ),
            image_generation=_build_media_usage(
                media_counts["image"], recent_media_counts["image"]
            ),
            video_generation=_build_media_usage(
                media_counts["video"], recent_media_counts["video"]
            ),
        )
