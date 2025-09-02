import mimetypes
import os
import uuid
import logging


from database.pg.file_ops.file_crud import create_db_folder, get_root_folder_for_user
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

USER_FILES_BASE_DIR = "data/user_files"

logger = logging.getLogger("uvicorn.error")


def get_user_storage_path(user_id: uuid.UUID | str) -> str:
    """Returns the absolute path to the user's storage directory."""
    return os.path.join(USER_FILES_BASE_DIR, str(user_id))


async def create_user_root_folder(pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID | None):
    """
    Creates the physical root folder for a user and the corresponding DB record.
    This function is idempotent.
    """
    if not user_id:
        return

    user_dir = get_user_storage_path(user_id)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    root_folder = await get_root_folder_for_user(pg_engine, user_id)
    if not root_folder:
        await create_db_folder(
            pg_engine=pg_engine,
            user_id=user_id,
            name="/",
            parent_id=None,
        )


async def save_file_to_disk(
    user_id: uuid.UUID, file_contents: bytes, original_filename: str
) -> str:
    """
    Save a file to the user's directory and return the unique filename.
    This unique filename should be stored in the database's `file_path` column.
    """
    user_dir = get_user_storage_path(user_id)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    _, ext = os.path.splitext(original_filename)
    if not ext:
        ext = mimetypes.guess_extension(mimetypes.guess_type(original_filename)[0] or "") or ""

    unique_filename = str(uuid.uuid4()) + (ext or "")
    full_path = os.path.join(user_dir, unique_filename)

    with open(full_path, "wb") as f:
        f.write(file_contents)

    return unique_filename


def delete_file_from_disk(user_id: uuid.UUID, unique_filename: str) -> bool:
    """
    Deletes a specific file from a user's storage directory.
    Returns True if successful, False otherwise.
    """
    user_dir = get_user_storage_path(user_id)
    file_path = os.path.join(user_dir, unique_filename)

    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            os.remove(file_path)
            return True
        except OSError as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    return True
