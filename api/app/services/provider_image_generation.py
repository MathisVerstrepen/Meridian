import asyncio
import base64
from dataclasses import dataclass
from typing import Any

import httpx
from models.inference import InferenceCredentials, InferenceProviderEnum
from services.inference import resolve_model_provider

OPENROUTER_IMAGE_GENERATION_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_VIDEO_GENERATION_URL = "https://openrouter.ai/api/v1/videos"
OPENROUTER_IMAGE_HEADERS = {
    "Content-Type": "application/json",
    "HTTP-Referer": "https://meridian.diikstra.fr/",
    "X-Title": "Meridian",
}


class ImageGenerationProviderError(RuntimeError):
    pass


class VideoGenerationProviderError(RuntimeError):
    pass


@dataclass
class GeneratedImageResult:
    image_bytes: bytes
    extension: str
    model: str


@dataclass
class GeneratedVideoResult:
    video_bytes: bytes
    extension: str
    model: str
    job_id: str


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


def _extract_video_extension(content_type: str | None, url: str) -> str:
    content_type = (content_type or "").lower()
    if "webm" in content_type:
        return "webm"
    if "quicktime" in content_type or "mov" in content_type:
        return "mov"
    if "mp4" in content_type or "mpeg" in content_type:
        return "mp4"

    clean_url = url.split("?", 1)[0].lower()
    for extension in ("webm", "mov", "mp4"):
        if clean_url.endswith(f".{extension}"):
            return extension
    return "mp4"


def _normalize_openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        **OPENROUTER_IMAGE_HEADERS,
        "Authorization": f"Bearer {api_key}",
    }


def _openrouter_video_download_headers(
    content_url: str, headers: dict[str, str]
) -> dict[str, str] | None:
    if content_url.startswith("https://openrouter.ai/api/"):
        return headers
    return None


def _build_openrouter_image_modalities(output_modalities: list[str] | None) -> list[str]:
    normalized_modalities = [
        modality.lower() for modality in output_modalities or [] if isinstance(modality, str)
    ]
    if "image" in normalized_modalities and "text" in normalized_modalities:
        return ["image", "text"]
    return ["image"]


async def _generate_image_with_openrouter(
    *,
    credentials: InferenceCredentials,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
    source_image_ids: list[str],
    output_modalities: list[str] | None,
    http_client: httpx.AsyncClient,
) -> GeneratedImageResult:
    if not credentials.openrouter_api_key:
        raise ImageGenerationProviderError("OpenRouter is not connected for image generation.")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": message_content}],
        "modalities": _build_openrouter_image_modalities(output_modalities),
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


async def _generate_video_with_openrouter(
    *,
    credentials: InferenceCredentials,
    model: str,
    prompt: str,
    aspect_ratio: str | None,
    resolution: str | None,
    duration: int | None,
    input_references: list[dict[str, Any]],
    http_client: httpx.AsyncClient,
) -> GeneratedVideoResult:
    if not credentials.openrouter_api_key:
        raise VideoGenerationProviderError("OpenRouter is not connected for video generation.")

    payload: dict[str, Any] = {"model": model, "prompt": prompt}
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if resolution:
        payload["resolution"] = resolution
    if duration is not None:
        payload["duration"] = duration
    if input_references:
        payload["input_references"] = input_references

    headers = _normalize_openrouter_headers(credentials.openrouter_api_key)
    response = await http_client.post(
        OPENROUTER_VIDEO_GENERATION_URL,
        headers=headers,
        json=payload,
    )
    if response.status_code not in (200, 202):
        raise VideoGenerationProviderError(
            f"Video generation failed (status {response.status_code}): "
            f"{_extract_error_message(response)}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise VideoGenerationProviderError(
            "Video generation service returned invalid JSON."
        ) from exc

    job_id = str(data.get("id") or "")
    polling_url = str(data.get("polling_url") or "")
    if not job_id or not polling_url:
        raise VideoGenerationProviderError(
            "Video generation job response was missing polling data."
        )

    status_payload = data
    for _ in range(20):
        status = str(status_payload.get("status") or "").lower()
        if status == "completed":
            unsigned_urls = status_payload.get("unsigned_urls")
            if not isinstance(unsigned_urls, list) or not unsigned_urls:
                raise VideoGenerationProviderError(
                    "Video generation completed without a video URL."
                )
            content_url = unsigned_urls[0]
            if not isinstance(content_url, str) or not content_url:
                raise VideoGenerationProviderError("Video URL missing in response.")

            video_response = await http_client.get(
                content_url,
                headers=_openrouter_video_download_headers(content_url, headers),
                follow_redirects=True,
            )
            if video_response.status_code != 200:
                raise VideoGenerationProviderError(
                    f"Failed to download generated video from URL "
                    f"(status {video_response.status_code}): "
                    f"{_extract_error_message(video_response)}"
                )
            extension = _extract_video_extension(
                video_response.headers.get("content-type"),
                content_url,
            )
            return GeneratedVideoResult(
                video_bytes=video_response.content,
                extension=extension,
                model=model,
                job_id=job_id,
            )
        if status == "failed":
            error = status_payload.get("error") or "Unknown video generation error."
            raise VideoGenerationProviderError(f"Video generation failed: {error}")

        await asyncio.sleep(30)
        poll_response = await http_client.get(polling_url, headers=headers)
        if poll_response.status_code != 200:
            raise VideoGenerationProviderError(
                f"Video generation polling failed (status {poll_response.status_code}): "
                f"{_extract_error_message(poll_response)}"
            )
        try:
            status_payload = poll_response.json()
        except ValueError as exc:
            raise VideoGenerationProviderError(
                "Video generation polling returned invalid JSON."
            ) from exc

    raise VideoGenerationProviderError("Video generation timed out while waiting for completion.")


async def generate_image_with_provider(
    *,
    credentials: InferenceCredentials,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
    source_image_ids: list[str],
    http_client: httpx.AsyncClient,
    output_modalities: list[str] | None = None,
) -> GeneratedImageResult:
    provider = resolve_model_provider(model)
    if provider == InferenceProviderEnum.CLAUDE_AGENT:
        raise ImageGenerationProviderError(
            "Claude Agent models do not support image generation yet."
        )
    if provider == InferenceProviderEnum.GITHUB_COPILOT:
        raise ImageGenerationProviderError(
            "GitHub Copilot models do not support direct image generation."
        )
    if provider == InferenceProviderEnum.Z_AI_CODING_PLAN:
        raise ImageGenerationProviderError(
            "Z.AI Coding Plan models do not support direct image generation."
        )
    if provider == InferenceProviderEnum.GEMINI_CLI:
        raise ImageGenerationProviderError(
            "Gemini CLI models do not support direct image generation."
        )
    if provider == InferenceProviderEnum.OPENAI_CODEX:
        if not credentials.openai_codex_auth_json:
            raise ImageGenerationProviderError(
                "OpenAI Codex is not connected for image generation."
            )
        from services.openai_codex import generate_image_with_openai_codex

        try:
            generated_image = await generate_image_with_openai_codex(
                auth_json=credentials.openai_codex_auth_json,
                model=model,
                message_content=message_content,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                http_client=http_client,
            )
        except Exception as exc:
            raise ImageGenerationProviderError(str(exc)) from exc
        return GeneratedImageResult(
            image_bytes=generated_image.image_bytes,
            extension=generated_image.extension,
            model=generated_image.model,
        )
    return await _generate_image_with_openrouter(
        credentials=credentials,
        model=model,
        message_content=message_content,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        source_image_ids=source_image_ids,
        output_modalities=output_modalities,
        http_client=http_client,
    )


async def generate_video_with_provider(
    *,
    credentials: InferenceCredentials,
    model: str,
    prompt: str,
    aspect_ratio: str | None,
    resolution: str | None,
    duration: int | None,
    input_references: list[dict[str, Any]],
    http_client: httpx.AsyncClient,
) -> GeneratedVideoResult:
    provider = resolve_model_provider(model)
    if provider != InferenceProviderEnum.OPENROUTER:
        raise VideoGenerationProviderError(
            "Only OpenRouter models support video generation currently."
        )

    return await _generate_video_with_openrouter(
        credentials=credentials,
        model=model,
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        input_references=input_references,
        http_client=http_client,
    )
