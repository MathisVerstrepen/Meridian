import base64
from dataclasses import dataclass
from typing import Any

import httpx
from models.inference import InferenceCredentials, InferenceProviderEnum
from services.inference import resolve_model_provider

OPENROUTER_IMAGE_GENERATION_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_HEADERS = {
    "Content-Type": "application/json",
    "HTTP-Referer": "https://meridian.diikstra.fr/",
    "X-Title": "Meridian",
}


class ImageGenerationProviderError(RuntimeError):
    pass


@dataclass
class GeneratedImageResult:
    image_bytes: bytes
    extension: str
    model: str


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "Unknown image generation error."

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)
        if error:
            return str(error)

    return response.text or "Unknown image generation error."


def _normalize_openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        **OPENROUTER_IMAGE_HEADERS,
        "Authorization": f"Bearer {api_key}",
    }


async def _generate_image_with_openrouter(
    *,
    credentials: InferenceCredentials,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
    source_image_ids: list[str],
    http_client: httpx.AsyncClient,
) -> GeneratedImageResult:
    if not credentials.openrouter_api_key:
        raise ImageGenerationProviderError("OpenRouter is not connected for image generation.")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": message_content}],
        "modalities": ["image", "text"],
    }
    if "gemini" in model.lower():
        payload["image_config"] = {"image_size": resolution}
        if not source_image_ids:
            payload["image_config"]["aspect_ratio"] = aspect_ratio

    response = await http_client.post(
        OPENROUTER_IMAGE_GENERATION_URL,
        headers=_normalize_openrouter_headers(credentials.openrouter_api_key),
        json=payload,
    )
    if response.status_code != 200:
        raise ImageGenerationProviderError(
            f"Image generation failed (status {response.status_code}): "
            f"{_extract_error_message(response)}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ImageGenerationProviderError(
            "Image generation service returned invalid JSON."
        ) from exc

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ImageGenerationProviderError("No image generation result returned by the model.")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    images = message.get("images", []) if isinstance(message, dict) else []
    if not isinstance(images, list) or not images:
        raise ImageGenerationProviderError("No images returned by the model.")

    image_obj = images[0] if isinstance(images[0], dict) else {}
    image_url = image_obj.get("image_url", {}).get("url", "") if isinstance(image_obj, dict) else ""
    if not isinstance(image_url, str) or not image_url:
        raise ImageGenerationProviderError("Image URL missing in response.")

    if image_url.startswith("data:"):
        try:
            header, encoded = image_url.split(",", 1)
            image_bytes = base64.b64decode(encoded)
        except Exception as exc:
            raise ImageGenerationProviderError(f"Failed to decode base64 image: {exc}") from exc

        extension = "png"
        if "jpeg" in header or "jpg" in header:
            extension = "jpg"
        elif "webp" in header:
            extension = "webp"
        return GeneratedImageResult(image_bytes=image_bytes, extension=extension, model=model)

    image_response = await http_client.get(image_url)
    if image_response.status_code != 200:
        raise ImageGenerationProviderError("Failed to download generated image from URL.")
    return GeneratedImageResult(image_bytes=image_response.content, extension="png", model=model)


async def generate_image_with_provider(
    *,
    credentials: InferenceCredentials,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
    source_image_ids: list[str],
    http_client: httpx.AsyncClient,
) -> GeneratedImageResult:
    provider = resolve_model_provider(model)
    if provider == InferenceProviderEnum.CLAUDE_AGENT:
        raise ImageGenerationProviderError(
            "Claude Agent models do not support image generation yet."
        )
    return await _generate_image_with_openrouter(
        credentials=credentials,
        model=model,
        message_content=message_content,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        source_image_ids=source_image_ids,
        http_client=http_client,
    )
