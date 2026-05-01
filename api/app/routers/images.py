import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO
from math import gcd
from pathlib import Path
from typing import Any, Optional, cast

import httpx
from database.pg.file_ops.file_crud import create_db_file, get_root_folder_for_user
from database.pg.models import Files, ImageGenerationJob
from database.pg.user_ops.storage_crud import check_and_reserve_storage, release_storage
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from PIL import Image
from pydantic import BaseModel, Field
from services.auth import get_current_user_id
from services.files import delete_file_from_disk, save_file_to_disk
from services.inference import get_user_inference_credentials
from services.provider_image_generation import (
    ImageGenerationProviderError,
    generate_image_with_provider,
)
from services.tools.image_generation import _build_image_content_payload
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/images", tags=["images"])

ASPECT_RATIOS = {"1:1", "16:9", "4:3", "3:4", "9:16"}
RESOLUTIONS = {"1K", "2K", "4K"}
MAX_TASKS_PER_BATCH = 24
MAX_PARALLEL_GENERATIONS = 4
RATE_LIMIT_RETRY_BASE_SECONDS = 30
RATE_LIMIT_RETRY_MAX_SECONDS = 300
TRANSIENT_PROVIDER_RETRY_BASE_SECONDS = 10
TRANSIENT_PROVIDER_RETRY_MAX_SECONDS = 120


class ImageGenerationTaskPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    effective_prompt: Optional[str] = Field(default=None, max_length=10000)
    model: str = Field(min_length=1, max_length=255)
    aspect_ratio: str = "1:1"
    resolution: str = "1K"
    style_preset: Optional[str] = Field(default=None, max_length=64)
    source_image_ids: list[str] = Field(default_factory=list)


class CreateImageJobsPayload(BaseModel):
    tasks: list[ImageGenerationTaskPayload] = Field(min_length=1, max_length=MAX_TASKS_PER_BATCH)


class ImageGenerationJobResponse(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    status: str
    prompt: str
    effective_prompt: str
    model: str
    aspect_ratio: str
    resolution: str
    actual_width: Optional[int]
    actual_height: Optional[int]
    actual_aspect_ratio: Optional[str]
    style_preset: Optional[str]
    source_image_ids: list[str]
    file_id: Optional[uuid.UUID]
    error: Optional[str]
    attempts: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class CreateImageJobsResponse(BaseModel):
    job_id: uuid.UUID
    tasks: list[ImageGenerationJobResponse]


class ImageBatchStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    total: int
    completed: int
    failed: int
    processing: int
    pending: int
    tasks: list[ImageGenerationJobResponse]


class GeneratedImageGalleryItem(BaseModel):
    id: uuid.UUID
    name: str
    path: str
    size: Optional[int]
    content_type: Optional[str]
    created_at: datetime
    updated_at: datetime
    prompt: Optional[str] = None
    effective_prompt: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    actual_width: Optional[int] = None
    actual_height: Optional[int] = None
    actual_aspect_ratio: Optional[str] = None
    style_preset: Optional[str] = None
    source_image_ids: list[str] = Field(default_factory=list)


class GeneratedImageGalleryResponse(BaseModel):
    total: int
    items: list[GeneratedImageGalleryItem]


def _is_rate_limit_error(exc: ImageGenerationProviderError) -> bool:
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "rate limit" in message


def _is_transient_provider_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current:
        if isinstance(current, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        current = current.__cause__ or current.__context__

    message = str(exc).lower()
    return "connect timeout" in message or "timed out" in message or "connection error" in message


def _is_empty_image_result_error(exc: ImageGenerationProviderError) -> bool:
    message = str(exc).lower()
    if _is_codex_auth_error(exc):
        return False
    return (
        "no images returned" in message
        or "no image generation result" in message
        or "image url missing" in message
        or "completed without returning an image" in message
    )


def _is_codex_auth_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "openai codex authentication" in message
        or "failed to refresh token" in message
        or "refresh_token_reused" in message
        or "your refresh token has already been used" in message
    )


def _get_model_output_modalities(request: Request, model_id: str) -> list[str] | None:
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


def _codex_auth_failed_message() -> str:
    return (
        "OpenAI Codex authentication failed while refreshing token. "
        "Sign in again and update your Codex auth.json before generating images."
    )


def _rate_limit_retry_message(delay_seconds: int) -> str:
    return f"Rate limited by image provider. Retrying in {delay_seconds}s."


def _rate_limit_failed_message(attempts: int) -> str:
    return (
        f"Rate limited by image provider after {attempts} attempts. "
        "Try again later or reduce batch size."
    )


def _transient_provider_retry_message(delay_seconds: int) -> str:
    return f"Image provider connection timed out. Retrying in {delay_seconds}s."


def _transient_provider_failed_message(attempts: int) -> str:
    return (
        f"Image provider stayed unreachable after {attempts} attempts. "
        "Try again later or reduce batch size."
    )


def _empty_image_result_retry_message(delay_seconds: int) -> str:
    return f"Image provider returned no image. Retrying in {delay_seconds}s."


def _empty_image_result_failed_message(attempts: int) -> str:
    return (
        f"Image provider returned no image after {attempts} attempts. "
        "Try again later or choose another model."
    )


def _measure_image_dimensions(image_bytes: bytes) -> tuple[int, int, str]:
    with Image.open(BytesIO(image_bytes)) as image:
        width, height = image.size

    divisor = gcd(width, height) or 1
    return width, height, f"{width // divisor}:{height // divisor}"


def _job_response(job: ImageGenerationJob) -> ImageGenerationJobResponse:
    return ImageGenerationJobResponse(
        id=job.id,
        batch_id=job.batch_id,
        status=job.status,
        prompt=job.prompt,
        effective_prompt=job.effective_prompt,
        model=job.model,
        aspect_ratio=job.aspect_ratio,
        resolution=job.resolution,
        actual_width=job.actual_width,
        actual_height=job.actual_height,
        actual_aspect_ratio=job.actual_aspect_ratio,
        style_preset=job.style_preset,
        source_image_ids=job.source_image_ids,
        file_id=job.file_id,
        error=job.error,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


async def _send_job_update(connection_manager: Any, job: ImageGenerationJob) -> None:
    await connection_manager.send_to_user(
        str(job.user_id),
        {
            "type": "image_generation_job_update",
            "payload": _job_response(job).model_dump(mode="json"),
        },
    )


def _batch_status(jobs: list[ImageGenerationJob]) -> str:
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


async def _get_batch_jobs(
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


async def _get_job(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    job_id: uuid.UUID,
) -> Optional[ImageGenerationJob]:
    async with AsyncSession(pg_engine) as session:
        return await session.get(ImageGenerationJob, job_id)


async def _is_job_cancelled(pg_engine: SQLAlchemyAsyncEngine, job_id: uuid.UUID) -> bool:
    job = await _get_job(pg_engine, job_id=job_id)
    return bool(job and job.status == "cancelled")


async def _set_job_state(
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
            await _send_job_update(connection_manager, job)


async def _create_generated_image_file(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    prompt: str,
    source_image_ids: list[str],
    image_bytes: bytes,
    extension: str,
) -> Files:
    await check_and_reserve_storage(pg_engine, user_id, len(image_bytes))
    unique_filename = None
    try:
        filename = f"generated_{uuid.uuid4().hex}.{extension}"
        unique_filename = await save_file_to_disk(
            user_id=user_id,
            file_contents=image_bytes,
            original_filename=filename,
            subdirectory="generated_images",
        )

        root_folder = await get_root_folder_for_user(pg_engine, user_id)
        if not root_folder:
            raise HTTPException(status_code=404, detail="Root folder not found for user.")

        return await create_db_file(
            pg_engine=pg_engine,
            user_id=user_id,
            parent_id=root_folder.id,
            name=(
                f"Context: {prompt[:30]}..."
                if source_image_ids
                else f"Gen: {prompt[:30]}.{extension}"
            ),
            file_path=str(Path("generated_images") / unique_filename),
            size=len(image_bytes),
            content_type=f"image/{extension}",
            hash=hashlib.sha256(image_bytes).hexdigest(),
        )
    except Exception:
        if unique_filename:
            await delete_file_from_disk(user_id, unique_filename, subdirectory="generated_images")
        await release_storage(pg_engine, user_id, len(image_bytes))
        raise


async def _run_image_generation_job(request: Request, job_id: uuid.UUID) -> None:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    connection_manager = request.app.state.connection_manager
    job = await _get_job(pg_engine, job_id=job_id)
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
        await _set_job_state(
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
        if await _is_job_cancelled(pg_engine, job.id):
            return
        await _set_job_state(
            pg_engine,
            connection_manager=connection_manager,
            job_id=job.id,
            status_value="processing",
            attempts=attempt,
            error=None,
        )
        if await _is_job_cancelled(pg_engine, job.id):
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
                output_modalities=_get_model_output_modalities(request, job.model),
            )
            if await _is_job_cancelled(pg_engine, job.id):
                return
            actual_width, actual_height, actual_aspect_ratio = _measure_image_dimensions(
                generated_image.image_bytes
            )
            new_file = await _create_generated_image_file(
                pg_engine=pg_engine,
                user_id=job.user_id,
                prompt=job.prompt,
                source_image_ids=job.source_image_ids,
                image_bytes=generated_image.image_bytes,
                extension=generated_image.extension,
            )
            await _set_job_state(
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
            is_rate_limit_error = _is_rate_limit_error(exc)
            is_transient_error = _is_transient_provider_error(exc)
            is_codex_auth_error = _is_codex_auth_error(exc)
            is_empty_image_result_error = _is_empty_image_result_error(exc)
            if attempt < max_attempts and (
                is_rate_limit_error or is_transient_error or is_empty_image_result_error
            ):
                delay_seconds = min(
                    (
                        RATE_LIMIT_RETRY_BASE_SECONDS
                        if is_rate_limit_error
                        else TRANSIENT_PROVIDER_RETRY_BASE_SECONDS
                    )
                    * 2 ** (attempt - 1),
                    (
                        RATE_LIMIT_RETRY_MAX_SECONDS
                        if is_rate_limit_error
                        else TRANSIENT_PROVIDER_RETRY_MAX_SECONDS
                    ),
                )
                await _set_job_state(
                    pg_engine,
                    connection_manager=connection_manager,
                    job_id=job.id,
                    status_value="retrying",
                    attempts=attempt,
                    error=(
                        _rate_limit_retry_message(delay_seconds)
                        if is_rate_limit_error
                        else (
                            _transient_provider_retry_message(delay_seconds)
                            if is_transient_error
                            else _empty_image_result_retry_message(delay_seconds)
                        )
                    ),
                )
                await asyncio.sleep(delay_seconds)
                if await _is_job_cancelled(pg_engine, job.id):
                    return
                continue

            await _set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error=(
                    _rate_limit_failed_message(attempt)
                    if is_rate_limit_error
                    else (
                        _transient_provider_failed_message(attempt)
                        if is_transient_error
                        else (
                            _codex_auth_failed_message()
                            if is_codex_auth_error
                            else (
                                _empty_image_result_failed_message(attempt)
                                if is_empty_image_result_error
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
                await _set_job_state(
                    pg_engine,
                    connection_manager=connection_manager,
                    job_id=job.id,
                    status_value="retrying",
                    attempts=attempt,
                    error=_transient_provider_retry_message(delay_seconds),
                )
                logger.warning(
                    "Image playground provider connection failed on attempt %s/%s: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                await asyncio.sleep(delay_seconds)
                if await _is_job_cancelled(pg_engine, job.id):
                    return
                continue

            await _set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error=_transient_provider_failed_message(attempt),
                completed=True,
            )
            return
        except Exception as exc:
            logger.error("Image playground job failed: %s", exc, exc_info=True)
            await _set_job_state(
                pg_engine,
                connection_manager=connection_manager,
                job_id=job.id,
                status_value="failed",
                attempts=attempt,
                error="Internal error during generation.",
                completed=True,
            )
            return


async def _run_image_generation_batch(request: Request, job_ids: list[uuid.UUID]) -> None:
    semaphore = asyncio.Semaphore(MAX_PARALLEL_GENERATIONS)

    async def run_one(job_id: uuid.UUID) -> None:
        async with semaphore:
            await _run_image_generation_job(request, job_id)

    await asyncio.gather(*(run_one(job_id) for job_id in job_ids))


@router.post("/jobs", response_model=CreateImageJobsResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_image_jobs(
    request: Request,
    payload: CreateImageJobsPayload,
    background_tasks: BackgroundTasks,
    user_id_str: str = Depends(get_current_user_id),
) -> CreateImageJobsResponse:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    batch_id = uuid.uuid4()

    jobs: list[ImageGenerationJob] = []
    async with AsyncSession(pg_engine) as session:
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
            )
            session.add(job)
            jobs.append(job)

        await session.commit()
        for job in jobs:
            await session.refresh(job)

    background_tasks.add_task(_run_image_generation_batch, request, [job.id for job in jobs])
    return CreateImageJobsResponse(job_id=batch_id, tasks=[_job_response(job) for job in jobs])


@router.get("/jobs/active", response_model=list[ImageGenerationJobResponse])
async def list_active_image_jobs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    user_id_str: str = Depends(get_current_user_id),
) -> list[ImageGenerationJobResponse]:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine

    async with AsyncSession(pg_engine) as session:
        active_result = await session.exec(
            select(ImageGenerationJob)
            .where(
                and_(
                    ImageGenerationJob.user_id == user_id,
                    col(ImageGenerationJob.status).in_(["pending", "processing", "retrying"]),
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
                    )
                )
                .order_by(col(ImageGenerationJob.updated_at).desc())
                .limit(remaining)
            )
            jobs.extend(failed_result.all())

        return [_job_response(job) for job in jobs]


@router.delete("/jobs/failed", status_code=status.HTTP_204_NO_CONTENT)
async def clear_failed_image_jobs(
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine

    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(ImageGenerationJob).where(
                and_(ImageGenerationJob.user_id == user_id, ImageGenerationJob.status == "failed")
            )
        )
        for job in result.all():
            await session.delete(job)
        await session.commit()


@router.post("/jobs/tasks/{task_id}/retry", response_model=ImageGenerationJobResponse)
async def retry_image_job(
    task_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    user_id_str: str = Depends(get_current_user_id),
) -> ImageGenerationJobResponse:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine

    async with AsyncSession(pg_engine) as session:
        job = await session.get(ImageGenerationJob, task_id)
        if not job or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="Image generation job not found.")
        if job.status != "failed":
            raise HTTPException(status_code=400, detail="Only failed image jobs can be retried.")

        job.status = "pending"
        job.error = None
        job.attempts = 0
        job.file_id = None
        job.completed_at = None
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        await session.commit()
        await session.refresh(job)

    await _send_job_update(request.app.state.connection_manager, job)
    background_tasks.add_task(_run_image_generation_job, request, task_id)
    return _job_response(job)


@router.post("/jobs/tasks/{task_id}/cancel", response_model=ImageGenerationJobResponse)
async def cancel_image_job(
    task_id: uuid.UUID,
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> ImageGenerationJobResponse:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine

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

    await _send_job_update(request.app.state.connection_manager, job)
    return _job_response(job)


@router.delete("/jobs/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_failed_image_job(
    task_id: uuid.UUID,
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine

    async with AsyncSession(pg_engine) as session:
        job = await session.get(ImageGenerationJob, task_id)
        if not job or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="Image generation job not found.")
        if job.status != "failed":
            raise HTTPException(status_code=400, detail="Only failed image jobs can be removed.")

        await session.delete(job)
        await session.commit()


@router.get("/jobs/{job_id}", response_model=ImageBatchStatusResponse)
async def get_image_job_status(
    job_id: uuid.UUID,
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> ImageBatchStatusResponse:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    jobs = await _get_batch_jobs(pg_engine, batch_id=job_id, user_id=user_id)
    if not jobs:
        raise HTTPException(status_code=404, detail="Image generation job not found.")

    return ImageBatchStatusResponse(
        job_id=job_id,
        status=_batch_status(jobs),
        total=len(jobs),
        completed=sum(1 for job in jobs if job.status == "completed"),
        failed=sum(1 for job in jobs if job.status == "failed"),
        processing=sum(1 for job in jobs if job.status in {"processing", "retrying"}),
        pending=sum(1 for job in jobs if job.status == "pending"),
        tasks=[_job_response(job) for job in jobs],
    )


@router.get("/gallery", response_model=GeneratedImageGalleryResponse)
async def list_generated_image_gallery(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None, max_length=200),
    model: Optional[str] = Query(default=None, max_length=255),
    aspect_ratio: Optional[str] = Query(default=None, max_length=32),
    references: Optional[str] = Query(default=None, pattern="^(with|without)$"),
    user_id_str: str = Depends(get_current_user_id),
) -> GeneratedImageGalleryResponse:
    user_id = uuid.UUID(user_id_str)
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    gallery_conditions: list[Any] = [
        Files.user_id == user_id,
        Files.type == "file",
        col(Files.file_path).contains("generated_images/"),
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

    items: list[GeneratedImageGalleryItem] = []
    for file_record, job in rows:
        items.append(
            GeneratedImageGalleryItem(
                id=file_record.id,
                name=file_record.name,
                path=f"/Generated Images/{file_record.name}",
                size=file_record.size,
                content_type=file_record.content_type,
                created_at=file_record.created_at,
                updated_at=file_record.updated_at,
                prompt=job.prompt if job else None,
                effective_prompt=job.effective_prompt if job else None,
                model=job.model if job else None,
                aspect_ratio=job.aspect_ratio if job else None,
                resolution=job.resolution if job else None,
                actual_width=job.actual_width if job else None,
                actual_height=job.actual_height if job else None,
                actual_aspect_ratio=job.actual_aspect_ratio if job else None,
                style_preset=job.style_preset if job else None,
                source_image_ids=job.source_image_ids if job else [],
            )
        )

    return GeneratedImageGalleryResponse(total=total, items=items)
