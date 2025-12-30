import logging
import uuid
from typing import Optional, Tuple

from database.pg.models import Files
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_, col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def get_item_path(session: AsyncSession, item_id: uuid.UUID) -> str:
    """
    Calculates the full logical path for a given item using a Recursive CTE.
    """
    stmt = text(
        """
        WITH RECURSIVE path_tree AS (
            SELECT id, name, parent_id, 1 as level
            FROM files
            WHERE id = :item_id
            UNION ALL
            SELECT f.id, f.name, f.parent_id, pt.level + 1
            FROM files f
            JOIN path_tree pt ON f.id = pt.parent_id
        )
        SELECT name FROM path_tree ORDER BY level DESC;
    """
    )
    result = await session.execute(stmt, {"item_id": item_id})
    names = [r[0] for r in result.fetchall()]

    if not names:
        return ""

    if names[0] == "/":
        return "/" + "/".join(names[1:])

    return "/" + "/".join(names)


async def create_db_file(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    parent_id: uuid.UUID,
    name: str,
    file_path: str,
    size: int,
    content_type: str,
    hash: Optional[str] = None,
) -> Files:
    """
    Creates a file record in the database.
    Verifies that the parent folder exists and belongs to the user.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(Files).where(
            Files.id == parent_id, Files.user_id == user_id, Files.type == "folder"
        )
        parent_check = await session.exec(stmt)
        if not parent_check.one_or_none():
            raise HTTPException(status_code=404, detail="Parent folder not found or access denied")

        file_record = Files(
            user_id=user_id,
            parent_id=parent_id,
            name=name,
            type="file",
            file_path=file_path,
            size=size,
            content_type=content_type,
            content_hash=hash,
        )
        session.add(file_record)
        await session.commit()
        await session.refresh(file_record)
        return file_record


async def create_db_folder(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: uuid.UUID,
    name: str,
    parent_id: Optional[uuid.UUID],
) -> Files:
    """
    Creates a folder record in the database.
    If parent_id is provided, verifies it exists and belongs to the user.
    """
    async with AsyncSession(pg_engine) as session:
        if parent_id:
            parent_check = await session.exec(
                select(Files).where(
                    Files.id == parent_id, Files.user_id == user_id, Files.type == "folder"
                )
            )
            if not parent_check.one_or_none():
                raise HTTPException(
                    status_code=404, detail="Parent folder not found or access denied"
                )

        folder_record = Files(
            user_id=user_id,
            parent_id=parent_id,
            name=name,
            type="folder",
        )
        session.add(folder_record)
        await session.commit()
        await session.refresh(folder_record)
        return folder_record


async def get_root_folder_for_user(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> Optional[Files]:
    """Retrieves the root folder for a given user."""
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(Files).where(
                and_(Files.user_id == user_id, Files.parent_id == None)  # noqa: E711
            )
        )
        return result.one_or_none()  # type: ignore


async def get_file_by_id(
    pg_engine: SQLAlchemyAsyncEngine, file_id: uuid.UUID, user_id: uuid.UUID | str
) -> Optional[Files]:
    """
    Retrieve a file or folder by its ID, ensuring it belongs to the specified user.
    """
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(Files).where(and_(Files.id == file_id, Files.user_id == user_id))
        )
        return result.one_or_none()  # type: ignore


async def get_folder_contents(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, parent_id: uuid.UUID
) -> list[Tuple[Files, str]]:
    """
    Retrieves the contents (files and subfolders) of a given folder for a specific user.
    Returns a list of tuples containing (FileObject, logical_path).
    """
    async with AsyncSession(pg_engine) as session:
        # Verify the user has access to the parent folder.
        parent_check = await session.exec(
            select(Files).where(
                and_(Files.id == parent_id, Files.user_id == user_id, Files.type == "folder")
            )
        )
        parent_folder = parent_check.one_or_none()
        if not parent_folder:
            raise HTTPException(status_code=404, detail="Folder not found or access denied")

        # Calculate parent path once
        parent_path = await get_item_path(session, parent_id)
        # Normalize parent path for appending
        base_path = parent_path if parent_path != "/" else ""

        # If access is verified, fetch the contents, excluding generated_images paths.
        result = await session.exec(
            select(Files).where(
                and_(
                    Files.user_id == user_id,
                    Files.parent_id == parent_id,
                    or_(
                        (Files.file_path == None),  # noqa: E711
                        ~col(Files.file_path).contains("generated_images/"),
                    ),
                )
            )
        )

        items = list(result.all())

        # Return items with their constructed paths
        return [(item, f"{base_path}/{item.name}") for item in items]


async def get_generated_images_files(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> list[Tuple[Files, str]]:
    """
    Retrieves all files that are classified as generated images (path contains 'generated_images/').
    Returns a flat list of tuples containing (FileObject, logical_path).
    """
    async with AsyncSession(pg_engine) as session:
        result = await session.exec(
            select(Files).where(
                and_(
                    Files.user_id == user_id,
                    Files.type == "file",
                    col(Files.file_path).contains("generated_images/"),
                )
            )
        )
        items = list(result.all())
        # For generated images, we return a virtual path
        return [(item, f"/Generated Images/{item.name}") for item in items]


async def delete_db_item_recursively(
    pg_engine: SQLAlchemyAsyncEngine, item_id: uuid.UUID, user_id: uuid.UUID
) -> list[str]:
    """
    Deletes a file or folder (and its contents recursively) from the database
    and the physical storage.
    """
    async with AsyncSession(pg_engine) as session:
        recursive_query = text(
            """
            WITH RECURSIVE file_tree AS (
                SELECT id, file_path, type, user_id
                FROM files
                WHERE id = :item_id
                UNION ALL
                SELECT f.id, f.file_path, f.type, f.user_id
                FROM files f
                JOIN file_tree ft ON f.parent_id = ft.id
            )
            SELECT id, file_path, type, user_id FROM file_tree
            """
        )
        result = await session.execute(recursive_query, {"item_id": item_id})
        all_items = result.fetchall()

        if not all_items:
            raise HTTPException(status_code=404, detail="Item not found")

        # Check ownership on the top-level item
        if all_items[0].user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Physical files to delete
        files_to_delete_on_disk = [
            item.file_path for item in all_items if item.type == "file" and item.file_path
        ]

        # Delete all database records
        item_ids_to_delete = [item.id for item in all_items]
        if item_ids_to_delete:
            delete_stmt = text("DELETE FROM files WHERE id = ANY(:item_ids)")
            await session.execute(delete_stmt, {"item_ids": item_ids_to_delete})

        await session.commit()
        return files_to_delete_on_disk


async def update_file_hash(pg_engine: SQLAlchemyAsyncEngine, file_id: uuid.UUID, file_hash: str):
    """Updates the content_hash for a given file."""
    async with AsyncSession(pg_engine) as session:
        stmt = select(Files).where(Files.id == file_id)
        result = await session.exec(stmt)
        file_record = result.one_or_none()
        if file_record:
            file_record.content_hash = file_hash
            session.add(file_record)
            await session.commit()


async def rename_item(
    pg_engine: SQLAlchemyAsyncEngine, item_id: uuid.UUID, user_id: uuid.UUID, new_name: str
) -> Files:
    """
    Renames a file or folder.
    """
    async with AsyncSession(pg_engine) as session:
        # Check existence and ownership
        stmt = select(Files).where(and_(Files.id == item_id, Files.user_id == user_id))
        result = await session.exec(stmt)
        item = result.one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Check for name collision in the same parent folder
        stmt_check = select(Files).where(
            and_(
                Files.user_id == user_id,
                Files.parent_id == item.parent_id,
                Files.name == new_name,
                Files.id != item_id,
            )
        )
        collision = await session.exec(stmt_check)
        if collision.first():
            raise HTTPException(
                status_code=409,
                detail="An item with this name already exists in the destination folder.",
            )

        item.name = new_name
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item
