import base64
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx
from database.pg.file_ops.file_crud import create_db_file, get_file_by_id, get_root_folder_for_user
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from services.file_encoding import encode_file_as_data_uri
from services.files import get_user_storage_path, save_file_to_disk
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
    model = settings.toolsImageGeneration.defaultModel or "google/gemini-2.5-flash-image"

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
    Generates an image using the OpenRouter chat/completions endpoint with image modalities.
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

    # URL for Chat Completions (as per new docs)
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {req.headers['Authorization'].replace('Bearer ', '')}",
        "Content-Type": "application/json",
        "HTTP-Referer": req.headers.get("HTTP-Referer", "https://meridian.diikstra.fr/"),
        "X-Title": req.headers.get("X-Title", "Meridian"),
    }

    # Payload structure for Image Generation via Chat
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": message_content}],
        "modalities": ["image", "text"],
    }

    # Add image config for supported models (like Gemini)
    if "gemini" in model.lower():
        payload["image_config"] = {"image_size": resolution}
        if not source_image_ids:
            payload["image_config"]["aspect_ratio"] = aspect_ratio

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                error_msg = response.text
                try:
                    err_json = response.json()
                    # OpenRouter/Provider error structure
                    if "error" in err_json:
                        if isinstance(err_json["error"], dict):
                            error_msg = err_json["error"].get("message", error_msg)
                        else:
                            error_msg = str(err_json["error"])
                except Exception:
                    pass
                return {
                    "error": f"Image generation failed (Status {response.status_code}): {error_msg}"
                }

            data = response.json()

            # Extract image from response
            # Structure: choices[0].message.images[0].image_url.url
            images = []
            if "choices" in data and len(data["choices"]) > 0:
                message = data["choices"][0].get("message", {})
                images = message.get("images", [])

            if not images:
                return {"error": "No images returned by the model."}

            # Process the first image (tool currently supports one, could be expanded)
            image_obj = images[0]
            image_url_raw = image_obj.get("image_url", {}).get("url", "")

            if not image_url_raw:
                return {"error": "Image URL missing in response."}

            image_bytes = None

            # Handle Base64 Data URL
            if image_url_raw.startswith("data:"):
                # Format: data:image/png;base64,.....
                try:
                    header, encoded = image_url_raw.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                    # Determine extension from header (e.g., data:image/png)
                    ext = "png"
                    if "jpeg" in header or "jpg" in header:
                        ext = "jpg"
                    elif "webp" in header:
                        ext = "webp"
                except Exception as e:
                    return {"error": f"Failed to decode base64 image: {str(e)}"}
            else:
                # Handle standard URL (if model returns a link instead of base64)
                img_resp = await client.get(image_url_raw)
                if img_resp.status_code != 200:
                    return {"error": "Failed to download generated image from URL."}
                image_bytes = img_resp.content
                ext = "png"  # Default fallback

            # Save to disk
            filename = f"generated_{uuid.uuid4().hex}.{ext}"
            unique_filename = await save_file_to_disk(
                user_id=user_id,
                file_contents=image_bytes,
                original_filename=filename,
                subdirectory="generated_images",
            )

            # Create DB record
            root_folder = await get_root_folder_for_user(pg_engine, user_id)

            if not root_folder:
                return {"error": "Could not find root folder for user."}

            # Create DB Entry
            new_file = await create_db_file(
                pg_engine=pg_engine,
                user_id=user_id,
                parent_id=root_folder.id,
                name=(
                    f"Context: {prompt[:30]}..."
                    if source_image_ids
                    else f"Gen: {prompt[:30]}.{ext}"
                ),
                file_path=str(Path("generated_images") / unique_filename),
                size=len(image_bytes),
                content_type=f"image/{ext}",
                hash=hashlib.sha256(image_bytes).hexdigest(),
            )

            return {"success": True, "id": str(new_file.id), "prompt": prompt, "model": model}

    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return {"error": f"Internal error during generation: {str(e)}"}
