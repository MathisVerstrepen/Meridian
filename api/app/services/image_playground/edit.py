import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO
from math import gcd
from pathlib import Path
from typing import Any

from database.pg.file_ops.file_crud import get_file_by_id
from database.pg.models import ImageGenerationJob
from fastapi import HTTPException, Request
from PIL import Image, ImageOps
from schemas.images import GeneratedImageGalleryItem, ImageEditPayload
from services.files import get_user_storage_path
from services.image_playground.constants import RESOLUTIONS
from services.image_playground.edit_processing import (
    build_image_edit_prompt,
    composite_image_edit_result,
    encode_png,
    get_padded_edit_crop,
    image_bytes_as_data_uri,
)
from services.image_playground.jobs import (
    create_generated_image_file,
    get_job,
    get_model_output_modalities,
    measure_image_dimensions,
    set_job_state,
)
from services.inference import get_user_inference_credentials
from services.provider_image_generation import (
    ImageGenerationProviderError,
    generate_image_with_provider,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def edit_image(
    request: Request,
    *,
    payload: ImageEditPayload,
    user_id: uuid.UUID,
) -> GeneratedImageGalleryItem:
    pg_engine: SQLAlchemyAsyncEngine = request.app.state.pg_engine
    if payload.resolution not in RESOLUTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported resolution: {payload.resolution}")

    source_file = await get_file_by_id(pg_engine, payload.source_image_id, user_id)
    if not source_file or not source_file.file_path:
        raise HTTPException(status_code=404, detail="Source image not found.")
    if source_file.content_type and not source_file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Source file must be an image.")

    source_path = Path(get_user_storage_path(user_id)) / source_file.file_path
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source image file not found on disk.")

    try:
        with Image.open(source_path) as loaded_image:
            original_image = ImageOps.exif_transpose(loaded_image).convert("RGB")
        cropped_image, cropped_mask, crop_box, _ = get_padded_edit_crop(
            original_image,
            payload.selection,
            padding_pct=payload.padding_pct,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read source image.") from exc

    crop_width, crop_height = cropped_image.size
    crop_aspect_divisor = gcd(crop_width, crop_height) or 1
    crop_aspect_ratio = f"{crop_width // crop_aspect_divisor}:{crop_height // crop_aspect_divisor}"
    effective_prompt = build_image_edit_prompt(
        user_prompt=payload.prompt,
        model=payload.model,
        cropped_image=cropped_image,
        cropped_mask=cropped_mask,
    )

    logger.info(effective_prompt)
    logger.info(
        f"Crop box: {crop_box}, aspect ratio: {crop_aspect_ratio}, size: {cropped_image.size}"
    )

    batch_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with AsyncSession(pg_engine) as session:
        job = ImageGenerationJob(
            batch_id=batch_id,
            user_id=user_id,
            status="processing",
            prompt=payload.prompt.strip() or "Remove selected object",
            effective_prompt=effective_prompt,
            model=payload.model.strip(),
            aspect_ratio=crop_aspect_ratio,
            resolution=payload.resolution,
            source_image_ids=[str(payload.source_image_id)],
            attempts=1,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

    try:
        message_content: list[dict[str, Any]] = [
            {"type": "text", "text": job.effective_prompt},
            {"type": "image_url", "image_url": {"url": image_bytes_as_data_uri(cropped_image)}},
        ]
        credentials = await get_user_inference_credentials(pg_engine, str(user_id))
        edited_crop_result = await generate_image_with_provider(
            credentials=credentials,
            model=job.model,
            message_content=message_content,
            aspect_ratio=crop_aspect_ratio,
            resolution=payload.resolution,
            source_image_ids=[str(payload.source_image_id)],
            http_client=request.app.state.http_client,
            output_modalities=get_model_output_modalities(request, job.model),
        )
        with Image.open(BytesIO(edited_crop_result.image_bytes)) as edited_image:
            final_image = composite_image_edit_result(
                original_image,
                edited_image,
                cropped_mask,
                crop_box,
            )
        final_bytes = encode_png(final_image)
        actual_width, actual_height, actual_aspect_ratio = measure_image_dimensions(final_bytes)
        new_file = await create_generated_image_file(
            pg_engine=pg_engine,
            user_id=user_id,
            prompt=job.prompt,
            source_image_ids=job.source_image_ids,
            image_bytes=final_bytes,
            extension="png",
        )
        await set_job_state(
            pg_engine,
            job_id=job.id,
            status_value="completed",
            attempts=1,
            file_id=new_file.id,
            actual_width=actual_width,
            actual_height=actual_height,
            actual_aspect_ratio=actual_aspect_ratio,
            completed=True,
        )
        completed_job = await get_job(pg_engine, job_id=job.id)
        return GeneratedImageGalleryItem(
            id=new_file.id,
            name=new_file.name,
            path=f"/Generated Images/{new_file.name}",
            size=new_file.size,
            content_type=new_file.content_type,
            created_at=new_file.created_at,
            updated_at=new_file.updated_at,
            generation_started_at=completed_job.created_at if completed_job else job.created_at,
            generation_completed_at=completed_job.completed_at if completed_job else None,
            prompt=completed_job.prompt if completed_job else job.prompt,
            effective_prompt=(
                completed_job.effective_prompt if completed_job else job.effective_prompt
            ),
            model=completed_job.model if completed_job else job.model,
            aspect_ratio=completed_job.aspect_ratio if completed_job else crop_aspect_ratio,
            resolution=completed_job.resolution if completed_job else payload.resolution,
            actual_width=actual_width,
            actual_height=actual_height,
            actual_aspect_ratio=actual_aspect_ratio,
            style_preset=None,
            source_image_ids=(
                completed_job.source_image_ids if completed_job else job.source_image_ids
            ),
        )
    except ImageGenerationProviderError as exc:
        await set_job_state(
            pg_engine,
            job_id=job.id,
            status_value="failed",
            attempts=1,
            error=str(exc),
            completed=True,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Image edit failed: %s", exc, exc_info=True)
        await set_job_state(
            pg_engine,
            job_id=job.id,
            status_value="failed",
            attempts=1,
            error="Internal error during image edit.",
            completed=True,
        )
        raise HTTPException(status_code=500, detail="Internal error during image edit.") from exc
