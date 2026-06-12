import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from schemas.images import (
    CreateImageJobsPayload,
    CreateImageJobsResponse,
    CreateVideoJobsPayload,
    CustomImageTonePresetCreate,
    CustomImageTonePresetResponse,
    GeneratedImageGalleryItem,
    GeneratedImageGalleryResponse,
    ImageBatchStatusResponse,
    ImageEditPayload,
    ImageGenerationJobResponse,
)
from services.auth import get_current_user_id
from services.image_playground.edit import edit_image as edit_image_service
from services.image_playground.gallery import list_generated_image_gallery as list_gallery_service
from services.image_playground.gallery import (
    list_generated_video_gallery as list_video_gallery_service,
)
from services.image_playground.jobs import cancel_image_job as cancel_image_job_service
from services.image_playground.jobs import (
    clear_failed_image_jobs as clear_failed_image_jobs_service,
)
from services.image_playground.jobs import create_image_jobs as create_image_jobs_service
from services.image_playground.jobs import create_video_jobs as create_video_jobs_service
from services.image_playground.jobs import (
    dismiss_failed_image_job as dismiss_failed_image_job_service,
)
from services.image_playground.jobs import get_batch_status_response
from services.image_playground.jobs import list_active_image_jobs as list_active_image_jobs_service
from services.image_playground.jobs import retry_image_job as retry_image_job_service
from services.image_playground.jobs import (
    run_image_generation_batch,
    run_image_generation_job,
    run_video_generation_batch,
)
from services.image_playground.tone_presets import (
    create_custom_image_tone_preset as create_tone_preset_service,
)
from services.image_playground.tone_presets import (
    list_custom_image_tone_presets as list_tone_presets_service,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/tone-presets", response_model=list[CustomImageTonePresetResponse])
async def list_custom_image_tone_presets(
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> list[CustomImageTonePresetResponse]:
    presets = await list_tone_presets_service(
        request.app.state.pg_engine,
        user_id=uuid.UUID(user_id_str),
    )
    return [CustomImageTonePresetResponse.model_validate(preset) for preset in presets]


@router.post("/tone-presets", response_model=CustomImageTonePresetResponse)
async def create_custom_image_tone_preset(
    request: Request,
    payload: CustomImageTonePresetCreate,
    user_id_str: str = Depends(get_current_user_id),
) -> CustomImageTonePresetResponse:
    preset = await create_tone_preset_service(
        request.app.state.pg_engine,
        user_id=uuid.UUID(user_id_str),
        payload=payload,
    )
    return CustomImageTonePresetResponse.model_validate(preset)


@router.post("/edit", response_model=GeneratedImageGalleryItem)
async def edit_image(
    request: Request,
    payload: ImageEditPayload,
    user_id_str: str = Depends(get_current_user_id),
) -> GeneratedImageGalleryItem:
    return await edit_image_service(request, payload=payload, user_id=uuid.UUID(user_id_str))


@router.post(
    "/videos/jobs", response_model=CreateImageJobsResponse, status_code=status.HTTP_202_ACCEPTED
)
async def create_video_jobs(
    request: Request,
    payload: CreateVideoJobsPayload,
    background_tasks: BackgroundTasks,
    user_id_str: str = Depends(get_current_user_id),
) -> CreateImageJobsResponse:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    response = await create_video_jobs_service(
        pg_engine,
        payload=payload,
        user_id=uuid.UUID(user_id_str),
    )
    background_tasks.add_task(
        run_video_generation_batch,
        request,
        [task.id for task in response.tasks],
    )
    return response


@router.get("/videos", response_model=GeneratedImageGalleryResponse)
async def list_generated_video_gallery(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id_str: str = Depends(get_current_user_id),
) -> GeneratedImageGalleryResponse:
    return await list_video_gallery_service(
        request.app.state.pg_engine,
        user_id=uuid.UUID(user_id_str),
        limit=limit,
        offset=offset,
    )


@router.post("/jobs", response_model=CreateImageJobsResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_image_jobs(
    request: Request,
    payload: CreateImageJobsPayload,
    background_tasks: BackgroundTasks,
    user_id_str: str = Depends(get_current_user_id),
) -> CreateImageJobsResponse:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    response = await create_image_jobs_service(
        pg_engine,
        payload=payload,
        user_id=uuid.UUID(user_id_str),
    )
    background_tasks.add_task(
        run_image_generation_batch,
        request,
        [task.id for task in response.tasks],
    )
    return response


@router.get("/jobs/active", response_model=list[ImageGenerationJobResponse])
async def list_active_image_jobs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    user_id_str: str = Depends(get_current_user_id),
) -> list[ImageGenerationJobResponse]:
    return await list_active_image_jobs_service(
        request.app.state.pg_engine,
        user_id=uuid.UUID(user_id_str),
        limit=limit,
    )


@router.delete("/jobs/failed", status_code=status.HTTP_204_NO_CONTENT)
async def clear_failed_image_jobs(
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    await clear_failed_image_jobs_service(
        request.app.state.pg_engine,
        user_id=uuid.UUID(user_id_str),
    )


@router.post("/jobs/tasks/{task_id}/retry", response_model=ImageGenerationJobResponse)
async def retry_image_job(
    task_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    user_id_str: str = Depends(get_current_user_id),
) -> ImageGenerationJobResponse:
    response = await retry_image_job_service(
        request.app.state.pg_engine,
        connection_manager=request.app.state.connection_manager,
        task_id=task_id,
        user_id=uuid.UUID(user_id_str),
    )
    if response.media_type == "video":
        background_tasks.add_task(run_video_generation_batch, request, [task_id])
    else:
        background_tasks.add_task(run_image_generation_job, request, task_id)
    return response


@router.post("/jobs/tasks/{task_id}/cancel", response_model=ImageGenerationJobResponse)
async def cancel_image_job(
    task_id: uuid.UUID,
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> ImageGenerationJobResponse:
    return await cancel_image_job_service(
        request.app.state.pg_engine,
        connection_manager=request.app.state.connection_manager,
        task_id=task_id,
        user_id=uuid.UUID(user_id_str),
    )


@router.delete("/jobs/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_failed_image_job(
    task_id: uuid.UUID,
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    await dismiss_failed_image_job_service(
        request.app.state.pg_engine,
        task_id=task_id,
        user_id=uuid.UUID(user_id_str),
    )


@router.get("/jobs/{job_id}", response_model=ImageBatchStatusResponse)
async def get_image_job_status(
    job_id: uuid.UUID,
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
) -> ImageBatchStatusResponse:
    return await get_batch_status_response(
        request.app.state.pg_engine,
        batch_id=job_id,
        user_id=uuid.UUID(user_id_str),
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
    return await list_gallery_service(
        request.app.state.pg_engine,
        user_id=uuid.UUID(user_id_str),
        limit=limit,
        offset=offset,
        search=search,
        model=model,
        aspect_ratio=aspect_ratio,
        references=references,
    )
