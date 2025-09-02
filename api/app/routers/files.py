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
    get_root_folder_for_user,
)
from database.pg.models import Files as FilesModel
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.files import (
    create_user_root_folder,
    delete_file_from_disk,
    get_user_storage_path,
    save_file_to_disk,
)

router = APIRouter(prefix="/files", tags=["files"])


class FileSystemObject(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateFolderPayload(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None


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
    return new_folder


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

    contents = await file.read()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    unique_filename = await save_file_to_disk(
        user_id=user_id,
        file_contents=contents,
        original_filename=file.filename,
    )

    new_file: FilesModel = await create_db_file(
        pg_engine=pg_engine,
        user_id=user_id,
        parent_id=parent_id,
        name=file.filename,
        file_path=unique_filename,
        size=len(contents),
        content_type=file.content_type or "application/octet-stream",
    )

    return FileSystemObject(
        id=new_file.id,
        name=new_file.name,
        type=new_file.type,
        size=new_file.size,
        content_type=new_file.content_type,
        created_at=new_file.created_at,
        updated_at=new_file.updated_at,
    )


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

    return root_folder


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

    contents = await get_folder_contents(pg_engine, user_id, folder_id)
    return contents


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

    files_to_delete_on_disk = await delete_db_item_recursively(
        pg_engine=pg_engine, item_id=item_id, user_id=user_id
    )
    for file_path in files_to_delete_on_disk:
        delete_file_from_disk(user_id, file_path)

    return


@router.get("/view/{file_id}")
async def view_file(
    request: Request,
    file_id: uuid.UUID,
    user_id_str: str = Depends(get_current_user_id),
):
    """
    Serves a file to the user after checking for ownership.
    """
    user_id = uuid.UUID(user_id_str)
    pg_engine = request.app.state.pg_engine

    file_record = await get_file_by_id(pg_engine=pg_engine, file_id=file_id, user_id=user_id)

    if not file_record or file_record.type != "file" or not file_record.file_path:
        raise HTTPException(status_code=404, detail="File not found or is not a file.")

    user_storage_path = get_user_storage_path(user_id)
    full_path = os.path.join(user_storage_path, file_record.file_path)

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileResponse(
        path=full_path, media_type=file_record.content_type, filename=file_record.name
    )
