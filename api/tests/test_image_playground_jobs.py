import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

import services.image_playground.jobs as jobs_module
from database.pg.models import ImageGenerationJob
from fastapi import HTTPException
from pydantic import ValidationError
from schemas.images import CreateImageJobsPayload, ImageGenerationTaskPayload, VideoGenerationPayload
from services.image_playground.constants import (
    MAX_ACTIVE_GENERATION_JOBS_PER_USER,
    MAX_SOURCE_IMAGE_REFERENCES,
)
from services.image_playground.jobs import (
    STALE_GENERATION_JOB_ERROR,
    batch_status,
    clear_failed_image_jobs,
    count_active_generation_jobs,
    get_model_output_modalities,
    job_response,
    mark_stale_generation_job_failed,
    recover_stale_image_generation_jobs,
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
        is_preview=True,
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
    assert response.is_preview is True


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


def test_image_generation_task_payload_validates_source_image_ids():
    reference_id = uuid.uuid4()

    payload = ImageGenerationTaskPayload(
        prompt="prompt",
        model="google/gemini-image",
        source_image_ids=[str(reference_id)],
    )

    assert payload.source_image_ids == [reference_id]

    with pytest.raises(ValidationError):
        ImageGenerationTaskPayload(
            prompt="prompt",
            model="google/gemini-image",
            source_image_ids=["not-a-uuid"],
        )

    with pytest.raises(ValidationError):
        ImageGenerationTaskPayload(
            prompt="prompt",
            model="google/gemini-image",
            source_image_ids=[str(uuid.uuid4()) for _ in range(MAX_SOURCE_IMAGE_REFERENCES + 1)],
        )


def test_video_generation_payload_validates_source_image_ids():
    reference_id = uuid.uuid4()

    payload = VideoGenerationPayload(
        prompt="prompt",
        model="google/veo-3.1",
        source_image_ids=[str(reference_id)],
    )

    assert payload.source_image_ids == [reference_id]

    with pytest.raises(ValidationError):
        VideoGenerationPayload(
            prompt="prompt",
            model="google/veo-3.1",
            source_image_ids=["not-a-uuid"],
        )

    with pytest.raises(ValidationError):
        VideoGenerationPayload(
            prompt="prompt",
            model="google/veo-3.1",
            source_image_ids=[str(uuid.uuid4()) for _ in range(MAX_SOURCE_IMAGE_REFERENCES + 1)],
        )


def test_count_active_generation_jobs_returns_count():
    class FakeSession:
        def __init__(self):
            self.query = None

        async def scalar(self, query):
            self.query = query
            return 7

    fake_session = FakeSession()

    count = asyncio.run(count_active_generation_jobs(fake_session, user_id=uuid.uuid4()))

    assert count == 7
    assert fake_session.query is not None


def test_create_image_jobs_returns_429_when_user_active_cap_reached(monkeypatch):
    class FakeSession:
        def __init__(self, engine):
            self.engine = engine

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def scalar(self, query):
            self.engine.query = query
            return MAX_ACTIVE_GENERATION_JOBS_PER_USER

        def add(self, job):
            self.engine.added.append(job)

        async def commit(self):
            self.engine.committed = True

        async def refresh(self, job):
            self.engine.refreshed.append(job)

    fake_engine = SimpleNamespace(added=[], committed=False, refreshed=[], query=None)
    payload = CreateImageJobsPayload(
        tasks=[ImageGenerationTaskPayload(prompt="prompt", model="google/gemini-image")]
    )
    monkeypatch.setattr(jobs_module, "AsyncSession", FakeSession)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            jobs_module.create_image_jobs(
                fake_engine,
                payload=payload,
                user_id=uuid.uuid4(),
            )
        )

    assert exc_info.value.status_code == 429
    assert "Too many active generation jobs" in exc_info.value.detail
    assert fake_engine.added == []
    assert fake_engine.committed is False


def test_clear_failed_image_jobs_uses_bulk_delete(monkeypatch):
    class FakeSession:
        def __init__(self, engine):
            self.engine = engine

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def exec(self, query):
            self.engine.query = query

        async def delete(self, job):
            self.engine.deleted.append(job)

        async def commit(self):
            self.engine.committed = True

    fake_engine = SimpleNamespace(query=None, deleted=[], committed=False)
    monkeypatch.setattr(jobs_module, "AsyncSession", FakeSession)

    asyncio.run(clear_failed_image_jobs(fake_engine, user_id=uuid.uuid4()))

    assert fake_engine.query is not None
    assert str(fake_engine.query).startswith("DELETE FROM image_generation_jobs")
    assert fake_engine.deleted == []
    assert fake_engine.committed is True


def test_mark_stale_generation_job_failed_makes_job_retryable():
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    recovered_at = datetime.now(timezone.utc)
    job = _job("retrying", updated_at=stale_time, attempts=3)

    mark_stale_generation_job_failed(job, recovered_at=recovered_at)

    assert job.status == "failed"
    assert job.error == STALE_GENERATION_JOB_ERROR
    assert job.attempts == 3
    assert job.updated_at == recovered_at
    assert job.completed_at == recovered_at


def test_recover_stale_image_generation_jobs_marks_jobs_failed(monkeypatch):
    class FakeResult:
        def __init__(self, jobs):
            self.jobs = jobs

        def all(self):
            return self.jobs

    class FakeSession:
        def __init__(self, engine):
            self.engine = engine

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def exec(self, query):
            self.engine.query = query
            return FakeResult(self.engine.jobs)

        def add(self, job):
            self.engine.added.append(job)

        async def commit(self):
            self.engine.committed = True

    stale_job = _job("processing", updated_at=datetime.now(timezone.utc) - timedelta(minutes=20))
    fake_engine = SimpleNamespace(jobs=[stale_job], added=[], committed=False, query=None)
    monkeypatch.setattr(jobs_module, "AsyncSession", FakeSession)

    recovered = asyncio.run(recover_stale_image_generation_jobs(fake_engine, stale_after_seconds=1))

    assert recovered == 1
    assert fake_engine.added == [stale_job]
    assert fake_engine.committed is True
    assert stale_job.status == "failed"
    assert stale_job.error == STALE_GENERATION_JOB_ERROR
