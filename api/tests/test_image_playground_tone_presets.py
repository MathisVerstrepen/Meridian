import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

import services.image_playground.tone_presets as tone_presets_module
from database.pg.models import CustomImageTonePreset
from fastapi import HTTPException
from schemas.images import CustomImageTonePresetCreate
from services.image_playground.constants import MAX_CUSTOM_TONE_PRESETS_PER_USER


def test_create_custom_image_tone_preset_returns_429_when_user_cap_reached(monkeypatch):
    class FakeSession:
        def __init__(self, engine, expire_on_commit=False):
            self.engine = engine
            self.expire_on_commit = expire_on_commit

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def scalar(self, query):
            self.engine.query = query
            return MAX_CUSTOM_TONE_PRESETS_PER_USER

        def add(self, preset):
            self.engine.added.append(preset)

        async def commit(self):
            self.engine.committed = True

    fake_engine = SimpleNamespace(added=[], committed=False, query=None)
    monkeypatch.setattr(tone_presets_module, "AsyncSession", FakeSession)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            tone_presets_module.create_custom_image_tone_preset(
                fake_engine,
                user_id=uuid.uuid4(),
                payload=CustomImageTonePresetCreate(label="Tone", suffix="cinematic light"),
            )
        )

    assert exc_info.value.status_code == 429
    assert "Too many custom tone presets" in exc_info.value.detail
    assert fake_engine.added == []
    assert fake_engine.committed is False


def test_delete_custom_image_tone_preset_deletes_owned_preset(monkeypatch):
    class FakeScalarResult:
        def __init__(self, preset):
            self.preset = preset

        def first(self):
            return self.preset

    class FakeResult:
        def __init__(self, preset):
            self.preset = preset

        def scalars(self):
            return FakeScalarResult(self.preset)

    class FakeSession:
        def __init__(self, engine):
            self.engine = engine

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def exec(self, query):
            self.engine.query = query
            return FakeResult(self.engine.preset)

        async def delete(self, preset):
            self.engine.deleted = preset

        async def commit(self):
            self.engine.committed = True

    preset = CustomImageTonePreset(user_id=uuid.uuid4(), label="Tone", suffix="soft light")
    fake_engine = SimpleNamespace(preset=preset, deleted=None, committed=False, query=None)
    monkeypatch.setattr(tone_presets_module, "AsyncSession", FakeSession)

    asyncio.run(
        tone_presets_module.delete_custom_image_tone_preset(
            fake_engine,
            user_id=preset.user_id,
            preset_id=preset.id,
        )
    )

    assert fake_engine.deleted is preset
    assert fake_engine.committed is True


def test_delete_custom_image_tone_preset_returns_404_when_missing(monkeypatch):
    class FakeScalarResult:
        def first(self):
            return None

    class FakeResult:
        def scalars(self):
            return FakeScalarResult()

    class FakeSession:
        def __init__(self, engine):
            self.engine = engine

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def exec(self, query):
            self.engine.query = query
            return FakeResult()

        async def delete(self, preset):
            self.engine.deleted = preset

        async def commit(self):
            self.engine.committed = True

    fake_engine = SimpleNamespace(deleted=None, committed=False, query=None)
    monkeypatch.setattr(tone_presets_module, "AsyncSession", FakeSession)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            tone_presets_module.delete_custom_image_tone_preset(
                fake_engine,
                user_id=uuid.uuid4(),
                preset_id=uuid.uuid4(),
            )
        )

    assert exc_info.value.status_code == 404
    assert fake_engine.deleted is None
    assert fake_engine.committed is False
