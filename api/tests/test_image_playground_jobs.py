import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.models import ImageGenerationJob
from services.image_playground.jobs import (
    batch_status,
    get_model_output_modalities,
    job_response,
    send_job_update,
)


def _job(status: str = "pending", **overrides) -> ImageGenerationJob:
    values = {
        "id": uuid.uuid4(),
        "batch_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "status": status,
        "prompt": "prompt",
        "effective_prompt": "effective prompt",
        "model": "google/gemini-image",
        "aspect_ratio": "1:1",
        "resolution": "1K",
        "source_image_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return ImageGenerationJob(**values)


def test_batch_status_handles_terminal_and_mixed_batches():
    assert batch_status([]) == "not_found"
    assert batch_status([_job("completed"), _job("completed")]) == "completed"
    assert batch_status([_job("cancelled"), _job("cancelled")]) == "cancelled"
    assert batch_status([_job("completed"), _job("failed")]) == "completed_with_errors"
    assert batch_status([_job("failed"), _job("failed")]) == "failed"
    assert batch_status([_job("processing"), _job("pending")]) == "processing"
    assert batch_status([_job("pending")]) == "pending"


def test_job_response_maps_all_persisted_fields():
    file_id = uuid.uuid4()
    job = _job(
        "completed",
        file_id=file_id,
        actual_width=1024,
        actual_height=768,
        actual_aspect_ratio="4:3",
        style_preset="cinematic",
        source_image_ids=[str(uuid.uuid4())],
        attempts=2,
        max_attempts=6,
        error=None,
        completed_at=datetime.now(timezone.utc),
    )

    response = job_response(job)

    assert response.id == job.id
    assert response.batch_id == job.batch_id
    assert response.file_id == file_id
    assert response.actual_width == 1024
    assert response.actual_aspect_ratio == "4:3"
    assert response.style_preset == "cinematic"
    assert response.source_image_ids == job.source_image_ids
    assert response.attempts == 2


def test_get_model_output_modalities_reads_available_model_architecture():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                available_models=SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            id="google/gemini-image",
                            architecture=SimpleNamespace(output_modalities=["text", "image"]),
                        )
                    ]
                )
            )
        )
    )

    assert get_model_output_modalities(request, "google/gemini-image") == ["text", "image"]
    assert get_model_output_modalities(request, "missing-model") is None


def test_send_job_update_targets_job_user_with_json_safe_payload():
    class FakeConnectionManager:
        def __init__(self):
            self.messages = []

        async def send_to_user(self, user_id, message):
            self.messages.append((user_id, message))

    connection_manager = FakeConnectionManager()
    job = _job("processing")

    asyncio.run(send_job_update(connection_manager, job))

    [(sent_user_id, message)] = connection_manager.messages
    assert sent_user_id == str(job.user_id)
    assert message["type"] == "image_generation_job_update"
    assert message["payload"]["id"] == str(job.id)
    assert message["payload"]["batch_id"] == str(job.batch_id)
