import hashlib
import uuid
from io import BytesIO
from math import gcd
from pathlib import Path

from database.pg.file_ops.file_crud import create_db_file, get_root_folder_for_user
from database.pg.models import Files
from database.pg.user_ops.storage_crud import check_and_reserve_storage, release_storage
from fastapi import HTTPException
from PIL import Image
from services.files import delete_file_from_disk, save_file_to_disk
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine


def measure_image_dimensions(image_bytes: bytes) -> tuple[int, int, str]:
    with Image.open(BytesIO(image_bytes)) as image:
        width, height = image.size

    divisor = gcd(width, height) or 1
    return width, height, f"{width // divisor}:{height // divisor}"


async def create_generated_image_file(
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


async def create_generated_video_file(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    prompt: str,
    source_image_ids: list[str],
    video_bytes: bytes,
    extension: str,
) -> Files:
    await check_and_reserve_storage(pg_engine, user_id, len(video_bytes))
    unique_filename = None
    try:
        filename = f"generated_{uuid.uuid4().hex}.{extension}"
        unique_filename = await save_file_to_disk(
            user_id=user_id,
            file_contents=video_bytes,
            original_filename=filename,
            subdirectory="generated_videos",
        )

        root_folder = await get_root_folder_for_user(pg_engine, user_id)
        if not root_folder:
            raise HTTPException(status_code=404, detail="Root folder not found for user.")

        return await create_db_file(
            pg_engine=pg_engine,
            user_id=user_id,
            parent_id=root_folder.id,
            name=(
                f"Video Context: {prompt[:30]}..."
                if source_image_ids
                else f"Video: {prompt[:30]}.{extension}"
            ),
            file_path=str(Path("generated_videos") / unique_filename),
            size=len(video_bytes),
            content_type=f"video/{extension}",
            hash=hashlib.sha256(video_bytes).hexdigest(),
        )
    except Exception:
        if unique_filename:
            await delete_file_from_disk(user_id, unique_filename, subdirectory="generated_videos")
        await release_storage(pg_engine, user_id, len(video_bytes))
        raise
