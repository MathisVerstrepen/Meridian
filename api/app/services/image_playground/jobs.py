import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

import httpx
from database.pg.models import ImageGenerationJob
from fastapi import HTTPException, Request, status
from schemas.images import (
    CreateImageJobsPayload,
    CreateImageJobsResponse,
    CreateVideoJobsPayload,
    ImageBatchStatusResponse,
    ImageGenerationJobResponse,
)
from services.image_playground.constants import (
    ACTIVE_GENERATION_JOB_STATUSES,
    ASPECT_RATIOS,
    MAX_ACTIVE_GENERATION_JOBS_PER_USER,
    MAX_PARALLEL_GENERATIONS,
    RATE_LIMIT_RETRY_BASE_SECONDS,
    RATE_LIMIT_RETRY_MAX_SECONDS,
    RESOLUTIONS,
    STALE_GENERATION_JOB_SECONDS,
    TRANSIENT_PROVIDER_RETRY_BASE_SECONDS,
    TRANSIENT_PROVIDER_RETRY_MAX_SECONDS,
    VIDEO_ASPECT_RATIOS,
    VIDEO_RESOLUTIONS,
)
from services.image_playground.generated_files import (
    create_generated_image_file,
    create_generated_video_file,
    measure_image_dimensions,
)
from services.image_playground.provider_errors import (
    codex_auth_failed_message,
    empty_image_result_failed_message,
    empty_image_result_retry_message,
    is_codex_auth_error,
    is_empty_image_result_error,
    is_rate_limit_error,
    is_transient_provider_error,
    rate_limit_failed_message,
    rate_limit_retry_message,
    transient_provider_failed_message,
    transient_provider_retry_message,
)
from services.inference import get_user_inference_credentials
from services.provider_image_generation import (
    ImageGenerationProviderError,
    VideoGenerationProviderError,
    generate_image_with_provider,
    generate_video_with_provider,
)
from services.tools.image_generation import (
    _build_image_content_payload,
    _build_video_reference_payload,
)
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")

STALE_GENERATION_JOB_ERROR = (
    "Generation was interrupted by a server restart. Retry the job to run it again."
)


def mark_stale_generation_job_failed(
    job: ImageGenerationJob,
    *,
    recovered_at: datetime,
) -> None:
    job.status = "failed"
    job.error = STALE_GENERATION_JOB_ERROR
    job.updated_at = recovered_at
    job.completed_at = recovered_at


def get_model_output_modalities(request: Request, model_id: str) -> list[str] | None:
    available_models = getattr(request.app.state, "available_models", None)
    models = getattr(available_models, "data", None)
    if not isinstance(models, list):
        return None

    for model in models:
        if getattr(model, "id", None) != model_id:
            continue
        architecture = getattr(model, "architecture", None)
        output_modalities = getattr(architecture, "output_modalities", None)
        if isinstance(output_modalities, list):
            return [modality for modality in output_modalities if isinstance(modality, str)]
        return None
    return None


def job_response(job: ImageGenerationJob) -> ImageGenerationJobResponse:
    return ImageGenerationJobResponse(
        id=job.id,
        batch_id=job.batch_id,
        status=job.status,
        prompt=job.prompt,
        effective_prompt=job.effective_prompt,
        model=job.model,
        media_type=job.media_type,
        aspect_ratio=job.aspect_ratio,
        resolution=job.resolution,
        duration=job.duration,
        generate_audio=getattr(job, "generate_audio", False),
        actual_width=job.actual_width,
        actual_height=job.actual_height,
        actual_aspect_ratio=job.actual_aspect_ratio,
        style_preset=job.style_preset,
        source_image_ids=job.source_image_ids,
        file_id=job.file_id,
        error=job.error,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        is_preview=getattr(job, "is_preview", False),
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


async def send_job_update(connection_manager: Any, job: ImageGenerationJob) -> None:
    await connection_manager.send_to_user(
        str(job.user_id),
        {
            "type": "image_generation_job_update",
            "payload": job_response(job).model_dump(mode="json"),
        },
    )


def batch_status(jobs: list[ImageGenerationJob]) -> str:
    if not jobs:
        return "not_found"
    if all(job.status == "completed" for job in jobs):
        return "completed"
    if all(job.status == "cancelled" for job in jobs):
        return "cancelled"
    if all(job.status in {"completed", "failed", "cancelled"} for job in jobs):
        if any(job.status == "failed" for job in jobs):
            return (
                "failed" if all(job.status == "failed" for job in jobs) else "completed_with_errors"
            )
        return "completed" if any(job.status == "completed" for job in jobs) else "cancelled"
    if any(job.status in {"processing", "retrying"} for job in jobs):
        return "processing"
    return "pending"


async def get_batch_jobs(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[ImageGenerationJob]:
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(ImageGenerationJob)
            .where(
                and_(
                    ImageGenerationJob.batch_id == batch_id,
                    ImageGenerationJob.user_id == user_id,
                )
            )
            .order_by(col(ImageGenerationJob.created_at))
        )
        return list(result.all())


async def get_job(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    job_id: uuid.UUID,
) -> Optional[ImageGenerationJob]:
    async with AsyncSession(pg_engine) as session:
        return await session.get(ImageGenerationJob, job_id)


async def is_job_cancelled(pg_engine: SQLAlchemyAsyncEngine, job_id: uuid.UUID) -> bool:
    job = await get_job(pg_engine, job_id=job_id)
    return bool(job and job.status == "cancelled")


async def count_active_generation_jobs(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    result = await session.exec(
        select(func.count())
        .select_from(ImageGenerationJob)
        .where(
            and_(
                ImageGenerationJob.user_id == user_id,
                col(ImageGenerationJob.status).in_(ACTIVE_GENERATION_JOB_STATUSES),
            )
        )
    )
    return int(result.one())


async def ensure_active_generation_job_capacity(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    requested_jobs: int,
) -> None:
    active_count = await count_active_generation_jobs(session, user_id=user_id)
    if active_count + requested_jobs > MAX_ACTIVE_GENERATION_JOBS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many active generation jobs. "
                f"You can have up to {MAX_ACTIVE_GENERATION_JOBS_PER_USER} pending, "
                "processing, or retrying jobs at once."
            ),
        )


async def set_job_state(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    connection_manager: Optional[Any] = None,
    job_id: uuid.UUID,
    status_value: str,
    attempts: Optional[int] = None,
    file_id: Optional[uuid.UUID] = None,
    actual_width: Optional[int] = None,
    actual_height: Optional[int] = None,
    actual_aspect_ratio: Optional[str] = None,
    error: Optional[str] = None,
    completed: bool = False,
) -> None:
    async with AsyncSession(pg_engine) as session:
        job = await session.get(ImageGenerationJob, job_id)
        if not job:
            return
        if job.status == "cancelled" and status_value != "cancelled":
            return
        job.status = status_value
        job.error = error
        if attempts is not None:
            job.attempts = attempts
        if file_id is not None:
            job.file_id = file_id
        if actual_width is not None:
            job.actual_width = actual_width
        if actual_height is not None:
            job.actual_height = actual_height
        if actual_aspect_ratio is not None:
            job.actual_aspect_ratio = actual_aspect_ratio
        job.updated_at = datetime.now(timezone.utc)
        if completed:
            job.completed_at = datetime.now(timezone.utc)
        session.add(job)
        await session.commit()
        await session.refresh(job)

        if connection_manager:
            await send_job_update(connection_manager, job)


async def recover_stale_image_generation_jobs(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    stale_after_seconds: int = STALE_GENERATION_JOB_SECONDS,
) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    recovered_at = datetime.now(timezone.utc)

    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(ImageGenerationJob).where(
                and_(
                    col(ImageGenerationJob.status).in_(["processing", "retrying"]),
                    ImageGenerationJob.updated_at < cutoff,
                )
            )
        )
        stale_jobs = list(result.all())
        for job in stale_jobs:
            mark_stale_generation_job_failed(job, recovered_at=recovered_at)
            session.add(job)

        await session.commit()
        return len(stale_jobs)


async def run_image_generation_job(request: Request, job_id: uuid.UUID) -> None:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    connection_manager = request.app.state.connection_manager
    job = await get_job(pg_engine, job_id=job_id)
    if not job:
        return
    if job.status == "cancelled":
        return

    image_message_content = await _build_image_content_payload(
        {
            "prompt": job.effective_prompt,
            "source_image_ids": job.source_image_ids,
        },
        user_id=job.user_id,
        pg_engine=pg_engine,
    )
    if isinstance(image_message_content, dict) and image_message_content.get("error"):
        await set_job_state(
            pg_engine,
            connection_manager=connection_manager,
            job_id=job.id,
            status_value="failed",
            error=str(image_message_content["error"]),
            completed=True,
        )
        return
    provider_message_content = cast(str | list[dict[str, Any]], image_message_content)

    credentials = await get_user_inference_credentials(pg_engine, str(job.user_id))
    max_attempts = max(job.max_attempts, 1)

    for attempt in range(1, max_attempts + 1):
        if await is_job_cancelled(pg_engine, job.id):
            return
        await set_job_state(
            pg_engine,
            connection_manager=connection_manager,
            job_id=job.id,
            status_value="processing",
            attempts=attempt,
            error=None,
        )
        if await is_job_cancelled(pg_engine, job.id):
            return
        try:
            generated_image = await generate_image_with_provider(
                credentials=credentials,
                model=job.model,
                message_content=provider_message_content,
                aspect_ratio=job.aspect_ratio,
                resolution=job.resolution,
                source_image_ids=job.source_image_ids,
                http_client=request.app.state.http_client,
                output_modalities=get_model_output_modalities(request, job.model),
            )
            if await is_job_cancelled(pg_engine, job.id):
                return
            actual_width, actual_height, actual_aspect_ratio = measure_image_dimensions(
                generated_image.image_bytes
            )
            new_file = await create_generated_image_file(
                pg_engine=pg_engine,
                user_id=job.user_id,
                prompt=job.prompt,
                source_image_ids=job.source_image_ids,
                image_bytes=generated_image.image_bytes,
                extension=generated_image.extension,
            )
            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="completed",
                attempts=attempt,
                file_id=new_file.id,
                actual_width=actual_width,
                actual_height=actual_height,
                actual_aspect_ratio=actual_aspect_ratio,
                completed=True,
            )
            return
        except ImageGenerationProviderError as exc:
            rate_limited = is_rate_limit_error(exc)
            transient_error = is_transient_provider_error(exc)
            codex_auth_error = is_codex_auth_error(exc)
            empty_image_result = is_empty_image_result_error(exc)
            if attempt < max_attempts and (rate_limited or transient_error or empty_image_result):
                delay_seconds = min(
                    (
                        RATE_LIMIT_RETRY_BASE_SECONDS
                        if rate_limited
                        else TRANSIENT_PROVIDER_RETRY_BASE_SECONDS
                    )
                    * 2 ** (attempt - 1),
                    (
                        RATE_LIMIT_RETRY_MAX_SECONDS
                        if rate_limited
                        else TRANSIENT_PROVIDER_RETRY_MAX_SECONDS
                    ),
                )
                await set_job_state(
                    pg_engine,
                    connection_manager=connection_manager,
                    job_id=job.id,
                    status_value="retrying",
                    attempts=attempt,
                    error=(
                        rate_limit_retry_message(delay_seconds)
                        if rate_limited
                        else (
                            transient_provider_retry_message(delay_seconds)
                            if transient_error
                            else empty_image_result_retry_message(delay_seconds)
                        )
                    ),
                )
                await asyncio.sleep(delay_seconds)
                if await is_job_cancelled(pg_engine, job.id):
                    return
                continue

            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error=(
                    rate_limit_failed_message(attempt)
                    if rate_limited
                    else (
                        transient_provider_failed_message(attempt)
                        if transient_error
                        else (
                            codex_auth_failed_message()
                            if codex_auth_error
                            else (
                                empty_image_result_failed_message(attempt)
                                if empty_image_result
                                else str(exc)
                            )
                        )
                    )
                ),
                completed=True,
            )
            return
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            if attempt < max_attempts:
                delay_seconds = min(
                    TRANSIENT_PROVIDER_RETRY_BASE_SECONDS * 2 ** (attempt - 1),
                    TRANSIENT_PROVIDER_RETRY_MAX_SECONDS,
                )
                await set_job_state(
                    pg_engine,
                    connection_manager=connection_manager,
                    job_id=job.id,
                    status_value="retrying",
                    attempts=attempt,
                    error=transient_provider_retry_message(delay_seconds),
                )
                logger.warning(
                    "Image playground provider connection failed on attempt %s/%s: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                await asyncio.sleep(delay_seconds)
                if await is_job_cancelled(pg_engine, job.id):
                    return
                continue

            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error=transient_provider_failed_message(attempt),
                completed=True,
            )
            return
        except Exception as exc:
            logger.error("Image playground job failed: %s", exc, exc_info=True)
            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error="Internal error during generation.",
                completed=True,
            )
            return


async def run_video_generation_job(request: Request, job_id: uuid.UUID) -> None:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    connection_manager = request.app.state.connection_manager
    job = await get_job(pg_engine, job_id=job_id)
    if not job or job.status == "cancelled":
        return

    reference_payload = await _build_video_reference_payload(
        {"source_image_ids": job.source_image_ids},
        user_id=job.user_id,
        pg_engine=pg_engine,
    )
    if isinstance(reference_payload, dict) and reference_payload.get("error"):
        await set_job_state(
            pg_engine,
            connection_manager=connection_manager,
            job_id=job.id,
            status_value="failed",
            error=str(reference_payload["error"]),
            completed=True,
        )
        return

    credentials = await get_user_inference_credentials(pg_engine, str(job.user_id))
    max_attempts = max(job.max_attempts, 1)

    for attempt in range(1, max_attempts + 1):
        if await is_job_cancelled(pg_engine, job.id):
            return
        await set_job_state(
            pg_engine,
            connection_manager=connection_manager,
            job_id=job.id,
            status_value="processing",
            attempts=attempt,
            error=None,
        )
        if await is_job_cancelled(pg_engine, job.id):
            return
        try:
            generated_video = await generate_video_with_provider(
                credentials=credentials,
                model=job.model,
                prompt=job.effective_prompt,
                aspect_ratio=job.aspect_ratio,
                resolution=job.resolution,
                duration=job.duration,
                generate_audio=job.generate_audio,
                input_references=cast(list[dict[str, Any]], reference_payload),
                http_client=request.app.state.http_client,
            )
            if await is_job_cancelled(pg_engine, job.id):
                return
            new_file = await create_generated_video_file(
                pg_engine=pg_engine,
                user_id=job.user_id,
                prompt=job.prompt,
                source_image_ids=job.source_image_ids,
                video_bytes=generated_video.video_bytes,
                extension=generated_video.extension,
            )
            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="completed",
                attempts=attempt,
                file_id=new_file.id,
                completed=True,
            )
            return
        except VideoGenerationProviderError as exc:
            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error=str(exc),
                completed=True,
            )
            return
        except Exception as exc:
            logger.error("Video playground job failed: %s", exc, exc_info=True)
            await set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error="Internal error during video generation.",
                completed=True,
            )
            return


async def run_image_generation_batch(request: Request, job_ids: list[uuid.UUID]) -> None:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_GENERATIONS)

    async def run_one(job_id: uuid.UUID) -> None:
        async with semaphore:
            await run_image_generation_job(request, job_id)

    await asyncio.gather(*(run_one(job_id) for job_id in job_ids))


async def run_video_generation_batch(request: Request, job_ids: list[uuid.UUID]) -> None:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_GENERATIONS)

    async def run_one(job_id: uuid.UUID) -> None:
        async with semaphore:
            await run_video_generation_job(request, job_id)

    await asyncio.gather(*(run_one(job_id) for job_id in job_ids))


async def create_image_jobs(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    payload: CreateImageJobsPayload,
    user_id: uuid.UUID,
) -> CreateImageJobsResponse:
    batch_id = uuid.uuid4()
    jobs: list[ImageGenerationJob] = []
    async with AsyncSession(pg_engine) as session:
        await ensure_active_generation_job_capacity(
            session,
            user_id=user_id,
            requested_jobs=len(payload.tasks),
        )
        for task in payload.tasks:
            if task.aspect_ratio not in ASPECT_RATIOS:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported aspect ratio: {task.aspect_ratio}"
                )
            if task.resolution not in RESOLUTIONS:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported resolution: {task.resolution}"
                )

            job = ImageGenerationJob(
                batch_id=batch_id,
                user_id=user_id,
                prompt=task.prompt.strip(),
                effective_prompt=(task.effective_prompt or task.prompt).strip(),
                model=task.model.strip(),
                aspect_ratio=task.aspect_ratio,
                resolution=task.resolution,
                style_preset=task.style_preset,
                source_image_ids=[str(image_id) for image_id in task.source_image_ids],
                is_preview=task.is_preview,
            )
            session.add(job)
            jobs.append(job)

        await session.commit()
        for job in jobs:
            await session.refresh(job)

    return CreateImageJobsResponse(job_id=batch_id, tasks=[job_response(job) for job in jobs])


async def create_video_jobs(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    payload: CreateVideoJobsPayload,
    user_id: uuid.UUID,
) -> CreateImageJobsResponse:
    task = payload.task
    if task.aspect_ratio not in VIDEO_ASPECT_RATIOS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported video aspect ratio: {task.aspect_ratio}"
        )
    if task.resolution not in VIDEO_RESOLUTIONS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported video resolution: {task.resolution}"
        )

    batch_id = uuid.uuid4()
    async with AsyncSession(pg_engine) as session:
        await ensure_active_generation_job_capacity(session, user_id=user_id, requested_jobs=1)
        job = ImageGenerationJob(
            batch_id=batch_id,
            user_id=user_id,
            prompt=task.prompt.strip(),
            effective_prompt=task.prompt.strip(),
            model=task.model.strip(),
            media_type="video",
            aspect_ratio=task.aspect_ratio,
            resolution=task.resolution,
            duration=task.duration,
            generate_audio=task.generate_audio,
            source_image_ids=[str(image_id) for image_id in task.source_image_ids],
            max_attempts=1,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    return CreateImageJobsResponse(job_id=batch_id, tasks=[job_response(job)])


async def list_active_image_jobs(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    user_id: uuid.UUID,
    limit: int,
) -> list[ImageGenerationJobResponse]:
    async with AsyncSession(pg_engine) as session:
        active_result = await session.exec(
            select(ImageGenerationJob)
            .where(
                and_(
                    ImageGenerationJob.user_id == user_id,
                    col(ImageGenerationJob.status).in_(["pending", "processing", "retrying"]),
                    col(ImageGenerationJob.is_preview).is_(False),
                )
            )
            .order_by(col(ImageGenerationJob.created_at))
            .limit(limit)
        )
        jobs = list(active_result.all())

        remaining = limit - len(jobs)
        if remaining > 0:
            failed_result = await session.exec(
                select(ImageGenerationJob)
                .where(
                    and_(
                        ImageGenerationJob.user_id == user_id,
                        ImageGenerationJob.status == "failed",
                        col(ImageGenerationJob.is_preview).is_(False),
                    )
                )
                .order_by(col(ImageGenerationJob.updated_at).desc())
                .limit(remaining)
            )
            jobs.extend(failed_result.all())

    return [job_response(job) for job in jobs]


async def clear_failed_image_jobs(pg_engine: SQLAlchemyAsyncEngine, *, user_id: uuid.UUID) -> None:
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(ImageGenerationJob).where(
                and_(ImageGenerationJob.user_id == user_id, ImageGenerationJob.status == "failed")
            )
        )
        for job in result.all():
            await session.delete(job)
        await session.commit()


async def retry_image_job(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    connection_manager: Any,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ImageGenerationJobResponse:
    async with AsyncSession(pg_engine) as session:
        job = await session.get(ImageGenerationJob, task_id)
        if not job or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="Image generation job not found.")
        if job.status != "failed":
            raise HTTPException(status_code=400, detail="Only failed image jobs can be retried.")
        await ensure_active_generation_job_capacity(session, user_id=user_id, requested_jobs=1)

        job.status = "pending"
        job.error = None
        job.attempts = 0
        job.file_id = None
        job.completed_at = None
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        await session.commit()
        await session.refresh(job)

    await send_job_update(connection_manager, job)
    return job_response(job)


async def cancel_image_job(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    connection_manager: Any,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ImageGenerationJobResponse:
    async with AsyncSession(pg_engine) as session:
        job = await session.get(ImageGenerationJob, task_id)
        if not job or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="Image generation job not found.")
        if job.status not in {"pending", "processing", "retrying"}:
            raise HTTPException(status_code=400, detail="Only active image jobs can be cancelled.")

        job.status = "cancelled"
        job.error = "Cancelled by user."
        job.completed_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        await session.commit()
        await session.refresh(job)

    await send_job_update(connection_manager, job)
    return job_response(job)


async def dismiss_failed_image_job(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    async with AsyncSession(pg_engine) as session:
        job = await session.get(ImageGenerationJob, task_id)
        if not job or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="Image generation job not found.")
        if job.status != "failed":
            raise HTTPException(status_code=400, detail="Only failed image jobs can be removed.")

        await session.delete(job)
        await session.commit()


async def get_batch_status_response(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ImageBatchStatusResponse:
    jobs = await get_batch_jobs(pg_engine, batch_id=batch_id, user_id=user_id)
    if not jobs:
        raise HTTPException(status_code=404, detail="Image generation job not found.")

    return ImageBatchStatusResponse(
        job_id=batch_id,
        status=batch_status(jobs),
        total=len(jobs),
        completed=sum(1 for job in jobs if job.status == "completed"),
        failed=sum(1 for job in jobs if job.status == "failed"),
        processing=sum(1 for job in jobs if job.status in {"processing", "retrying"}),
        pending=sum(1 for job in jobs if job.status == "pending"),
        tasks=[job_response(job) for job in jobs],
    )
