import asyncio
import hashlib
import logging
import mimetypes
import os
import uuid
from typing import Optional

import aiofiles
import aiofiles.os
import sentry_sdk
from database.pg.file_ops.file_crud import (
    create_db_folder,
    get_file_by_id,
    get_root_folder_for_user,
    update_file_hash,
)
from database.pg.models import Files
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

USER_FILES_BASE_DIR = "data/user_files"
ALLOWED_RESIZES = ["48x48", "160x160"]

logger = logging.getLogger("uvicorn.error")


def get_user_storage_path(user_id: uuid.UUID | str) -> str:
    """Returns the absolute path to the user's storage directory."""
    return os.path.join(USER_FILES_BASE_DIR, str(user_id))


async def create_user_root_folder(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID | None
) -> Optional[Files]:
    """
    Creates the physical root folder for a user and the corresponding DB record.
    This function is idempotent.
    """
    if not user_id:
        return None

    sentry_sdk.add_breadcrumb(
        category="file.system",
        message=f"Ensuring user root folder exists for user {user_id}",
        level="info",
    )

    user_dir = get_user_storage_path(user_id)
    if not await aiofiles.os.path.exists(user_dir):
        try:
            with sentry_sdk.start_span(op="file.mkdir", description="create_user_root_folder"):
                await aiofiles.os.makedirs(user_dir)
        except OSError as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to create directory {user_dir}: {e}")
            raise

    root_folder = await get_root_folder_for_user(pg_engine, user_id)
    if not root_folder:
        root_folder = await create_db_folder(
            pg_engine=pg_engine,
            user_id=user_id,
            name="/",
            parent_id=None,
        )

    return root_folder


async def save_file_to_disk(
    user_id: uuid.UUID,
    file_contents: bytes,
    original_filename: str,
    subdirectory: Optional[str] = None,
) -> str:
    """
    Save a file to the user's directory and return the unique filename.
    This unique filename should be stored in the database's `file_path` column.
    """
    with sentry_sdk.start_span(op="file.write", description="save_file_to_disk") as span:
        user_dir = get_user_storage_path(user_id)
        if subdirectory:
            user_dir = os.path.join(user_dir, subdirectory)
        if not await aiofiles.os.path.exists(user_dir):
            await aiofiles.os.makedirs(user_dir, exist_ok=True)

        _, ext = os.path.splitext(original_filename)
        if not ext:
            guessed_type = mimetypes.guess_type(original_filename)[0]
            ext = mimetypes.guess_extension(guessed_type or "") or ""
            span.set_data("extension_guessed", True)
            span.set_data("guessed_mime_type", guessed_type)

        unique_filename = str(uuid.uuid4()) + (ext or "")
        full_path = os.path.join(user_dir, unique_filename)

        file_size = len(file_contents)
        span.set_tag("file.ext", ext)
        span.set_data("file_size_bytes", file_size)

        try:
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(file_contents)
        except (IOError, OSError) as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to write file to {full_path}: {e}")
            raise

        return unique_filename


async def delete_file_from_disk(
    user_id: uuid.UUID, unique_filename: str, subdirectory: Optional[str] = None
) -> bool:
    """
    Deletes a specific file from a user's storage directory.
    Returns True if successful, False otherwise.
    """
    with sentry_sdk.start_span(op="file.delete", description="delete_file_from_disk") as span:
        user_dir = get_user_storage_path(user_id)
        if subdirectory:
            user_dir = os.path.join(user_dir, subdirectory)
        file_path = os.path.join(user_dir, unique_filename)
        span.set_data("file_path", file_path)

        if await aiofiles.os.path.exists(file_path) and await aiofiles.os.path.isfile(file_path):
            try:
                await aiofiles.os.remove(file_path)
                return True
            except OSError as e:
                logger.error(f"Error deleting file {file_path}: {e}")
                sentry_sdk.capture_exception(e)
                return False

        sentry_sdk.add_breadcrumb(
            category="file.system",
            message=f"Attempted to delete a non-existent file: {file_path}",
            level="info",
        )
        return True


async def calculate_file_hash(file_path: str) -> str:
    """
    Calculates the SHA-256 hash of a file located at file_path.
    """
    sha256_hash = hashlib.sha256()
    try:
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(128 * 1024):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        logger.error(f"File not found for hashing: {file_path}")
        return ""
    except Exception as e:
        logger.error(f"Error hashing file {file_path}: {e}")
        sentry_sdk.capture_exception(e)
        return ""


async def get_or_calculate_file_hash(
    pg_engine: SQLAlchemyAsyncEngine,
    file_id: uuid.UUID,
    user_id: str,
    file_path: str,
) -> str:
    """
    Retrieves a file's hash from the DB. If not present, calculates it,
    stores it in the DB, and then returns it.
    """
    # 1. First, try to get the file record to check for a stored hash
    file_record = await get_file_by_id(pg_engine=pg_engine, file_id=file_id, user_id=str(user_id))
    if file_record and file_record.content_hash:
        return file_record.content_hash

    # 2. If not found, calculate it
    calculated_hash = await calculate_file_hash(str(file_path))

    # 3. Store the new hash in the database for future requests
    await update_file_hash(pg_engine, file_id, calculated_hash)

    return calculated_hash


def _resize_image_sync(source_path: str, target_path: str, width: int, height: int):
    """Synchronously resize image using Pillow (Center Crop)."""
    temp_path = f"{target_path}.{uuid.uuid4()}.tmp"

    try:
        with Image.open(source_path) as img:
            resized_img = ImageOps.fit(
                img,
                (width, height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

            ext = os.path.splitext(target_path)[1].lower()
            if ext in [".jpg", ".jpeg"] and resized_img.mode in ("RGBA", "P"):
                resized_img = resized_img.convert("RGB")

            resized_img.save(temp_path, optimize=True)

        os.replace(temp_path, target_path)
    except Exception as e:
        logger.error(f"Error resizing image {source_path}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


async def ensure_resized_image(
    user_id: uuid.UUID,
    unique_filename: str,
    size_str: str,
) -> Optional[str]:
    """
    Ensures a resized version of the image exists in the cache.
    Returns the path to the resized image or None if it fails.
    """
    if size_str not in ALLOWED_RESIZES:
        return None

    try:
        width, height = map(int, size_str.lower().split("x"))
    except ValueError:
        return None

    user_base = get_user_storage_path(user_id)
    cache_base = os.path.join(user_base, ".cache", "resized")

    # Original full path
    source_path = os.path.join(user_base, unique_filename)

    # Construct target path preserving structure to avoid collisions
    relative_dir = os.path.dirname(unique_filename)
    filename = os.path.basename(unique_filename)
    name, ext = os.path.splitext(filename)

    resized_filename = f"{name}_{width}x{height}{ext}"

    # Target directory inside cache
    target_dir = os.path.join(cache_base, relative_dir)
    target_path = os.path.join(target_dir, resized_filename)

    # Check existence
    if not await aiofiles.os.path.exists(source_path):
        return None

    # Cache Invalidation Check
    if await aiofiles.os.path.exists(target_path):
        source_stat = await aiofiles.os.stat(source_path)
        target_stat = await aiofiles.os.stat(target_path)

        # If cache is newer than source, return cache
        if target_stat.st_mtime > source_stat.st_mtime:
            return target_path

    if not await aiofiles.os.path.exists(target_dir):
        await aiofiles.os.makedirs(target_dir, exist_ok=True)

    # Resize (CPU bound, run in executor)
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None, _resize_image_sync, source_path, target_path, width, height
        )
        return target_path
    except Exception:
        return None
