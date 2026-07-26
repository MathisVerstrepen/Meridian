import asyncio
import base64
import io
import uuid
import warnings
from pathlib import Path
from typing import Any

from database.pg.file_ops.file_crud import get_file_by_id
from PIL import Image, ImageOps, UnidentifiedImageError
from services.files import get_user_storage_path
from services.tools.runtime_results import ToolExecutionEnvelope, TransientImageContent

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_SOURCE_PIXELS = 20_000_000
MAX_INSPECTION_EDGE = 1600
MAX_INSPECTION_PIXELS = 2_560_000
MAX_DATA_URI_BYTES = 2 * 1024 * 1024

INSPECT_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "inspect_image",
        "description": (
            "Load one user-owned image into your immediate visual context by its file UUID. "
            "Use this only when seeing a generated image is necessary."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "UUID returned by an image-generation tool.",
                }
            },
            "required": ["file_id"],
            "additionalProperties": False,
        },
    },
}


def _error(message: str, file_id: str | None = None) -> ToolExecutionEnvelope:
    result: dict[str, Any] = {"error": message}
    if file_id:
        result["file_id"] = file_id
    return ToolExecutionEnvelope(result)


def _prepare_image(path: Path, file_id: str, source_content_type: str) -> ToolExecutionEnvelope:
    try:
        source_size = path.stat().st_size
    except OSError:
        return _error("Image is unavailable.", file_id)
    if source_size <= 0 or source_size > MAX_SOURCE_BYTES:
        return _error("Image exceeds inspection resource limits.", file_id)

    try:
        source_bytes = path.read_bytes()
    except OSError:
        return _error("Image is unavailable.", file_id)
    if len(source_bytes) > MAX_SOURCE_BYTES:
        return _error("Image exceeds inspection resource limits.", file_id)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(source_bytes)) as opened:
                opened.seek(0)
                decoded_content_type = Image.MIME.get(str(opened.format or "").upper())
                declared_content_type = source_content_type.lower().replace(
                    "image/jpg", "image/jpeg"
                )
                if decoded_content_type != declared_content_type:
                    return _error("File image type does not match its metadata.", file_id)
                original_width, original_height = opened.size
                if (
                    original_width <= 0
                    or original_height <= 0
                    or original_width * original_height > MAX_SOURCE_PIXELS
                ):
                    return _error("Image exceeds inspection resource limits.", file_id)
                image = ImageOps.exif_transpose(opened).copy()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError):
        return _error("File is not a supported raster image.", file_id)
    except (OSError, ValueError):
        return _error("Image could not be decoded safely.", file_id)

    try:
        width, height = image.size
        scale = min(1.0, MAX_INSPECTION_EDGE / max(width, height))
        if width * height * scale * scale > MAX_INSPECTION_PIXELS:
            scale = min(scale, (MAX_INSPECTION_PIXELS / (width * height)) ** 0.5)
        target = (max(1, int(width * scale)), max(1, int(height * scale)))
        if target != image.size:
            image.thumbnail(target, Image.Resampling.LANCZOS)

        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            flattened = Image.new("RGB", rgba.size, "white")
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            image = flattened
        elif image.mode != "RGB":
            image = image.convert("RGB")

        encoded = b""
        for quality in (85, 75, 65, 55):
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            encoded = output.getvalue()
            data_uri_size = len(encoded) * 4 // 3 + 64
            if data_uri_size <= MAX_DATA_URI_BYTES:
                break
        else:
            return _error("Image exceeds inspection output limits.", file_id)

        data_uri = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
        if len(data_uri.encode("ascii")) > MAX_DATA_URI_BYTES:
            return _error("Image exceeds inspection output limits.", file_id)

        result = {
            "success": True,
            "file_id": file_id,
            "source_content_type": source_content_type,
            "original_width": original_width,
            "original_height": original_height,
            "inspection_content_type": "image/jpeg",
            "inspection_width": image.width,
            "inspection_height": image.height,
            "inspection_bytes": len(encoded),
        }
        return ToolExecutionEnvelope(
            result,
            (TransientImageContent(file_id=file_id, data_uri=data_uri),),
        )
    finally:
        image.close()


async def inspect_image(arguments: dict, req: Any) -> ToolExecutionEnvelope:
    if not bool(getattr(req, "image_inspection_enabled", False)):
        return _error("Image inspection is unavailable for this request.")

    raw_file_id = arguments.get("file_id")
    try:
        file_id = uuid.UUID(str(raw_file_id))
    except (TypeError, ValueError, AttributeError):
        return _error("A valid file UUID is required.")

    file_id_text = str(file_id)
    record = await get_file_by_id(req.pg_engine, file_id, user_id=req.user_id)
    if record is None:
        return _error("Image is unavailable.", file_id_text)
    if (
        record.type != "file"
        or record.storage_provider != "local"
        or not record.file_path
        or not str(record.content_type or "").lower().startswith("image/")
        or str(record.content_type or "").lower() == "image/svg+xml"
    ):
        return _error("File is not a supported local raster image.", file_id_text)
    if record.size is not None and (record.size <= 0 or record.size > MAX_SOURCE_BYTES):
        return _error("Image exceeds inspection resource limits.", file_id_text)

    relative_path = Path(record.file_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return _error("Image is unavailable.", file_id_text)
    root = Path(get_user_storage_path(req.user_id)).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return _error("Image is unavailable.", file_id_text)
    if not candidate.is_file():
        return _error("Image is unavailable.", file_id_text)

    return await asyncio.to_thread(
        _prepare_image,
        candidate,
        file_id_text,
        str(record.content_type),
    )
