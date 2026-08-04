import asyncio
import os
import random
import sys
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, features

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_DIR))

from services import image_previews
from services.image_previews import (
    IMAGE_PREVIEW_PRESETS,
    ImagePreviewSpec,
    _build_cache_key,
    ensure_image_preview,
)


def _write_image(path: Path, size: tuple[int, int] = (800, 600)) -> None:
    Image.new("RGBA", size, (20, 80, 160, 120)).save(path, format="PNG")


def test_image_preview_presets_have_fixed_quality_and_version() -> None:
    assert {
        size: (spec.width, spec.height, spec.output_format, spec.quality, spec.transform_version)
        for size, spec in IMAGE_PREVIEW_PRESETS.items()
    } == {
        "48x48": (48, 48, "WEBP", 80, 1),
        "160x160": (160, 160, "WEBP", 80, 1),
        "512x512": (512, 512, "WEBP", 80, 1),
    }


@pytest.mark.parametrize(
    ("size", "expected_dimensions"),
    [
        ("48x48", (48, 48)),
        ("160x160", (160, 160)),
        ("512x512", (512, 512)),
    ],
)
def test_image_preview_renders_exact_webp_presets(
    tmp_path: Path,
    monkeypatch,
    size,
    expected_dimensions: tuple[int, int],
) -> None:
    assert features.check("webp"), "Installed Pillow must support WebP"
    user_id = uuid.uuid4()
    source_path = tmp_path / "images" / "source.png"
    source_path.parent.mkdir()
    _write_image(source_path)
    monkeypatch.setattr(image_previews, "get_user_storage_path", lambda _: str(tmp_path))

    artifact = asyncio.run(ensure_image_preview(user_id, "images/source.png", size, "hash-a"))

    assert artifact is not None
    assert artifact.media_type == "image/webp"
    assert artifact.path.endswith(".webp")
    with Image.open(artifact.path) as preview:
        assert preview.format == "WEBP"
        assert preview.size == expected_dimensions


def test_image_preview_is_smaller_than_deterministic_multimegabyte_png(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "source.png"
    random_bytes = random.Random(1729).randbytes(1024 * 1024 * 3)
    Image.frombytes("RGB", (1024, 1024), random_bytes).save(source_path, format="PNG")
    assert source_path.stat().st_size > 2 * 1024 * 1024
    monkeypatch.setattr(image_previews, "get_user_storage_path", lambda _: str(tmp_path))

    artifact = asyncio.run(
        ensure_image_preview(uuid.uuid4(), "source.png", "512x512", "fixture-hash")
    )

    assert artifact is not None
    assert os.path.getsize(artifact.path) < source_path.stat().st_size


def test_image_preview_reuses_exact_cache_and_invalidates_changed_source_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "source.png"
    _write_image(source_path)
    monkeypatch.setattr(image_previews, "get_user_storage_path", lambda _: str(tmp_path))
    user_id = uuid.uuid4()

    first = asyncio.run(ensure_image_preview(user_id, "source.png", "160x160", "hash-a"))
    assert first is not None
    first_mtime_ns = os.stat(first.path).st_mtime_ns

    def fail_render(*args, **kwargs):
        raise AssertionError("exact cache hit must not render")

    original_render = image_previews._render_preview_sync
    monkeypatch.setattr(image_previews, "_render_preview_sync", fail_render)
    cached = asyncio.run(ensure_image_preview(user_id, "source.png", "160x160", "hash-a"))
    assert cached == first
    assert os.stat(first.path).st_mtime_ns == first_mtime_ns

    monkeypatch.setattr(image_previews, "_render_preview_sync", original_render)
    changed_hash = asyncio.run(
        ensure_image_preview(user_id, "source.png", "160x160", "hash-b")
    )
    assert changed_hash is not None
    assert changed_hash.path != first.path

    _write_image(source_path, size=(801, 600))
    changed_stat = asyncio.run(
        ensure_image_preview(user_id, "source.png", "160x160", "hash-b")
    )
    assert changed_stat is not None
    assert changed_stat.path != changed_hash.path


@pytest.mark.parametrize(
    "changed_spec",
    [
        replace(ImagePreviewSpec(160, 160), width=48),
        replace(ImagePreviewSpec(160, 160), height=48),
        replace(ImagePreviewSpec(160, 160), output_format="PNG"),
        replace(ImagePreviewSpec(160, 160), quality=81),
        replace(ImagePreviewSpec(160, 160), transform_version=2),
    ],
)
def test_image_preview_cache_key_includes_transform_identity(changed_spec) -> None:
    original_spec = IMAGE_PREVIEW_PRESETS["160x160"]
    identity = {
        "relative_source_path": "images/source.png",
        "content_hash": "hash-a",
        "source_size": 123,
        "source_mtime_ns": 456,
    }

    assert _build_cache_key(**identity, spec=changed_spec) != _build_cache_key(
        **identity, spec=original_spec
    )


def test_image_preview_atomically_replaces_unique_temp_file(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "source.png"
    _write_image(source_path)
    monkeypatch.setattr(image_previews, "get_user_storage_path", lambda _: str(tmp_path))
    replacements: list[tuple[str, str]] = []
    original_replace = image_previews.os.replace

    def record_replace(source: str, target: str) -> None:
        replacements.append((source, target))
        original_replace(source, target)

    monkeypatch.setattr(image_previews.os, "replace", record_replace)

    artifact = asyncio.run(
        ensure_image_preview(uuid.uuid4(), "source.png", "48x48", "hash-a")
    )

    assert artifact is not None
    assert len(replacements) == 1
    assert replacements[0][1] == artifact.path
    assert replacements[0][0] != artifact.path
    assert not os.path.exists(replacements[0][0])
