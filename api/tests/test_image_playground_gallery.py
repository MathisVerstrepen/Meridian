import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.image_playground.gallery import gallery_item, video_gallery_item


def _file_record(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4(),
        "name": "generated.png",
        "size": 123,
        "content_type": "image/png",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _job_record(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "created_at": now,
        "completed_at": now,
        "prompt": "raw prompt",
        "effective_prompt": "effective prompt",
        "model": "google/gemini-image",
        "aspect_ratio": "1:1",
        "resolution": "1K",
        "duration": None,
        "generate_audio": False,
        "actual_width": 1024,
        "actual_height": 1024,
        "actual_aspect_ratio": "1:1",
        "style_preset": "cinematic",
        "source_image_ids": [str(uuid.uuid4())],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_gallery_item_maps_file_and_job_metadata():
    file_record = _file_record(name="generated-cat.png")
    job_record = _job_record()

    item = gallery_item(file_record, job_record)

    assert item.id == file_record.id
    assert item.name == "generated-cat.png"
    assert item.path == "/Generated Images/generated-cat.png"
    assert item.prompt == "raw prompt"
    assert item.effective_prompt == "effective prompt"
    assert item.model == "google/gemini-image"
    assert item.actual_width == 1024
    assert item.actual_aspect_ratio == "1:1"
    assert item.source_image_ids == job_record.source_image_ids


def test_gallery_item_uses_safe_defaults_without_job_metadata():
    file_record = _file_record()

    item = gallery_item(file_record, None)

    assert item.path == "/Generated Images/generated.png"
    assert item.prompt is None
    assert item.model is None
    assert item.source_image_ids == []


def test_video_gallery_item_maps_persisted_generation_metadata():
    file_created_at = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
    generation_started_at = datetime(2026, 8, 5, 9, 58, tzinfo=timezone.utc)
    generation_completed_at = datetime(2026, 8, 5, 9, 59, tzinfo=timezone.utc)
    source_image_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    file_record = _file_record(
        name="generated-video.mp4",
        content_type="video/mp4",
        created_at=file_created_at,
        updated_at=file_created_at,
    )
    job_record = _job_record(
        created_at=generation_started_at,
        completed_at=generation_completed_at,
        prompt="A cinematic valley",
        effective_prompt="A cinematic valley",
        model="provider/resolved-video-model",
        aspect_ratio="16:9",
        resolution="1080p",
        duration=6,
        generate_audio=True,
        source_image_ids=source_image_ids,
    )

    item = video_gallery_item(file_record, job_record)

    assert item.id == file_record.id
    assert item.path == "/Generated Videos/generated-video.mp4"
    assert item.generation_started_at == generation_started_at
    assert item.generation_completed_at == generation_completed_at
    assert item.prompt == "A cinematic valley"
    assert item.effective_prompt == "A cinematic valley"
    assert item.model == "provider/resolved-video-model"
    assert item.aspect_ratio == "16:9"
    assert item.resolution == "1080p"
    assert item.duration == 6
    assert item.generate_audio is True
    assert item.source_image_ids == source_image_ids
