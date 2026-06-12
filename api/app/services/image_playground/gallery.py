import uuid
from typing import Any, Optional

from database.pg.models import Files, ImageGenerationJob
from schemas.images import GeneratedImageGalleryItem, GeneratedImageGalleryResponse
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, col, select
from sqlmodel.ext.asyncio.session import AsyncSession


def gallery_item(file_record: Files, job: ImageGenerationJob | None) -> GeneratedImageGalleryItem:
    return GeneratedImageGalleryItem(
        id=file_record.id,
        name=file_record.name,
        path=f"/Generated Images/{file_record.name}",
        size=file_record.size,
        content_type=file_record.content_type,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
        generation_started_at=job.created_at if job else None,
        generation_completed_at=job.completed_at if job else None,
        prompt=job.prompt if job else None,
        effective_prompt=job.effective_prompt if job else None,
        model=job.model if job else None,
        aspect_ratio=job.aspect_ratio if job else None,
        resolution=job.resolution if job else None,
        duration=getattr(job, "duration", None) if job else None,
        generate_audio=getattr(job, "generate_audio", None) if job else None,
        actual_width=job.actual_width if job else None,
        actual_height=job.actual_height if job else None,
        actual_aspect_ratio=job.actual_aspect_ratio if job else None,
        style_preset=job.style_preset if job else None,
        source_image_ids=job.source_image_ids if job else [],
    )


def video_gallery_item(
    file_record: Files, job: ImageGenerationJob | None
) -> GeneratedImageGalleryItem:
    return GeneratedImageGalleryItem(
        id=file_record.id,
        name=file_record.name,
        path=f"/Generated Videos/{file_record.name}",
        size=int(file_record.size) if file_record.size is not None else None,
        content_type=file_record.content_type,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
        generation_started_at=job.created_at if job else None,
        generation_completed_at=job.completed_at if job else file_record.created_at,
        prompt=job.prompt if job else None,
        effective_prompt=job.effective_prompt if job else None,
        model=job.model if job else None,
        aspect_ratio=job.aspect_ratio if job else None,
        resolution=job.resolution if job else None,
        duration=getattr(job, "duration", None) if job else None,
        generate_audio=getattr(job, "generate_audio", None) if job else None,
        actual_width=None,
        actual_height=None,
        actual_aspect_ratio=None,
        style_preset=None,
        source_image_ids=job.source_image_ids if job else [],
    )


async def list_generated_image_gallery(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
    search: Optional[str],
    model: Optional[str],
    aspect_ratio: Optional[str],
    references: Optional[str],
) -> GeneratedImageGalleryResponse:
    gallery_conditions: list[Any] = [
        Files.user_id == user_id,
        Files.type == "file",
        col(Files.file_path).contains("generated_images/"),
        or_(col(ImageGenerationJob.id).is_(None), col(ImageGenerationJob.is_preview).is_(False)),
    ]

    normalized_search = search.strip() if search else None
    if normalized_search:
        search_pattern = f"%{normalized_search}%"
        gallery_conditions.append(
            or_(
                col(Files.name).ilike(search_pattern),
                col(ImageGenerationJob.prompt).ilike(search_pattern),
                col(ImageGenerationJob.effective_prompt).ilike(search_pattern),
            )
        )
    if model:
        gallery_conditions.append(ImageGenerationJob.model == model)
    if aspect_ratio:
        gallery_conditions.append(
            func.coalesce(
                ImageGenerationJob.actual_aspect_ratio,
                ImageGenerationJob.aspect_ratio,
            )
            == aspect_ratio
        )
    if references == "with":
        gallery_conditions.append(func.jsonb_array_length(ImageGenerationJob.source_image_ids) > 0)
    elif references == "without":
        gallery_conditions.append(
            or_(
                col(ImageGenerationJob.id).is_(None),
                func.coalesce(func.jsonb_array_length(ImageGenerationJob.source_image_ids), 0) == 0,
            )
        )

    gallery_filter = and_(*gallery_conditions)

    async with AsyncSession(pg_engine) as session:
        total_result = await session.exec(
            select(func.count())
            .select_from(Files)
            .join(
                ImageGenerationJob, col(ImageGenerationJob.file_id) == col(Files.id), isouter=True
            )
            .where(gallery_filter)
        )
        total = int(total_result.one())

        result = await session.exec(
            select(Files, ImageGenerationJob)
            .join(
                ImageGenerationJob, col(ImageGenerationJob.file_id) == col(Files.id), isouter=True
            )
            .where(gallery_filter)
            .order_by(col(Files.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list(result.all())

    return GeneratedImageGalleryResponse(
        total=total,
        items=[gallery_item(file_record, job) for file_record, job in rows],
    )


async def list_generated_video_gallery(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> GeneratedImageGalleryResponse:
    gallery_filter = and_(
        Files.user_id == user_id,
        Files.type == "file",
        col(Files.file_path).contains("generated_videos/"),
    )

    async with AsyncSession(pg_engine) as session:
        total_result = await session.exec(
            select(func.count()).select_from(Files).where(gallery_filter)
        )
        total = int(total_result.one())

        result = await session.exec(
            select(Files, ImageGenerationJob)
            .join(
                ImageGenerationJob, col(ImageGenerationJob.file_id) == col(Files.id), isouter=True
            )
            .where(gallery_filter)
            .order_by(col(Files.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list(result.all())

    return GeneratedImageGalleryResponse(
        total=total,
        items=[video_gallery_item(file_record, job) for file_record, job in rows],
    )
