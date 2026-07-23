import asyncio
import base64
import io
import sys
from pathlib import Path

import httpx
import pytest
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

import services.alibaba_token_plan_media as media


def _image_data_uri(width: int = 512, height: int = 512) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"


class FakeDownloadResponse:
    def __init__(self, *, content: bytes, content_type: str, status_code: int = 200, headers=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type, **(headers or {})}
        self.content = content
        self.closed = False

    async def aiter_content(self):
        yield self.content

    async def aclose(self):
        self.closed = True


class FakeDownloadSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


def test_image_payload_maps_square_sizes_and_orders_references_before_text():
    payload = media.build_alibaba_image_payload(
        model="alibaba-token-plan/future-image",
        message_content=[
            {"type": "text", "text": "paint a lighthouse"},
            {"type": "image_url", "image_url": {"url": _image_data_uri()}},
        ],
        aspect_ratio="1:1",
        resolution="2K",
    )

    assert payload["model"] == "future-image"
    assert payload["parameters"] == {"size": "2048*2048", "n": 1}
    content = payload["input"]["messages"][0]["content"]
    assert list(content[0]) == ["image"]
    assert content[1] == {"text": "paint a lighthouse"}

    with pytest.raises(media.AlibabaTokenPlanMediaError, match="only 1K or 2K"):
        media.build_alibaba_image_payload(
            model="alibaba-token-plan/future-image",
            message_content="prompt",
            aspect_ratio="1:1",
            resolution="4K",
        )
    with pytest.raises(media.AlibabaTokenPlanMediaError, match="only 1:1"):
        media.build_alibaba_image_payload(
            model="alibaba-token-plan/future-image",
            message_content="prompt",
            aspect_ratio="16:9",
            resolution="1K",
        )


@pytest.mark.parametrize(
    ("model", "references", "ratio", "media_type"),
    [
        ("alibaba-token-plan/happyhorse-next-t2v", [], "16:9", None),
        (
            "alibaba-token-plan/happyhorse-next-i2v",
            [{"type": "image_url", "image_url": {"url": _image_data_uri()}}],
            "16:9",
            "first_frame",
        ),
        (
            "alibaba-token-plan/happyhorse-next-r2v",
            [{"type": "image_url", "image_url": {"url": _image_data_uri()}}],
            "1:1",
            "reference_image",
        ),
    ],
)
def test_video_payloads_follow_dynamic_operation(model, references, ratio, media_type):
    payload = media.build_alibaba_video_payload(
        model=model,
        prompt="move slowly",
        aspect_ratio=ratio,
        resolution="720p",
        duration=6,
        generate_audio=False,
        input_references=references,
    )

    assert payload["parameters"]["resolution"] == "720P"
    assert payload["parameters"]["duration"] == 6
    if media_type is None:
        assert "media" not in payload["input"]
    else:
        assert payload["input"]["media"][0]["type"] == media_type
    if "i2v" in model:
        assert "ratio" not in payload["parameters"]
    else:
        assert payload["parameters"]["ratio"] == ratio


@pytest.mark.parametrize(
    "url",
    [
        "http://bucket.aliyuncs.com/result.png",
        "https://bucket.aliyuncs.com:444/result.png",
        "https://127.0.0.1/result.png",
        "https://aliyuncs.com.evil.test/result.png",
        "https://user@bucket.aliyuncs.com/result.png",
        "https://bucket.aliyuncs.com/result.png#fragment",
    ],
)
def test_result_url_validation_fails_closed(url):
    with pytest.raises(media.AlibabaTokenPlanMediaError, match="not permitted"):
        media._validate_result_url(url)


def test_download_uses_manual_validated_redirect_and_no_sensitive_headers():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(buffer, format="PNG")
    first = FakeDownloadResponse(
        content=b"",
        content_type="text/plain",
        status_code=302,
        headers={"location": "/final.png?signature=secret"},
    )
    second = FakeDownloadResponse(content=buffer.getvalue(), content_type="image/png")
    session = FakeDownloadSession([first, second])

    data, extension = asyncio.run(
        media._download_result(
            "https://bucket.aliyuncs.com/start?signature=secret",
            expected_media="image",
            max_bytes=1024 * 1024,
            deadline_seconds=10,
            session_factory=lambda: session,
        )
    )

    assert data == buffer.getvalue()
    assert extension == "png"
    assert len(session.requests) == 2
    assert session.requests[1][0].startswith("https://bucket.aliyuncs.com/final.png")
    for _, kwargs in session.requests:
        assert kwargs["headers"] == {}
        assert kwargs["cookies"] == {}
        assert kwargs["proxy"] is None
        assert kwargs["allow_redirects"] is False
        assert kwargs["discard_cookies"] is True


def test_video_submits_once_polls_and_returns_opaque_task_id(monkeypatch):
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
    session = FakeDownloadSession([FakeDownloadResponse(content=mp4, content_type="video/mp4")])
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"output": {"task_id": "opaque_task-123"}})
        return httpx.Response(
            200,
            json={
                "output": {
                    "task_status": "SUCCEEDED",
                    "video_url": "https://bucket.aliyuncs.com/video.mp4?signed=secret",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        media.generate_alibaba_video(
            api_key="sk-sp-secret",
            model="alibaba-token-plan/happyhorse-future-t2v",
            prompt="move",
            aspect_ratio="16:9",
            resolution="720p",
            duration=None,
            generate_audio=False,
            input_references=[],
            http_client=client,
            download_session_factory=lambda: session,
        )
    )

    assert result.task_id == "opaque_task-123"
    assert result.video_bytes == mp4
    assert [request.method for request in requests].count("POST") == 1
    assert [request.method for request in requests].count("GET") == 1
    assert requests[1].url.path.endswith("/opaque_task-123")


def test_video_local_cancellation_happens_before_submission():
    calls = 0

    async def cancelled():
        return True

    async def run():
        nonlocal calls

        def handler(_request):
            nonlocal calls
            calls += 1
            return httpx.Response(500)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await media.generate_alibaba_video(
            api_key="sk-sp-secret",
            model="alibaba-token-plan/happyhorse-future-t2v",
            prompt="move",
            aspect_ratio="16:9",
            resolution="720p",
            duration=None,
            generate_audio=False,
            input_references=[],
            http_client=client,
            cancellation_callback=cancelled,
        )

    with pytest.raises(media.AlibabaMediaCancelled):
        asyncio.run(run())
    assert calls == 0


def test_invalid_task_id_is_rejected_without_polling():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(202, json={"output": {"task_id": "../unsafe"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(media.AlibabaTokenPlanMediaError, match="invalid task ID"):
        asyncio.run(
            media.generate_alibaba_video(
                api_key="sk-sp-secret",
                model="alibaba-token-plan/happyhorse-future-t2v",
                prompt="move",
                aspect_ratio="16:9",
                resolution="720p",
                duration=None,
                generate_audio=False,
                input_references=[],
                http_client=client,
            )
        )
    assert len(calls) == 1
