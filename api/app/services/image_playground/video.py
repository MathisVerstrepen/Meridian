import uuid
from typing import Any, cast

from fastapi import HTTPException, Request
from schemas.images import GeneratedImageGalleryItem, VideoGenerationPayload
from services.image_playground.generated_files import create_generated_video_file
from services.inference import get_user_inference_credentials
from services.provider_image_generation import (
    VideoGenerationProviderError,
    generate_video_with_provider,
)
from services.tools.image_generation import _build_video_reference_payload
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine


async def generate_video(
    request: Request,
    *,
    payload: VideoGenerationPayload,
    user_id: uuid.UUID,
) -> GeneratedImageGalleryItem:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    reference_payload = await _build_video_reference_payload(
        {"source_image_ids": payload.source_image_ids},
        user_id=user_id,
        pg_engine=pg_engine,
    )
    if isinstance(reference_payload, dict) and reference_payload.get("error"):
        raise HTTPException(status_code=400, detail=reference_payload["error"])

    try:
        credentials = await get_user_inference_credentials(pg_engine, str(user_id))
        generated_video = await generate_video_with_provider(
            credentials=credentials,
            model=payload.model,
            prompt=payload.prompt,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
            duration=payload.duration,
            input_references=cast(list[dict[str, Any]], reference_payload),
            http_client=request.app.state.http_client,
        )
    except VideoGenerationProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    file_record = await create_generated_video_file(
        pg_engine=pg_engine,
        user_id=user_id,
        prompt=payload.prompt,
        source_image_ids=payload.source_image_ids,
        video_bytes=generated_video.video_bytes,
        extension=generated_video.extension,
    )

    return GeneratedImageGalleryItem(
        id=file_record.id,
        name=file_record.name,
        path=f"/Generated Videos/{file_record.name}",
        size=file_record.size,
        content_type=file_record.content_type,
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
        generation_started_at=None,
        generation_completed_at=file_record.created_at,
        prompt=payload.prompt,
        effective_prompt=payload.prompt,
        model=payload.model,
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        actual_width=None,
        actual_height=None,
        actual_aspect_ratio=None,
        style_preset=None,
        source_image_ids=payload.source_image_ids,
    )
