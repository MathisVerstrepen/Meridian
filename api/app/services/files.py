import logging
import mimetypes
import os
import uuid
from typing import Optional

import sentry_sdk
from database.pg.file_ops.file_crud import create_db_folder, get_root_folder_for_user
from database.pg.models import Files
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

USER_FILES_BASE_DIR = "data/user_files"

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
    if not os.path.exists(user_dir):
        try:
            with sentry_sdk.start_span(op="file.mkdir", description="create_user_root_folder"):
                os.makedirs(user_dir)
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
    user_id: uuid.UUID, file_contents: bytes, original_filename: str
) -> str:
    """
    Save a file to the user's directory and return the unique filename.
    This unique filename should be stored in the database's `file_path` column.
    """
    with sentry_sdk.start_span(op="file.write", description="save_file_to_disk") as span:
        user_dir = get_user_storage_path(user_id)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

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
        sentry_sdk.metrics.distribution("files.upload.size.bytes", file_size, unit="byte")

        try:
            with open(full_path, "wb") as f:
                f.write(file_contents)
        except (IOError, OSError) as e:
            sentry_sdk.capture_exception(e)
            logger.error(f"Failed to write file to {full_path}: {e}")
            raise

        return unique_filename


def delete_file_from_disk(user_id: uuid.UUID, unique_filename: str) -> bool:
    """
    Deletes a specific file from a user's storage directory.
    Returns True if successful, False otherwise.
    """
    with sentry_sdk.start_span(op="file.delete", description="delete_file_from_disk") as span:
        user_dir = get_user_storage_path(user_id)
        file_path = os.path.join(user_dir, unique_filename)
        span.set_data("file_path", file_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                os.remove(file_path)
                sentry_sdk.metrics.incr("files.delete.count", 1, tags={"success": "true"})
                return True
            except OSError as e:
                logger.error(f"Error deleting file {file_path}: {e}")
                sentry_sdk.capture_exception(e)
                sentry_sdk.metrics.incr("files.delete.count", 1, tags={"success": "false"})
                return False

        sentry_sdk.add_breadcrumb(
            category="file.system",
            message=f"Attempted to delete a non-existent file: {file_path}",
            level="info",
        )
        return True
