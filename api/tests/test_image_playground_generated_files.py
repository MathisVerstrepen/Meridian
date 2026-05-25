import asyncio
import hashlib
import sys
import uuid
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image


sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.image_playground import generated_files
from services.image_playground.generated_files import (
    create_generated_image_file,
    measure_image_dimensions,
)


def _png_bytes(size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "green").save(buffer, format="PNG")
    return buffer.getvalue()


def test_measure_image_dimensions_reduces_aspect_ratio():
    assert measure_image_dimensions(_png_bytes((896, 1200))) == (896, 1200, "56:75")
    assert measure_image_dimensions(_png_bytes((1024, 768))) == (1024, 768, "4:3")


def test_create_generated_image_file_saves_under_generated_images(monkeypatch):
    calls: dict[str, object] = {}
    user_id = uuid.uuid4()
    root_id = uuid.uuid4()
    file_id = uuid.uuid4()
    image_bytes = b"image-bytes"

    async def fake_check_and_reserve_storage(pg_engine, checked_user_id, file_size):
        calls["reserved"] = (pg_engine, checked_user_id, file_size)

    async def fake_save_file_to_disk(user_id, file_contents, original_filename, subdirectory):
        calls["saved"] = (user_id, file_contents, original_filename, subdirectory)
        return "saved-image.png"

    async def fake_get_root_folder_for_user(pg_engine, root_user_id):
        calls["root"] = (pg_engine, root_user_id)
        return SimpleNamespace(id=root_id)

    async def fake_create_db_file(**kwargs):
        calls["created"] = kwargs
        return SimpleNamespace(id=file_id, **kwargs)

    monkeypatch.setattr(
        generated_files, "check_and_reserve_storage", fake_check_and_reserve_storage
    )
    monkeypatch.setattr(generated_files, "save_file_to_disk", fake_save_file_to_disk)
    monkeypatch.setattr(generated_files, "get_root_folder_for_user", fake_get_root_folder_for_user)
    monkeypatch.setattr(generated_files, "create_db_file", fake_create_db_file)

    created_file = asyncio.run(
        create_generated_image_file(
            pg_engine="engine",
            user_id=user_id,
            prompt="A generated subject",
            source_image_ids=[],
            image_bytes=image_bytes,
            extension="png",
        )
    )

    assert created_file.id == file_id
    assert calls["reserved"] == ("engine", user_id, len(image_bytes))
    assert calls["saved"][3] == "generated_images"
    created_kwargs = calls["created"]
    assert created_kwargs["parent_id"] == root_id
    assert created_kwargs["name"].startswith("Gen: A generated subject")
    assert created_kwargs["file_path"] == "generated_images/saved-image.png"
    assert created_kwargs["content_type"] == "image/png"
    assert created_kwargs["hash"] == hashlib.sha256(image_bytes).hexdigest()


def test_create_generated_image_file_rolls_back_storage_and_disk_on_failure(monkeypatch):
    calls: dict[str, object] = {}
    user_id = uuid.uuid4()
    image_bytes = b"image-bytes"

    async def fake_check_and_reserve_storage(pg_engine, checked_user_id, file_size):
        calls["reserved"] = True

    async def fake_save_file_to_disk(user_id, file_contents, original_filename, subdirectory):
        return "saved-image.png"

    async def fake_get_root_folder_for_user(pg_engine, root_user_id):
        return None

    async def fake_delete_file_from_disk(user_id, unique_filename, subdirectory):
        calls["deleted"] = (user_id, unique_filename, subdirectory)

    async def fake_release_storage(pg_engine, released_user_id, file_size):
        calls["released"] = (pg_engine, released_user_id, file_size)

    monkeypatch.setattr(
        generated_files, "check_and_reserve_storage", fake_check_and_reserve_storage
    )
    monkeypatch.setattr(generated_files, "save_file_to_disk", fake_save_file_to_disk)
    monkeypatch.setattr(generated_files, "get_root_folder_for_user", fake_get_root_folder_for_user)
    monkeypatch.setattr(generated_files, "delete_file_from_disk", fake_delete_file_from_disk)
    monkeypatch.setattr(generated_files, "release_storage", fake_release_storage)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            create_generated_image_file(
                pg_engine="engine",
                user_id=user_id,
                prompt="A generated subject",
                source_image_ids=[str(uuid.uuid4())],
                image_bytes=image_bytes,
                extension="png",
            )
        )

    assert exc_info.value.status_code == 404
    assert calls["reserved"] is True
    assert calls["deleted"] == (user_id, "saved-image.png", "generated_images")
    assert calls["released"] == ("engine", user_id, len(image_bytes))
