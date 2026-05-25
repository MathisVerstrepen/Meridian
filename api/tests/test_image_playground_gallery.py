import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.image_playground.gallery import gallery_item


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
