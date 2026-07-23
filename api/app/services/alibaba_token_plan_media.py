import asyncio
import base64
import binascii
import io
import re
import time
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from curl_cffi.requests import AsyncSession as CurlAsyncSession
from PIL import Image, UnidentifiedImageError
from services.providers.alibaba_token_plan_catalog import (
    ALIBABA_TOKEN_PLAN_MODEL_PREFIX,
    classify_happyhorse_operation,
)

ALIBABA_IMAGE_GENERATION_URL = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/"
    "multimodal-generation/generation"
)
ALIBABA_VIDEO_GENERATION_URL = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/"
    "video-generation/video-synthesis"
)
ALIBABA_TASK_URL_PREFIX = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/api/v1/tasks/"

IMAGE_SIZE_MAP = {"1K": "1024*1024", "2K": "2048*2048"}
VIDEO_RATIOS = frozenset({"16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "9:21"})
IMAGE_REFERENCE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_REFERENCE_TOTAL_MAX_BYTES = 30 * 1024 * 1024
VIDEO_REFERENCE_MAX_BYTES = 20 * 1024 * 1024
VIDEO_REFERENCE_TOTAL_MAX_BYTES = 64 * 1024 * 1024
IMAGE_DOWNLOAD_MAX_BYTES = 64 * 1024 * 1024
VIDEO_DOWNLOAD_MAX_BYTES = 256 * 1024 * 1024
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SECRET_RE = re.compile(r"sk-sp-[A-Za-z0-9_-]+", re.IGNORECASE)
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class AlibabaTokenPlanMediaError(RuntimeError):
    """A bounded, sanitized native media error."""


class AlibabaMediaCancelled(AlibabaTokenPlanMediaError):
    """Local cancellation observed; no provider cancellation is implied."""


@dataclass
class AlibabaImageResult:
    image_bytes: bytes
    extension: str
    model: str


@dataclass
class AlibabaVideoResult:
    video_bytes: bytes
    extension: str
    model: str
    task_id: str


@dataclass
class _DecodedImage:
    data_uri: str
    byte_count: int
    width: int
    height: int
    extension: str


def _raw_model_id(model: str) -> str:
    if not model.startswith(ALIBABA_TOKEN_PLAN_MODEL_PREFIX):
        raise AlibabaTokenPlanMediaError("Invalid Alibaba Token Plan model identifier.")
    raw_model = model[len(ALIBABA_TOKEN_PLAN_MODEL_PREFIX) :]
    if not raw_model:
        raise AlibabaTokenPlanMediaError("Invalid Alibaba Token Plan model identifier.")
    return raw_model


def _sanitize_provider_error(payload: Any) -> str:
    code = ""
    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        sources = [error, payload.get("output"), payload]
        for source in sources:
            if not isinstance(source, dict):
                continue
            if not code and source.get("code") is not None:
                code = str(source["code"])
            if not message and source.get("message") is not None:
                message = str(source["message"])
    clean_message = " ".join(message.split())
    clean_code = " ".join(code.split())
    clean = clean_message
    if clean_code:
        clean = f"{clean} ({clean_code})" if clean else clean_code
    clean = _SECRET_RE.sub("[REDACTED]", clean)
    return clean[:500] or "The provider rejected the media request."


def _parse_data_uri(value: Any, *, max_bytes: int) -> _DecodedImage:
    if not isinstance(value, str) or not value.startswith("data:image/") or "," not in value:
        raise AlibabaTokenPlanMediaError("References must be local image data URIs.")
    header, encoded = value.split(",", 1)
    if not header.endswith(";base64"):
        raise AlibabaTokenPlanMediaError("References must use base64 image data URIs.")
    mime = header[5:-7].lower()
    mime_to_extension = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    expected_extension = mime_to_extension.get(mime)
    if expected_extension is None:
        raise AlibabaTokenPlanMediaError("Reference image type must be JPEG, PNG, or WEBP.")
    estimated_size = (len(encoded) * 3) // 4
    if estimated_size > max_bytes + 2:
        raise AlibabaTokenPlanMediaError("Reference image exceeds the size limit.")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AlibabaTokenPlanMediaError("Reference image data is invalid.") from exc
    if not image_bytes or len(image_bytes) > max_bytes:
        raise AlibabaTokenPlanMediaError("Reference image exceeds the size limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.verify()
            with Image.open(io.BytesIO(image_bytes)) as image:
                width, height = image.size
                actual_extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(
                    str(image.format).upper()
                )
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise AlibabaTokenPlanMediaError("Reference image data is invalid.") from exc
    if actual_extension != expected_extension:
        raise AlibabaTokenPlanMediaError("Reference image MIME type does not match its bytes.")
    return _DecodedImage(value, len(image_bytes), width, height, actual_extension)


def _image_url_from_part(part: Any) -> str:
    if not isinstance(part, dict) or part.get("type") != "image_url":
        raise AlibabaTokenPlanMediaError("Alibaba image content contains an unsupported part.")
    image_url = part.get("image_url")
    if not isinstance(image_url, dict) or not isinstance(image_url.get("url"), str):
        raise AlibabaTokenPlanMediaError("Alibaba image reference is malformed.")
    url = image_url["url"]
    return str(url)


def build_alibaba_image_payload(
    *,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
) -> dict[str, Any]:
    raw_model = _raw_model_id(model)
    if aspect_ratio != "1:1":
        raise AlibabaTokenPlanMediaError("Alibaba image generation supports only 1:1 output.")
    native_size = IMAGE_SIZE_MAP.get(resolution)
    if native_size is None:
        raise AlibabaTokenPlanMediaError("Alibaba image generation supports only 1K or 2K.")
    prompt = ""
    reference_urls: list[str] = []
    if isinstance(message_content, str):
        prompt = message_content.strip()
    elif isinstance(message_content, list):
        for part in message_content:
            if isinstance(part, dict) and part.get("type") == "text":
                if prompt or not isinstance(part.get("text"), str):
                    raise AlibabaTokenPlanMediaError(
                        "Alibaba image generation requires exactly one text prompt."
                    )
                prompt = part["text"].strip()
            else:
                reference_urls.append(_image_url_from_part(part))
    else:
        raise AlibabaTokenPlanMediaError("Alibaba image content is malformed.")
    if not prompt:
        raise AlibabaTokenPlanMediaError("A nonempty image prompt is required.")
    if len(reference_urls) > 3:
        raise AlibabaTokenPlanMediaError("Alibaba image generation accepts at most 3 references.")
    decoded_references = [
        _parse_data_uri(url, max_bytes=IMAGE_REFERENCE_MAX_BYTES) for url in reference_urls
    ]
    if sum(item.byte_count for item in decoded_references) > IMAGE_REFERENCE_TOTAL_MAX_BYTES:
        raise AlibabaTokenPlanMediaError("Image references exceed the cumulative size limit.")
    for item in decoded_references:
        ratio = item.width / item.height
        if not (384 <= item.width <= 3072 and 384 <= item.height <= 3072):
            raise AlibabaTokenPlanMediaError(
                "Alibaba image references must be between 384 and 3072 pixels per side."
            )
        if not 1 / 8 <= ratio <= 8:
            raise AlibabaTokenPlanMediaError("Alibaba image reference aspect ratio is unsupported.")
    content = [{"image": item.data_uri} for item in decoded_references]
    content.append({"text": prompt})
    return {
        "model": raw_model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": {"size": native_size, "n": 1},
    }


def _video_reference_urls(input_references: list[dict[str, Any]]) -> list[str]:
    return [_image_url_from_part(part) for part in input_references]


def build_alibaba_video_payload(
    *,
    model: str,
    prompt: str,
    aspect_ratio: str | None,
    resolution: str | None,
    duration: int | None,
    generate_audio: bool,
    input_references: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_model = _raw_model_id(model)
    operation = classify_happyhorse_operation(raw_model)
    if operation is None:
        raise AlibabaTokenPlanMediaError(
            "Alibaba video generation requires an unambiguous HappyHorse t2v, i2v, or r2v model."
        )
    if not isinstance(prompt, str) or not prompt.strip():
        raise AlibabaTokenPlanMediaError("A nonempty video prompt is required.")
    if resolution not in {"720p", "1080p"}:
        raise AlibabaTokenPlanMediaError("HappyHorse resolution must be 720p or 1080p.")
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, int) or not 3 <= duration <= 15
    ):
        raise AlibabaTokenPlanMediaError("HappyHorse duration must be between 3 and 15 seconds.")
    if generate_audio:
        raise AlibabaTokenPlanMediaError(
            "HappyHorse manages audio automatically and does not expose an audio switch."
        )
    reference_urls = _video_reference_urls(input_references)
    if operation == "t2v" and reference_urls:
        raise AlibabaTokenPlanMediaError("HappyHorse t2v does not accept image references.")
    if operation == "i2v" and len(reference_urls) != 1:
        raise AlibabaTokenPlanMediaError("HappyHorse i2v requires exactly one first-frame image.")
    if operation == "r2v" and not 1 <= len(reference_urls) <= 8:
        raise AlibabaTokenPlanMediaError("HappyHorse r2v requires between 1 and 8 references.")
    if operation != "i2v" and aspect_ratio not in VIDEO_RATIOS:
        raise AlibabaTokenPlanMediaError("HappyHorse aspect ratio is unsupported.")
    decoded_references = [
        _parse_data_uri(url, max_bytes=VIDEO_REFERENCE_MAX_BYTES) for url in reference_urls
    ]
    if sum(item.byte_count for item in decoded_references) > VIDEO_REFERENCE_TOTAL_MAX_BYTES:
        raise AlibabaTokenPlanMediaError("Video references exceed the cumulative size limit.")
    if operation == "i2v":
        reference = decoded_references[0]
        if min(reference.width, reference.height) < 300:
            raise AlibabaTokenPlanMediaError("HappyHorse i2v references must be at least 300x300.")
        if not 1 / 2.5 <= reference.width / reference.height <= 2.5:
            raise AlibabaTokenPlanMediaError(
                "HappyHorse i2v reference aspect ratio is unsupported."
            )
    if operation == "r2v" and any(
        min(reference.width, reference.height) < 400 for reference in decoded_references
    ):
        raise AlibabaTokenPlanMediaError(
            "HappyHorse r2v references must have a shortest side of at least 400 pixels."
        )
    input_payload: dict[str, Any] = {"prompt": prompt.strip()}
    if decoded_references:
        media_type = "first_frame" if operation == "i2v" else "reference_image"
        input_payload["media"] = [
            {"type": media_type, "url": reference.data_uri} for reference in decoded_references
        ]
    parameters: dict[str, Any] = {"resolution": resolution.upper()}
    if operation != "i2v":
        parameters["ratio"] = aspect_ratio
    if duration is not None:
        parameters["duration"] = duration
    return {"model": raw_model, "input": input_payload, "parameters": parameters}


def _validate_result_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise AlibabaTokenPlanMediaError("Provider result URL is not permitted.") from exc
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (port is not None and port != 443)
        or re.fullmatch(r"[0-9.]+", hostname)
        or ":" in hostname
        or not (hostname == "aliyuncs.com" or hostname.endswith(".aliyuncs.com"))
    ):
        raise AlibabaTokenPlanMediaError("Provider result URL is not permitted.")


def _new_download_session() -> CurlAsyncSession:
    return CurlAsyncSession(
        trust_env=False,
        headers={},
        cookies={},
        default_headers=False,
        allow_redirects=False,
        retry=0,
        discard_cookies=True,
    )


async def _download_result(
    url: str,
    *,
    expected_media: str,
    max_bytes: int,
    deadline_seconds: float,
    session_factory: Callable[[], Any] | None = None,
) -> tuple[bytes, str]:
    current_url = url
    deadline = time.monotonic() + deadline_seconds
    factory = session_factory or _new_download_session
    try:
        async with factory() as session:
            for redirect_count in range(4):
                _validate_result_url(current_url)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AlibabaTokenPlanMediaError("Provider result download timed out.")
                response = await session.get(
                    current_url,
                    headers={},
                    cookies={},
                    proxy=None,
                    timeout=(10.0, min(remaining, deadline_seconds)),
                    allow_redirects=False,
                    stream=True,
                    discard_cookies=True,
                )
                try:
                    status_code = int(response.status_code)
                    if status_code in _REDIRECT_STATUSES:
                        if redirect_count >= 3:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result exceeded the redirect limit."
                            )
                        location = response.headers.get("location")
                        if not isinstance(location, str) or not location:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result redirect was invalid."
                            )
                        current_url = urljoin(current_url, location)
                        _validate_result_url(current_url)
                        continue
                    if status_code != 200:
                        raise AlibabaTokenPlanMediaError("Provider result download failed.")
                    content_type = (
                        str(response.headers.get("content-type") or "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    allowed_types = (
                        {"image/jpeg", "image/jpg", "image/png", "image/webp"}
                        if expected_media == "image"
                        else {"video/mp4"}
                    )
                    if content_type not in allowed_types:
                        raise AlibabaTokenPlanMediaError(
                            "Provider result returned an unsupported content type."
                        )
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_length = int(content_length)
                        except ValueError as exc:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result returned an invalid content length."
                            ) from exc
                        if declared_length < 0 or declared_length > max_bytes:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result exceeded the download size limit."
                            )
                    content = bytearray()
                    async for chunk in response.aiter_content():
                        if time.monotonic() >= deadline:
                            raise AlibabaTokenPlanMediaError("Provider result download timed out.")
                        content.extend(chunk)
                        if len(content) > max_bytes:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result exceeded the download size limit."
                            )
                    if not content:
                        raise AlibabaTokenPlanMediaError("Provider result download was empty.")
                    data = bytes(content)
                    if expected_media == "image":
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter("error", Image.DecompressionBombWarning)
                                with Image.open(io.BytesIO(data)) as image:
                                    image.verify()
                                    extension = {
                                        "JPEG": "jpg",
                                        "PNG": "png",
                                        "WEBP": "webp",
                                    }.get(str(image.format).upper())
                        except (
                            UnidentifiedImageError,
                            OSError,
                            Image.DecompressionBombError,
                            Image.DecompressionBombWarning,
                        ) as exc:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result was not a valid image."
                            ) from exc
                        if extension is None:
                            raise AlibabaTokenPlanMediaError(
                                "Provider result was not a supported image."
                            )
                        return data, extension
                    if len(data) < 12 or data[4:8] != b"ftyp":
                        raise AlibabaTokenPlanMediaError(
                            "Provider result was not a valid MP4 container."
                        )
                    return data, "mp4"
                finally:
                    await response.aclose()
    except asyncio.CancelledError:
        raise
    except AlibabaTokenPlanMediaError:
        raise
    except Exception:
        raise AlibabaTokenPlanMediaError("Provider result download failed.") from None
    raise AlibabaTokenPlanMediaError("Provider result download failed.")


def _first_image_url(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise AlibabaTokenPlanMediaError("Image generation returned an invalid response.")
    output = payload.get("output")
    choices = output.get("choices") if isinstance(output, dict) else None
    if not isinstance(choices, list):
        raise AlibabaTokenPlanMediaError("Image generation returned no image result.")
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for part in content:
            image_url = part.get("image") if isinstance(part, dict) else None
            if isinstance(image_url, str) and image_url.startswith("https://"):
                return image_url
    raise AlibabaTokenPlanMediaError("Image generation returned no image result.")


async def generate_alibaba_image(
    *,
    api_key: str,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
    http_client: httpx.AsyncClient,
    download_session_factory: Callable[[], Any] | None = None,
) -> AlibabaImageResult:
    payload = build_alibaba_image_payload(
        model=model,
        message_content=message_content,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
    )
    try:
        response = await http_client.post(
            ALIBABA_IMAGE_GENERATION_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=httpx.Timeout(300.0, connect=10.0, read=300.0),
        )
    except asyncio.CancelledError:
        raise
    except httpx.HTTPError as exc:
        raise AlibabaTokenPlanMediaError("Alibaba image generation request failed.") from exc
    if response.status_code != 200:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = None
        raise AlibabaTokenPlanMediaError(
            f"Alibaba image generation failed (status {response.status_code}): "
            f"{_sanitize_provider_error(error_payload)}"
        )
    try:
        response_payload = response.json()
    except ValueError as exc:
        raise AlibabaTokenPlanMediaError("Image generation returned invalid JSON.") from exc
    image_url = _first_image_url(response_payload)
    image_bytes, extension = await _download_result(
        image_url,
        expected_media="image",
        max_bytes=IMAGE_DOWNLOAD_MAX_BYTES,
        deadline_seconds=120.0,
        session_factory=download_session_factory,
    )
    return AlibabaImageResult(image_bytes, extension, model)


async def _check_cancelled(
    cancellation_callback: Callable[[], Awaitable[bool]] | None,
) -> None:
    if cancellation_callback is not None and await cancellation_callback():
        raise AlibabaMediaCancelled("Alibaba media generation was cancelled locally.")


async def generate_alibaba_video(
    *,
    api_key: str,
    model: str,
    prompt: str,
    aspect_ratio: str | None,
    resolution: str | None,
    duration: int | None,
    generate_audio: bool,
    input_references: list[dict[str, Any]],
    http_client: httpx.AsyncClient,
    cancellation_callback: Callable[[], Awaitable[bool]] | None = None,
    download_session_factory: Callable[[], Any] | None = None,
) -> AlibabaVideoResult:
    payload = build_alibaba_video_payload(
        model=model,
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        generate_audio=generate_audio,
        input_references=input_references,
    )
    await _check_cancelled(cancellation_callback)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    try:
        response = await http_client.post(
            ALIBABA_VIDEO_GENERATION_URL,
            headers=headers,
            json=payload,
            timeout=httpx.Timeout(120.0, connect=10.0, read=120.0, write=120.0),
        )
    except asyncio.CancelledError:
        raise
    except httpx.HTTPError as exc:
        raise AlibabaTokenPlanMediaError("Alibaba video submission failed.") from exc
    if response.status_code not in {200, 202}:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = None
        raise AlibabaTokenPlanMediaError(
            f"Alibaba video submission failed (status {response.status_code}): "
            f"{_sanitize_provider_error(error_payload)}"
        )
    try:
        submission_payload = response.json()
    except ValueError as exc:
        raise AlibabaTokenPlanMediaError("Alibaba video submission returned invalid JSON.") from exc
    output = submission_payload.get("output") if isinstance(submission_payload, dict) else None
    task_id = str(output.get("task_id") or "").strip() if isinstance(output, dict) else ""
    if not _TASK_ID_RE.fullmatch(task_id):
        raise AlibabaTokenPlanMediaError("Alibaba video submission returned an invalid task ID.")

    deadline = time.monotonic() + 600.0
    consecutive_failures = 0
    while time.monotonic() < deadline:
        await _check_cancelled(cancellation_callback)
        try:
            poll_response = await http_client.get(
                f"{ALIBABA_TASK_URL_PREFIX}{task_id}",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                timeout=httpx.Timeout(60.0, connect=10.0, read=60.0),
            )
        except asyncio.CancelledError:
            raise
        except (httpx.ConnectError, httpx.TimeoutException):
            consecutive_failures += 1
            if consecutive_failures >= 3:
                raise AlibabaTokenPlanMediaError("Alibaba video polling repeatedly failed.")
        else:
            if poll_response.status_code == 429 or poll_response.status_code >= 500:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    raise AlibabaTokenPlanMediaError("Alibaba video polling repeatedly failed.")
            elif poll_response.status_code != 200:
                raise AlibabaTokenPlanMediaError(
                    f"Alibaba video polling failed (status {poll_response.status_code})."
                )
            else:
                consecutive_failures = 0
                try:
                    poll_payload = poll_response.json()
                except ValueError as exc:
                    raise AlibabaTokenPlanMediaError(
                        "Alibaba video polling returned invalid JSON."
                    ) from exc
                poll_output = poll_payload.get("output") if isinstance(poll_payload, dict) else None
                status = (
                    str(poll_output.get("task_status") or "").strip().upper()
                    if isinstance(poll_output, dict)
                    else ""
                )
                if status == "SUCCEEDED":
                    if not isinstance(poll_output, dict):
                        raise AlibabaTokenPlanMediaError(
                            "Alibaba video polling returned an invalid response."
                        )
                    video_url = poll_output.get("video_url")
                    if not isinstance(video_url, str) or not video_url:
                        raise AlibabaTokenPlanMediaError(
                            "Alibaba video completed without a result URL."
                        )
                    await _check_cancelled(cancellation_callback)
                    video_bytes, extension = await _download_result(
                        video_url,
                        expected_media="video",
                        max_bytes=VIDEO_DOWNLOAD_MAX_BYTES,
                        deadline_seconds=300.0,
                        session_factory=download_session_factory,
                    )
                    return AlibabaVideoResult(video_bytes, extension, model, task_id)
                if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                    raise AlibabaTokenPlanMediaError(
                        f"Alibaba video generation ended with status {status}: "
                        f"{_sanitize_provider_error(poll_output)}"
                    )
                if status not in {"PENDING", "RUNNING"}:
                    raise AlibabaTokenPlanMediaError(
                        "Alibaba video polling returned an unknown status."
                    )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(15.0, remaining))
        await _check_cancelled(cancellation_callback)
    raise AlibabaTokenPlanMediaError("Alibaba video generation timed out.")
