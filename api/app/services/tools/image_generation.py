import base64
import hashlib
import logging
import uuid
from pathlib import Path

import httpx
from database.pg.file_ops.file_crud import create_db_file, get_root_folder_for_user
from services.files import calculate_file_hash, save_file_to_disk
from services.settings import get_user_settings
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

IMAGE_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "Generate an image based on a text prompt. Use this tool when the user asks to draw, create, or generate an image.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A detailed description of the image to generate.",
                },
                "model": {
                    "type": "string",
                    "description": "The model to use for generation. Optional, defaults to user settings.",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "4:3", "3:4", "9:16"],
                    "description": "The aspect ratio of the image. Default is 1:1.",
                },
            },
            "required": ["prompt"],
        },
    },
}


async def generate_image(arguments: dict, req) -> dict:
    """
    Generates an image using the OpenRouter chat/completions endpoint with image modalities.
    """
    user_id = uuid.UUID(req.user_id)
    pg_engine: SQLAlchemyAsyncEngine = req.pg_engine

    # Get settings
    settings = await get_user_settings(pg_engine, req.user_id)

    prompt = arguments.get("prompt")
    # Default to a known working image model if none provided
    model = (
        arguments.get("model")
        or settings.toolsImageGeneration.defaultModel
        or "google/gemini-2.5-flash-image-preview"
    )
    aspect_ratio = arguments.get("aspect_ratio", "1:1")

    if not prompt:
        return {"error": "Prompt is required for image generation."}

    # URL for Chat Completions (as per new docs)
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {req.headers['Authorization'].replace('Bearer ', '')}",
        "Content-Type": "application/json",
        "HTTP-Referer": req.headers.get("HTTP-Referer", "https://meridian.diikstra.fr/"),
        "X-Title": req.headers.get("X-Title", "Meridian"),
    }

    # Payload structure for Image Generation via Chat
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }

    # Add image config for supported models (like Gemini)
    if "gemini" in model.lower():
        payload["image_config"] = {"aspect_ratio": aspect_ratio}

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
                except:
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
                name=f"Gen: {prompt[:30]}...",
                file_path=str(Path("generated_images") / unique_filename),
                size=len(image_bytes),
                content_type=f"image/{ext}",
                hash=hashlib.sha256(image_bytes).hexdigest(),
            )

            # Return local URL
            local_url = f"/api/files/view/{new_file.id}"

            return {"success": True, "url": local_url, "prompt": prompt, "model": model}

    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return {"error": f"Internal error during generation: {str(e)}"}
