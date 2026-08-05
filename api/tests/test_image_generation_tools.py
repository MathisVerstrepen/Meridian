import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

import services.tools.image_generation as tools


def test_generate_image_records_completed_gallery_metadata(monkeypatch):
    calls: dict[str, object] = {}
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    source_image_id = uuid.uuid4()
    req = SimpleNamespace(
        user_id=str(user_id),
        pg_engine="engine",
        http_client="client",
    )

    async def fake_get_user_settings(pg_engine, requested_user_id):
        return SimpleNamespace()

    async def fake_get_model(req, settings):
        return "requested/image-model"

    async def fake_build_payload(arguments, **kwargs):
        calls["payload"] = (arguments, kwargs)
        return "A mountain lake"

    async def fake_get_credentials(request):
        return "credentials"

    async def fake_generate_image(**kwargs):
        calls["provider"] = kwargs
        return SimpleNamespace(
            image_bytes=b"generated-image",
            extension="png",
            model="provider/resolved-image-model",
        )

    async def fake_save_file(**kwargs):
        calls["saved"] = kwargs
        return "generated.png"

    async def fake_get_root(pg_engine, requested_user_id):
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_create_file(**kwargs):
        calls["file"] = kwargs
        return SimpleNamespace(id=file_id)

    def fake_measure(image_bytes):
        calls["measured"] = image_bytes
        return 1600, 900, "16:9"

    async def fake_create_job(**kwargs):
        calls["job"] = kwargs
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(tools, "get_user_settings", fake_get_user_settings)
    monkeypatch.setattr(tools, "_get_image_model_for_request", fake_get_model)
    monkeypatch.setattr(tools, "_build_image_content_payload", fake_build_payload)
    monkeypatch.setattr(tools, "get_request_inference_credentials", fake_get_credentials)
    monkeypatch.setattr(tools, "generate_image_with_provider", fake_generate_image)
    monkeypatch.setattr(tools, "save_file_to_disk", fake_save_file)
    monkeypatch.setattr(tools, "get_root_folder_for_user", fake_get_root)
    monkeypatch.setattr(tools, "create_db_file", fake_create_file)
    monkeypatch.setattr(tools, "measure_image_dimensions", fake_measure)
    monkeypatch.setattr(tools, "create_completed_generation_job", fake_create_job)

    result = asyncio.run(
        tools.generate_image(
            {
                "prompt": "A mountain lake",
                "aspect_ratio": "16:9",
                "resolution": "2K",
                "source_image_id": str(source_image_id),
            },
            req,
        )
    )

    assert result == {
        "success": True,
        "id": str(file_id),
        "prompt": "A mountain lake",
        "model": "provider/resolved-image-model",
    }
    provider_kwargs = calls["provider"]
    assert provider_kwargs["model"] == "requested/image-model"
    assert provider_kwargs["aspect_ratio"] == "16:9"
    assert provider_kwargs["resolution"] == "2K"
    assert provider_kwargs["source_image_ids"] == [str(source_image_id)]
    assert calls["measured"] == b"generated-image"
    job_kwargs = calls["job"]
    assert job_kwargs["pg_engine"] == "engine"
    assert job_kwargs["user_id"] == user_id
    assert job_kwargs["file_id"] == file_id
    assert job_kwargs["prompt"] == "A mountain lake"
    assert job_kwargs["model"] == "provider/resolved-image-model"
    assert job_kwargs["media_type"] == "image"
    assert job_kwargs["aspect_ratio"] == "16:9"
    assert job_kwargs["resolution"] == "2K"
    assert job_kwargs["source_image_ids"] == [str(source_image_id)]
    assert job_kwargs["actual_width"] == 1600
    assert job_kwargs["actual_height"] == 900
    assert job_kwargs["actual_aspect_ratio"] == "16:9"
    assert isinstance(job_kwargs["generation_started_at"], datetime)
    assert job_kwargs["generation_started_at"].tzinfo == timezone.utc


def test_generate_video_records_normalized_completed_gallery_metadata(monkeypatch):
    calls: dict[str, object] = {}
    user_id = uuid.uuid4()
    file_id = uuid.uuid4()
    source_image_id = uuid.uuid4()
    req = SimpleNamespace(
        user_id=str(user_id),
        pg_engine="engine",
        http_client="client",
    )

    async def fake_get_user_settings(pg_engine, requested_user_id):
        return SimpleNamespace()

    async def fake_get_model(req, settings):
        return "requested/video-model"

    async def fake_build_references(arguments, **kwargs):
        calls["references"] = (arguments, kwargs)
        return [{"type": "image_url"}]

    async def fake_get_credentials(request):
        return "credentials"

    async def fake_generate_video(**kwargs):
        calls["provider"] = kwargs
        return SimpleNamespace(
            video_bytes=b"generated-video",
            extension="mp4",
            model="provider/resolved-video-model",
            job_id="provider-job-id",
        )

    async def fake_create_video_file(**kwargs):
        calls["file"] = kwargs
        return SimpleNamespace(id=file_id)

    async def fake_create_job(**kwargs):
        calls["job"] = kwargs
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(tools, "get_user_settings", fake_get_user_settings)
    monkeypatch.setattr(tools, "_get_video_model_for_request", fake_get_model)
    monkeypatch.setattr(tools, "_build_video_reference_payload", fake_build_references)
    monkeypatch.setattr(tools, "get_request_inference_credentials", fake_get_credentials)
    monkeypatch.setattr(tools, "generate_video_with_provider", fake_generate_video)
    monkeypatch.setattr(tools, "create_generated_video_file", fake_create_video_file)
    monkeypatch.setattr(tools, "create_completed_generation_job", fake_create_job)

    result = asyncio.run(
        tools.generate_video(
            {
                "prompt": "Clouds moving over a valley",
                "aspect_ratio": "9:16",
                "resolution": "1080p",
                "duration": "6",
                "generate_audio": 1,
                "source_image_ids": str(source_image_id),
            },
            req,
        )
    )

    assert result == {
        "success": True,
        "id": str(file_id),
        "prompt": "Clouds moving over a valley",
        "model": "provider/resolved-video-model",
        "job_id": "provider-job-id",
    }
    provider_kwargs = calls["provider"]
    assert provider_kwargs["model"] == "requested/video-model"
    assert provider_kwargs["duration"] == 6
    assert provider_kwargs["generate_audio"] is True
    assert provider_kwargs["input_references"] == [{"type": "image_url"}]
    file_kwargs = calls["file"]
    assert file_kwargs["source_image_ids"] == [str(source_image_id)]
    job_kwargs = calls["job"]
    assert job_kwargs["file_id"] == file_id
    assert job_kwargs["prompt"] == "Clouds moving over a valley"
    assert job_kwargs["model"] == "provider/resolved-video-model"
    assert job_kwargs["media_type"] == "video"
    assert job_kwargs["aspect_ratio"] == "9:16"
    assert job_kwargs["resolution"] == "1080p"
    assert job_kwargs["duration"] == 6
    assert job_kwargs["generate_audio"] is True
    assert job_kwargs["source_image_ids"] == [str(source_image_id)]
    assert isinstance(job_kwargs["generation_started_at"], datetime)
    assert job_kwargs["generation_started_at"].tzinfo == timezone.utc


def test_alibaba_image_reference_count_is_rejected_before_file_lookup(monkeypatch):
    async def fail_lookup(**_kwargs):
        raise AssertionError("oversized reference list must fail before file lookup")

    monkeypatch.setattr(tools, "get_file_by_id", fail_lookup)
    result = asyncio.run(
        tools._build_image_content_payload(
            {"prompt": "draw", "source_image_ids": [str(uuid.uuid4()) for _ in range(4)]},
            user_id=uuid.uuid4(),
            pg_engine=SimpleNamespace(),
            model="alibaba-token-plan/future-image",
        )
    )

    assert result == {"error": "Alibaba image generation accepts at most 3 references."}


def test_alibaba_i2v_requires_reference_before_file_lookup(monkeypatch):
    async def fail_lookup(**_kwargs):
        raise AssertionError("missing reference must fail before file lookup")

    monkeypatch.setattr(tools, "get_file_by_id", fail_lookup)
    result = asyncio.run(
        tools._build_video_reference_payload(
            {"source_image_ids": []},
            user_id=uuid.uuid4(),
            pg_engine=SimpleNamespace(),
            model="alibaba-token-plan/happyhorse-future-i2v",
        )
    )

    assert result == {"error": "HappyHorse i2v requires exactly one first-frame image."}
