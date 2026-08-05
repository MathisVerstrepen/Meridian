import asyncio
import hashlib
import sys
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.image_playground import generated_files
from services.image_playground.generated_files import (
    create_completed_generation_job,
    create_generated_image_file,
    create_generated_video_file,
    generated_video_content_type,
    measure_image_dimensions,
)


def _png_bytes(size: tuple[int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "green").save(buffer, format="PNG")
    return buffer.getvalue()


def test_measure_image_dimensions_reduces_aspect_ratio():
    assert measure_image_dimensions(_png_bytes((896, 1200))) == (896, 1200, "56:75")
    assert measure_image_dimensions(_png_bytes((1024, 768))) == (1024, 768, "4:3")


def test_generated_video_content_type_maps_mov_to_quicktime():
    assert generated_video_content_type("mov") == "video/quicktime"
    assert generated_video_content_type(".MOV") == "video/quicktime"
    assert generated_video_content_type("mp4") == "video/mp4"


def test_create_completed_generation_job_persists_completed_metadata(monkeypatch):
    calls: dict[str, object] = {}
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    generation_started_at = datetime(2020, 8, 5, 10, 30, tzinfo=timezone.utc)
    source_image_ids = [str(uuid.uuid4())]

    class FakeSession:
        def __init__(self, pg_engine):
            calls["engine"] = pg_engine

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        def add(self, job):
            calls["job"] = job

        async def commit(self):
            calls["committed"] = True

        async def refresh(self, job):
            calls["refreshed"] = job

        async def rollback(self):
            calls["rolled_back"] = True

    monkeypatch.setattr(generated_files, "AsyncSession", FakeSession)

    job = asyncio.run(
        create_completed_generation_job(
            pg_engine="engine",
            user_id=user_id,
            file_id=file_id,
            prompt="  Generated prompt  ",
            model="  provider/resolved-model  ",
            media_type="image",
            aspect_ratio="4:3",
            resolution="2K",
            source_image_ids=source_image_ids,
            generation_started_at=generation_started_at,
            actual_width=1200,
            actual_height=900,
            actual_aspect_ratio="4:3",
        )
    )

    assert calls["engine"] == "engine"
    assert calls["job"] is job
    assert calls["committed"] is True
    assert calls["refreshed"] is job
    assert "rolled_back" not in calls
    assert job.user_id == user_id
    assert job.file_id == file_id
    assert job.status == "completed"
    assert job.prompt == "Generated prompt"
    assert job.effective_prompt == "Generated prompt"
    assert job.model == "provider/resolved-model"
    assert job.media_type == "image"
    assert job.aspect_ratio == "4:3"
    assert job.resolution == "2K"
    assert job.duration is None
    assert job.generate_audio is False
    assert job.actual_width == 1200
    assert job.actual_height == 900
    assert job.actual_aspect_ratio == "4:3"
    assert job.style_preset is None
    assert job.source_image_ids == source_image_ids
    assert job.error is None
    assert job.attempts == 1
    assert job.max_attempts == 1
    assert job.is_preview is False
    assert job.created_at == generation_started_at
    assert job.updated_at == job.completed_at
    assert job.completed_at >= generation_started_at


def test_create_completed_generation_job_rolls_back_and_reraises(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSession:
        def __init__(self, pg_engine):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        def add(self, job):
            calls["added"] = job

        async def commit(self):
            raise RuntimeError("database unavailable")

        async def refresh(self, job):
            calls["refreshed"] = True

        async def rollback(self):
            calls["rolled_back"] = True

    monkeypatch.setattr(generated_files, "AsyncSession", FakeSession)

    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(
            create_completed_generation_job(
                pg_engine="engine",
                user_id=uuid.uuid4(),
                file_id=uuid.uuid4(),
                prompt="prompt",
                model="provider/model",
                media_type="video",
                aspect_ratio="16:9",
                resolution="720p",
                source_image_ids=[],
                generation_started_at=datetime.now(timezone.utc),
                duration=6,
                generate_audio=True,
            )
        )

    assert "added" in calls
    assert calls["rolled_back"] is True
    assert "refreshed" not in calls


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


def test_create_generated_video_file_uses_quicktime_content_type_for_mov(monkeypatch):
    calls: dict[str, object] = {}
    user_id = uuid.uuid4()
    root_id = uuid.uuid4()
    video_bytes = b"video-bytes"

    async def fake_check_and_reserve_storage(pg_engine, checked_user_id, file_size):
        calls["reserved"] = (pg_engine, checked_user_id, file_size)

    async def fake_save_file_to_disk(user_id, file_contents, original_filename, subdirectory):
        calls["saved"] = (user_id, file_contents, original_filename, subdirectory)
        return "saved-video.mov"

    async def fake_get_root_folder_for_user(pg_engine, root_user_id):
        return SimpleNamespace(id=root_id)

    async def fake_create_db_file(**kwargs):
        calls["created"] = kwargs
        return SimpleNamespace(id=uuid.uuid4(), **kwargs)

    monkeypatch.setattr(
        generated_files, "check_and_reserve_storage", fake_check_and_reserve_storage
    )
    monkeypatch.setattr(generated_files, "save_file_to_disk", fake_save_file_to_disk)
    monkeypatch.setattr(generated_files, "get_root_folder_for_user", fake_get_root_folder_for_user)
    monkeypatch.setattr(generated_files, "create_db_file", fake_create_db_file)

    asyncio.run(
        create_generated_video_file(
            pg_engine="engine",
            user_id=user_id,
            prompt="A generated video",
            source_image_ids=[],
            video_bytes=video_bytes,
            extension="mov",
        )
    )

    assert calls["reserved"] == ("engine", user_id, len(video_bytes))
    assert calls["saved"][3] == "generated_videos"
    created_kwargs = calls["created"]
    assert created_kwargs["file_path"] == "generated_videos/saved-video.mov"
    assert created_kwargs["content_type"] == "video/quicktime"
    assert created_kwargs["hash"] == hashlib.sha256(video_bytes).hexdigest()
