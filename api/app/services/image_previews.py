import asyncio
import hashlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from typing import Literal, Optional

import aiofiles.os
from PIL import Image, ImageOps
from services.files import get_user_storage_path

ImagePreviewSize = Literal["48x48", "160x160", "512x512"]


@dataclass(frozen=True)
class ImagePreviewSpec:
    width: int
    height: int
    output_format: str = "WEBP"
    extension: str = ".webp"
    media_type: str = "image/webp"
    quality: int = 80
    optimize: bool = True
    resampling: str = "LANCZOS"
    centering: tuple[float, float] = (0.5, 0.5)
    transform_version: int = 1


@dataclass(frozen=True)
class ImagePreviewArtifact:
    path: str
    media_type: str


IMAGE_PREVIEW_PRESETS: dict[ImagePreviewSize, ImagePreviewSpec] = {
    "48x48": ImagePreviewSpec(width=48, height=48),
    "160x160": ImagePreviewSpec(width=160, height=160),
    "512x512": ImagePreviewSpec(width=512, height=512),
}

logger = logging.getLogger("uvicorn.error")


def _build_cache_key(
    *,
    relative_source_path: str,
    content_hash: Optional[str],
    source_size: int,
    source_mtime_ns: int,
    spec: ImagePreviewSpec,
) -> str:
    identity = {
        "relative_source_path": relative_source_path,
        "content_hash": content_hash,
        "source_size": source_size,
        "source_mtime_ns": source_mtime_ns,
        "transform": asdict(spec),
    }
    encoded_identity = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded_identity).hexdigest()


def _render_preview_sync(
    source_path: str,
    target_path: str,
    spec: ImagePreviewSpec,
) -> None:
    temp_path = f"{target_path}.{uuid.uuid4().hex}.tmp"
    try:
        with Image.open(source_path) as image:
            preview = ImageOps.fit(
                image,
                (spec.width, spec.height),
                method=getattr(Image.Resampling, spec.resampling),
                centering=spec.centering,
            )
            if preview.mode not in ("RGB", "RGBA"):
                has_alpha = "A" in preview.getbands() or "transparency" in preview.info
                preview = preview.convert("RGBA" if has_alpha else "RGB")
            preview.save(
                temp_path,
                format=spec.output_format,
                quality=spec.quality,
                optimize=spec.optimize,
            )
        os.replace(temp_path, target_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


async def ensure_image_preview(
    user_id: uuid.UUID,
    unique_filename: str,
    size: ImagePreviewSize,
    content_hash: Optional[str],
) -> Optional[ImagePreviewArtifact]:
    spec = IMAGE_PREVIEW_PRESETS[size]
    user_base = get_user_storage_path(user_id)
    source_path = os.path.join(user_base, unique_filename)

    try:
        source_stat = await aiofiles.os.stat(source_path)
    except OSError:
        return None

    cache_key = _build_cache_key(
        relative_source_path=unique_filename,
        content_hash=content_hash,
        source_size=source_stat.st_size,
        source_mtime_ns=source_stat.st_mtime_ns,
        spec=spec,
    )
    relative_dir = os.path.dirname(unique_filename)
    source_stem = os.path.splitext(os.path.basename(unique_filename))[0]
    target_dir = os.path.join(user_base, ".cache", "previews", relative_dir)
    target_path = os.path.join(target_dir, f"{source_stem}_{cache_key}{spec.extension}")

    if await aiofiles.os.path.exists(target_path):
        return ImagePreviewArtifact(path=target_path, media_type=spec.media_type)

    try:
        await aiofiles.os.makedirs(target_dir, exist_ok=True)
        await asyncio.to_thread(_render_preview_sync, source_path, target_path, spec)
    except Exception as error:
        logger.error("Failed to render image preview for %s: %s", source_path, error)
        return None

    return ImagePreviewArtifact(path=target_path, media_type=spec.media_type)
