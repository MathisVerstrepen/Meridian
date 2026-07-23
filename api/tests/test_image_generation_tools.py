import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

import services.tools.image_generation as tools


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
