import os
import uuid
from datetime import datetime
from typing import Optional

from database.pg.file_ops.file_crud import (
    create_db_file,
    create_db_folder,
    delete_db_item_recursively,
    get_file_by_id,
    get_folder_contents,
    get_generated_images_files,
    get_item_path,
    get_root_folder_for_user,
    rename_item,
)
from database.pg.models import Files as FilesModel
from database.pg.user_ops.storage_crud import (
    check_and_reserve_storage,
    get_recursive_item_size,
    release_storage,
)
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.files import (
    create_user_root_folder,
    delete_file_from_disk,
    ensure_resized_image,
    get_user_storage_path,
    save_upload_file_to_disk,
)
from services.settings import get_user_settings
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/files", tags=["files"])

EMBEDDABLE_HTML_CONTENT_TYPE = "text/html"
FILE_CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000"}
HTML_EMBED_CSP = "; ".join(
    [
        "sandbox allow-scripts allow-downloads",
        "default-src 'none'",
        "script-src 'unsafe-inline' 'unsafe-eval' https:",
        "style-src 'unsafe-inline' https:",
        "img-src data: blob: https:",
        "font-src data: https:",
        "connect-src https:",
        "media-src data: blob: https:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'self'",
    ]
)


class FileSystemObject(BaseModel):
    id: uuid.UUID
    name: str
    path: str
    type: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    cached: bool = False

    class Config:
        from_attributes = True


class CreateFolderPayload(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None


async def _get_owned_file_or_404(
    request: Request,
    file_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FilesModel:
    file_record = await get_file_by_id(
        pg_engine=request.app.state.pg_engine,
        file_id=file_id,
        user_id=user_id,
    )

    if not file_record or file_record.type != "file" or not file_record.file_path:
        raise HTTPException(status_code=404, detail="File not found or is not a file.")

    return file_record


def _get_full_file_path(user_id: uuid.UUID, file_path: str) -> str:
    full_path = os.path.join(get_user_storage_path(user_id), file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")
    return full_path


def _build_file_response(
    *,
    path: str,
    media_type: Optional[str],
    filename: str,
    headers: Optional[dict[str, str]] = None,
    content_disposition_type: str = "attachment",
) -> FileResponse:
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        headers=headers,
        content_disposition_type=content_disposition_type,
    )


@router.post("/folder", response_model=FileSystemObject, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: Request,
    payload: CreateFolderPayload,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Create a new folder for the user.
    If parent_id is not provided, it creates the folder in the user's root directory.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    if not payload.parent_id:
        root_folder = await get_root_folder_for_user(pg_engine, user_id)
        if not root_folder:
            raise HTTPException(status_code=404, detail="Root folder not found for user.")
        payload.parent_id = root_folder.id

    new_folder = await create_db_folder(
        pg_engine,
        user_id=user_id,
        name=payload.name,
        parent_id=payload.parent_id,
    )

    # Calculate path for response
    async with AsyncSession(pg_engine) as session:
        parent_path = await get_item_path(session, payload.parent_id)
        base_path = parent_path if parent_path != "/" else ""
        full_path = f"{base_path}/{new_folder.name}"

    return FileSystemObject(
        id=new_folder.id,
        name=new_folder.name,
        path=full_path,
        type=new_folder.type,
        created_at=new_folder.created_at,
        updated_at=new_folder.updated_at,
    )


@router.post("/upload", response_model=FileSystemObject, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    parent_id: uuid.UUID,
    file: UploadFile = File(...),
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Upload a file to a specific folder for the user.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    if file.size is None:
        raise HTTPException(status_code=400, detail="Unable to determine upload size.")

    file_size = file.size

    await check_and_reserve_storage(pg_engine, user_id, file_size)

    filename = os.path.basename(file.filename)
    unique_filename = None

    try:
        unique_filename, file_hash = await save_upload_file_to_disk(
            user_id=user_id,
            upload_file=file,
            original_filename=filename,
        )

        new_file: FilesModel = await create_db_file(
            pg_engine=pg_engine,
            user_id=user_id,
            parent_id=parent_id,
            name=filename,
            file_path=unique_filename,
            size=file_size,
            content_type=file.content_type or "application/octet-stream",
            hash=file_hash,
        )

        # Calculate logical path for response
        async with AsyncSession(pg_engine) as session:
            parent_path = await get_item_path(session, parent_id)
            base_path = parent_path if parent_path != "/" else ""
            logical_path = f"{base_path}/{new_file.name}"

        return FileSystemObject(
            id=new_file.id,
            name=new_file.name,
            path=logical_path,
            type=new_file.type,
            size=new_file.size,
            content_type=new_file.content_type,
            created_at=new_file.created_at,
            updated_at=new_file.updated_at,
        )
    except Exception as e:
        if unique_filename:
            await delete_file_from_disk(user_id, unique_filename)
        await release_storage(pg_engine, user_id, file_size)
        raise e


@router.get("/root", response_model=FileSystemObject)
async def get_root_folder(
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Get the user's root folder.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    root_folder = await get_root_folder_for_user(pg_engine, user_id)
    if not root_folder:
        root_folder = await create_user_root_folder(pg_engine, user_id)
    if not root_folder:
        raise HTTPException(status_code=404, detail="Root folder not found for user.")

    return FileSystemObject(
        id=root_folder.id,
        name=root_folder.name,
        path="/",
        type=root_folder.type,
        created_at=root_folder.created_at,
        updated_at=root_folder.updated_at,
    )


@router.get("/list/{folder_id}", response_model=list[FileSystemObject])
async def list_folder_contents(
    request: Request,
    folder_id: uuid.UUID,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    List the contents of a specific folder for the user.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine
    redis_manager = request.app.state.redis_manager

    user_settings = await get_user_settings(pg_engine, user_id_str)

    contents_with_paths = await get_folder_contents(pg_engine, user_id, folder_id)
    mapped_contents = []

    for content, path in contents_with_paths:
        cached = False
        if content.type == "file" and content.file_path and content.content_hash:
            hash_key = f"{user_settings.blockAttachment.pdf_engine}:{content.content_hash}"
            remote_hash = await redis_manager.get_remote_hash(hash_key)
            if remote_hash:
                cached = await redis_manager.annotation_exists(remote_hash)

        mapped_content = FileSystemObject.model_validate(
            {
                **content.__dict__,
                "path": path,
                "cached": cached,
            }
        )
        mapped_contents.append(mapped_content)

    return mapped_contents


@router.get("/generated_images", response_model=list[FileSystemObject])
async def list_generated_images(
    request: Request,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    List all generated images for the user.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    contents_with_paths = await get_generated_images_files(pg_engine, user_id)
    mapped_contents = []

    for content, path in contents_with_paths:
        mapped_content = FileSystemObject.model_validate(
            {
                **content.__dict__,
                "path": path,
                "cached": False,
            }
        )
        mapped_contents.append(mapped_content)

    return mapped_contents


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    request: Request,
    item_id: uuid.UUID,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Deletes a file or a folder (and all its contents).
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    size_to_free = await get_recursive_item_size(pg_engine, item_id, user_id)

    files_to_delete_on_disk = await delete_db_item_recursively(
        pg_engine=pg_engine, item_id=item_id, user_id=user_id
    )
    for file_path in files_to_delete_on_disk:
        await delete_file_from_disk(user_id, file_path)

    if size_to_free > 0:
        await release_storage(pg_engine, user_id, size_to_free)

    return


@router.get("/view/{file_id}")
async def view_file(
    request: Request,
    file_id: uuid.UUID,
    size: Optional[str] = Query(None, pattern=r"^\d+x\d+$"),
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Serves a file to the user after checking for ownership.
    If 'size' is provided (e.g., '160x160') and the file is an image,
    it returns a resized version, caching it if necessary.
    """
    user_id = uuid.UUID(user_id_str)
    file_record = await _get_owned_file_or_404(request, file_id, user_id)
    file_path = file_record.file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found on disk.")

    # Check if resize is requested for an image
    if size and file_record.content_type and file_record.content_type.startswith("image/"):
        resized_path = await ensure_resized_image(user_id, file_path, size)
        if resized_path:
            return _build_file_response(
                path=resized_path,
                media_type=file_record.content_type,
                filename=file_record.name,
            )

    full_path = _get_full_file_path(user_id, file_path)
    return _build_file_response(
        path=full_path,
        media_type=file_record.content_type,
        filename=file_record.name,
        headers=FILE_CACHE_HEADERS,
    )


@router.get("/embed/{file_id}")
async def embed_file(
    request: Request,
    file_id: uuid.UUID,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Serves an embeddable HTML file for sandbox-generated interactive artifacts.
    The response is sandboxed via CSP and can only be used for persisted HTML files
    owned by the current user.
    """
    user_id = uuid.UUID(user_id_str)
    file_record = await _get_owned_file_or_404(request, file_id, user_id)
    file_path = file_record.file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found on disk.")

    if file_record.content_type != EMBEDDABLE_HTML_CONTENT_TYPE:
        raise HTTPException(status_code=415, detail="Only HTML artifacts can be embedded.")

    full_path = _get_full_file_path(user_id, file_path)
    headers = {
        **FILE_CACHE_HEADERS,
        "Content-Security-Policy": HTML_EMBED_CSP,
        "X-Content-Type-Options": "nosniff",
    }
    return _build_file_response(
        path=full_path,
        media_type=file_record.content_type,
        filename=file_record.name,
        headers=headers,
        content_disposition_type="inline",
    )


class RenamePayload(BaseModel):
    name: str


@router.patch("/{item_id}/rename", response_model=FileSystemObject)
async def rename_file_or_folder(
    request: Request,
    item_id: uuid.UUID,
    payload: RenamePayload,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Renames a file or folder.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    # Call CRUD
    updated_item = await rename_item(pg_engine, item_id, user_id, payload.name)

    # Get path
    async with AsyncSession(pg_engine) as session:
        path = await get_item_path(session, item_id)

    return FileSystemObject(
        id=updated_item.id,
        name=updated_item.name,
        path=path,
        type=updated_item.type,
        size=updated_item.size,
        content_type=updated_item.content_type,
        created_at=updated_item.created_at,
        updated_at=updated_item.updated_at,
    )
