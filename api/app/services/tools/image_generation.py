import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, cast

from database.pg.file_ops.file_crud import create_db_file, get_file_by_id, get_root_folder_for_user
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from services.file_encoding import encode_file_as_data_uri
from services.files import get_user_storage_path, save_file_to_disk
from services.inference import get_request_inference_credentials
from services.provider_image_generation import (
    ImageGenerationProviderError,
    generate_image_with_provider,
)
from services.settings import get_user_settings
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

IMAGE_GENERATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "Generate an image from a text prompt, optionally using one or more reference images as context. Use this for pure image creation, edits, variations, merges, style transfers, or any generation grounded in user-provided images.",  # noqa: E501
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A detailed description of the image to generate.",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "4:3", "3:4", "9:16"],
                    "description": "The aspect ratio of the image. Default is 1:1.",
                },
                "resolution": {
                    "type": "string",
                    "enum": ["1K", "2K", "4K"],
                    "description": "The resolution of the generated image. Default is 1K. Should stay 1K unless the user specifically requests higher resolution.",  # noqa: E501
                },
                "source_image_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional reference image IDs to use as context for the generation. Use these when the output should be guided by one or more images from the conversation history.",  # noqa: E501
                },
            },
            "required": ["prompt"],
        },
    },
}


async def _get_image_model_for_request(req, settings) -> str:
    """
    Helper to determine the image model to use.
    Checks the node configuration first, falls back to user settings, then hardcoded default.
    """
    # Default fallback
    model = settings.toolsImageGeneration.defaultModel or "google/gemini-3.1-flash-image-preview"

    # If we have node context, check for a specific model override
    if (
        hasattr(req, "pg_engine")
        and hasattr(req, "graph_id")
        and hasattr(req, "node_id")
        and req.node_id
    ):
        try:
            nodes = await get_nodes_by_ids(
                pg_engine=req.pg_engine,
                graph_id=req.graph_id,
                node_ids=[req.node_id],
            )
            if nodes and nodes[0].data and isinstance(nodes[0].data, dict):
                node_image_model = nodes[0].data.get("imageModel")
                if node_image_model:
                    model = node_image_model
        except Exception as e:
            logger.warning(f"Failed to fetch node specific image model: {e}")

    return model


def _normalize_source_image_ids(arguments: dict[str, Any]) -> list[str]:
    source_image_ids = arguments.get("source_image_ids")
    if not source_image_ids:
        single_id = arguments.get("source_image_id")
        if single_id:
            source_image_ids = [single_id]

    if isinstance(source_image_ids, str):
        source_image_ids = [source_image_ids]

    if not source_image_ids:
        return []

    return [str(image_id) for image_id in source_image_ids]


async def _build_image_content_payload(
    arguments: dict[str, Any],
    *,
    user_id: uuid.UUID,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str | dict[str, Any] | list[dict[str, Any]]:
    prompt = arguments.get("prompt")
    source_image_ids = _normalize_source_image_ids(arguments)

    if not source_image_ids:
        return str(prompt)

    content_payload: list[dict[str, Any]] = [{"type": "text", "text": str(prompt)}]
    user_dir = get_user_storage_path(str(user_id))

    for img_id in source_image_ids:
        try:
            parsed_img_id = uuid.UUID(img_id)
        except ValueError:
            return {"error": f"Source image ID '{img_id}' is invalid."}

        source_file_record = await get_file_by_id(
            pg_engine=pg_engine, file_id=parsed_img_id, user_id=str(user_id)
        )
        if not source_file_record or not source_file_record.file_path:
            return {"error": f"Source image with ID '{img_id}' not found."}

        file_path = Path(user_dir) / source_file_record.file_path
        if not file_path.exists():
            return {"error": f"Source image file with ID '{img_id}' not found on disk."}

        content_type = source_file_record.content_type or "image/png"
        base64_image_uri = encode_file_as_data_uri(file_path, content_type)
        content_payload.append(
            {
                "type": "image_url",
                "image_url": {"url": base64_image_uri},
            }
        )

    return content_payload


async def generate_image(arguments: dict, req) -> dict:
    """
    Generates an image using the configured provider abstraction.
    """
    user_id = uuid.UUID(req.user_id)
    pg_engine: SQLAlchemyAsyncEngine = req.pg_engine

    # Get settings
    settings = await get_user_settings(pg_engine, req.user_id)

    prompt = arguments.get("prompt")
    model = await _get_image_model_for_request(req, settings)
    aspect_ratio = arguments.get("aspect_ratio", "1:1")
    resolution = arguments.get("resolution", "1K")
    source_image_ids = _normalize_source_image_ids(arguments)

    if not prompt:
        return {"error": "Prompt is required for image generation."}

    message_content = await _build_image_content_payload(
        arguments,
        user_id=user_id,
        pg_engine=pg_engine,
    )
    if isinstance(message_content, dict) and message_content.get("error"):
        return message_content
    image_message_content = cast(str | list[dict[str, Any]], message_content)

    try:
        credentials = await get_request_inference_credentials(req)
        generated_image = await generate_image_with_provider(
            credentials=credentials,
            model=model,
            message_content=image_message_content,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            source_image_ids=source_image_ids,
            http_client=req.http_client,
        )

        filename = f"generated_{uuid.uuid4().hex}.{generated_image.extension}"
        unique_filename = await save_file_to_disk(
            user_id=user_id,
            file_contents=generated_image.image_bytes,
            original_filename=filename,
            subdirectory="generated_images",
        )

        root_folder = await get_root_folder_for_user(pg_engine, user_id)
        if not root_folder:
            return {"error": "Could not find root folder for user."}

        new_file = await create_db_file(
            pg_engine=pg_engine,
            user_id=user_id,
            parent_id=root_folder.id,
            name=(
                f"Context: {prompt[:30]}..."
                if source_image_ids
                else f"Gen: {prompt[:30]}.{generated_image.extension}"
            ),
            file_path=str(Path("generated_images") / unique_filename),
            size=len(generated_image.image_bytes),
            content_type=f"image/{generated_image.extension}",
            hash=hashlib.sha256(generated_image.image_bytes).hexdigest(),
        )

        return {
            "success": True,
            "id": str(new_file.id),
            "prompt": prompt,
            "model": generated_image.model,
        }
    except ImageGenerationProviderError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.error("Image generation error: %s", exc, exc_info=True)
        return {"error": f"Internal error during generation: {str(exc)}"}
