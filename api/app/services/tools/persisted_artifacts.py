import hashlib
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from database.pg.file_ops.file_crud import (
    create_db_file,
    create_db_folder,
    delete_db_item_recursively,
    get_folder_contents,
    get_root_folder_for_user,
)
from database.pg.user_ops.storage_crud import check_and_reserve_storage, release_storage
from services.files import create_user_root_folder, delete_file_from_disk, save_file_to_disk

INLINE_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
GENERATED_FILES_FOLDER_NAME = "Generated Files"


def is_inline_image_content_type(content_type: str) -> bool:
    return content_type.lower() in INLINE_IMAGE_CONTENT_TYPES


async def _get_or_create_child_folder(
    pg_engine,
    user_id: uuid.UUID,
    parent_id: uuid.UUID,
    name: str,
):
    contents = await get_folder_contents(pg_engine, user_id, parent_id)
    for item, _ in contents:
        if item.type == "folder" and item.name == name:
            return item

    return await create_db_folder(
        pg_engine=pg_engine,
        user_id=user_id,
        name=name,
        parent_id=parent_id,
    )


async def _cleanup_persisted_run(
    pg_engine,
    user_id: uuid.UUID,
    run_folder_id: uuid.UUID | None,
    reserved_bytes: int,
    extra_file_paths: list[str],
    storage_reserved: bool,
) -> None:
    disk_paths_to_delete = set(extra_file_paths)

    if run_folder_id is not None:
        file_paths = await delete_db_item_recursively(
            pg_engine=pg_engine,
            item_id=run_folder_id,
            user_id=user_id,
        )
        disk_paths_to_delete.update(file_paths)

    for file_path in disk_paths_to_delete:
        await delete_file_from_disk(user_id, file_path)

    if storage_reserved and reserved_bytes > 0:
        await release_storage(pg_engine, user_id, reserved_bytes)


async def persist_generated_artifacts(
    *,
    req,
    user_id: uuid.UUID,
    artifacts: list[dict[str, Any]],
    category_folder_name: str,
    run_folder_name: str,
    disk_base_subdirectory: PurePosixPath,
) -> list[dict[str, Any]]:
    if not artifacts:
        return []

    reserved_bytes = sum(int(artifact["size"]) for artifact in artifacts)
    run_folder_id: uuid.UUID | None = None
    persisted_disk_paths: list[str] = []
    storage_reserved = False

    try:
        await check_and_reserve_storage(req.pg_engine, user_id, reserved_bytes)
        storage_reserved = True

        root_folder = await get_root_folder_for_user(req.pg_engine, user_id)
        if root_folder is None:
            root_folder = await create_user_root_folder(req.pg_engine, user_id)
        if root_folder is None or root_folder.id is None:
            raise RuntimeError("Root folder not found for user.")

        generated_folder = await _get_or_create_child_folder(
            req.pg_engine,
            user_id,
            root_folder.id,
            GENERATED_FILES_FOLDER_NAME,
        )
        category_folder = await _get_or_create_child_folder(
            req.pg_engine,
            user_id,
            generated_folder.id,
            category_folder_name,
        )
        run_folder = await create_db_folder(
            pg_engine=req.pg_engine,
            user_id=user_id,
            name=run_folder_name,
            parent_id=category_folder.id,
        )
        run_folder_id = run_folder.id
        if run_folder_id is None:
            raise RuntimeError("Failed to create generated artifact folder.")

        folder_cache: dict[PurePosixPath, uuid.UUID] = {PurePosixPath("."): run_folder_id}
        persisted_artifacts: list[dict[str, Any]] = []

        for artifact in artifacts:
            relative_path = PurePosixPath(str(artifact["relative_path"]))
            parent_path = relative_path.parent

            if parent_path not in folder_cache:
                current_parent_id = run_folder_id
                current_path = PurePosixPath(".")
                for segment in parent_path.parts:
                    if segment in {"", "."}:
                        continue

                    current_path = current_path / segment
                    cached_id = folder_cache.get(current_path)
                    if cached_id is None:
                        folder = await create_db_folder(
                            pg_engine=req.pg_engine,
                            user_id=user_id,
                            name=segment,
                            parent_id=current_parent_id,
                        )
                        if folder.id is None:
                            raise RuntimeError(f"Failed to create artifact folder '{segment}'.")
                        cached_id = folder.id
                        folder_cache[current_path] = cached_id

                    current_parent_id = cached_id

            parent_id = folder_cache[parent_path]
            disk_subdirectory = disk_base_subdirectory / parent_path
            file_bytes = bytes(artifact["bytes"])
            unique_filename = await save_file_to_disk(
                user_id=user_id,
                file_contents=file_bytes,
                original_filename=str(artifact["name"]),
                subdirectory=str(disk_subdirectory),
            )
            persisted_disk_path = str(Path(str(disk_subdirectory)) / unique_filename)
            persisted_disk_paths.append(persisted_disk_path)

            file_record = await create_db_file(
                pg_engine=req.pg_engine,
                user_id=user_id,
                parent_id=parent_id,
                name=str(artifact["name"]),
                file_path=persisted_disk_path,
                size=int(artifact["size"]),
                content_type=str(artifact["content_type"]),
                hash=hashlib.sha256(file_bytes).hexdigest(),
            )
            if file_record.id is None:
                raise RuntimeError(f"Failed to persist artifact '{artifact['relative_path']}'.")

            content_type = str(artifact["content_type"])
            persisted_artifacts.append(
                {
                    "id": str(file_record.id),
                    "name": str(artifact["name"]),
                    "relative_path": str(artifact["relative_path"]),
                    "content_type": content_type,
                    "size": int(artifact["size"]),
                    "kind": "image" if is_inline_image_content_type(content_type) else "file",
                }
            )

        return persisted_artifacts
    except Exception:
        await _cleanup_persisted_run(
            req.pg_engine,
            user_id,
            run_folder_id,
            reserved_bytes,
            persisted_disk_paths,
            storage_reserved,
        )
        raise
