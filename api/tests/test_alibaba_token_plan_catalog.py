import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

import services.inference as inference
import services.providers.alibaba_token_plan_official_catalog as official_catalog
from models.inference import Architecture, ModelInfo, Pricing, ResponseModel
from services.inference import get_alibaba_token_plan_models_safe
from services.model_catalog import encode_model_catalog
from services.providers.alibaba_token_plan_catalog import (
    ALIBABA_TOKEN_PLAN_PROVIDER_KEY,
    build_alibaba_token_plan_models_from_models_dev,
)
from services.providers.alibaba_token_plan_official_catalog import (
    ALIBABA_TOKEN_PLAN_OFFICIAL_OVERVIEW_URL,
    AlibabaTokenPlanOfficialCatalogError,
    fetch_alibaba_token_plan_official_video_model_ids,
    parse_alibaba_token_plan_official_video_model_ids,
)


def _official_html(*rows: str) -> bytes:
    return (
        "<html><table><tr><th>Brand</th><th>Model ID</th><th>Capability</th></tr>"
        + "".join(rows)
        + "</table></html>"
    ).encode()


def _model(model_id: str) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        name=model_id,
        architecture=Architecture(
            input_modalities=["text"],
            modality="text->video",
            output_modalities=["video"],
            tokenizer="unknown",
        ),
        pricing=Pricing(prompt="0", completion="0"),
    )


def test_alibaba_token_plan_official_parser_handles_current_rowspan_table():
    html = b"""
        <table>
          <tr><td><b>Brand</b></td><td><p>Model ID</p></td><td>Capability</td></tr>
          <tr><td rowspan="2">HappyHorse</td><td><p>happyhorse-next-t2v</p></td>
              <td><span>Video generation</span></td></tr>
          <tr><td>happyhorse-next-i2v</td><td> Video\n generation </td></tr>
          <tr><td>Qwen</td><td>qwen-image</td><td>Image generation</td></tr>
        </table>
    """

    assert parse_alibaba_token_plan_official_video_model_ids(html) == [
        "happyhorse-next-t2v",
        "happyhorse-next-i2v",
    ]


def test_alibaba_token_plan_official_parser_uses_exact_semantic_rows_only():
    html = b"""
        <p>happyhorse-prose-t2v Video generation</p>
        <table><tr><th>Model ID</th><th>Other</th></tr>
          <tr><td>happyhorse-wrong-t2v</td><td>Video generation</td></tr></table>
        <table><thead><tr><th> Brand </th><th><b> MODEL   ID </b></th>
          <th> Capability </th></tr></thead><tbody>
          <tr><td>A</td><td>happyhorse-semantic-r2v</td><td>VIDEO GENERATION</td></tr>
          <tr><td>A</td><td>happyhorse-semantic-r2v</td><td>video generation</td></tr>
          <tr><td>A</td><td>happyhorse-mixed-t2v</td><td>Video generation, image</td></tr>
          <tr><td>A</td><td>unknown-video</td><td>Video generation</td></tr>
          <tr><td colspan="3"><table><tr><td>nested-id</td>
            <td>Video generation</td></tr></table></td></tr>
        </tbody></table>
        <script>"<table><tr><th>Model ID</th><th>Capability</th></tr></table>"</script>
    """

    assert parse_alibaba_token_plan_official_video_model_ids(html) == [
        "happyhorse-semantic-r2v",
        "unknown-video",
    ]


@pytest.mark.parametrize(
    "html",
    [
        b"not utf-8: \xff",
        b"<table><tr><th>Model</th><th>Capability</th></tr></table>",
    ],
)
def test_alibaba_token_plan_official_parser_rejects_malformed_pages(html: bytes):
    with pytest.raises(AlibabaTokenPlanOfficialCatalogError) as exc_info:
        parse_alibaba_token_plan_official_video_model_ids(html)
    assert "\xff" not in str(exc_info.value)


def test_alibaba_token_plan_official_parser_enforces_bounds_and_omits_invalid_ids(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(official_catalog, "MAX_OFFICIAL_CATALOG_ROWS", 2)
    oversized_rows = _official_html(
        "<tr><td>A</td><td>one</td><td>text</td></tr>",
        "<tr><td>A</td><td>two</td><td>image</td></tr>",
        "<tr><td>A</td><td>three</td><td>audio</td></tr>",
    )
    with pytest.raises(AlibabaTokenPlanOfficialCatalogError, match="too many"):
        parse_alibaba_token_plan_official_video_model_ids(oversized_rows)

    monkeypatch.setattr(official_catalog, "MAX_OFFICIAL_CATALOG_ROWS", 5_000)
    html = _official_html(
        "<tr><td>A</td><td>happyhorse good t2v</td><td>Video generation</td></tr>",
        "<tr><td>A</td><td>happyhorse-good-t2v</td><td>Video generation</td></tr>",
        f"<tr><td>A</td><td>{'x' * 237}</td><td>Video generation</td></tr>",
    )
    assert parse_alibaba_token_plan_official_video_model_ids(html) == ["happyhorse-good-t2v"]

    with pytest.raises(AlibabaTokenPlanOfficialCatalogError, match="size limit"):
        parse_alibaba_token_plan_official_video_model_ids(
            b"x" * (official_catalog.MAX_OFFICIAL_CATALOG_BYTES + 1)
        )


def test_alibaba_token_plan_official_fetch_is_fixed_bounded_and_credential_free():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=_official_html(
                "<tr><td>A</td><td>happyhorse-fetched-t2v</td>" "<td>Video generation</td></tr>"
            ),
            request=request,
        )

    async def run() -> list[str]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer sentinel", "X-API-Key": "sentinel"},
            cookies={"session": "sentinel"},
            auth=("sentinel-user", "sentinel-password"),
        ) as client:
            return await fetch_alibaba_token_plan_official_video_model_ids(client)

    assert asyncio.run(run()) == ["happyhorse-fetched-t2v"]
    assert len(captured) == 1
    request = captured[0]
    assert str(request.url) == ALIBABA_TOKEN_PLAN_OFFICIAL_OVERVIEW_URL
    sensitive_headers = {"authorization", "cookie", "x-api-key"}
    assert sensitive_headers.isdisjoint(request.headers)
    assert request.url.query == b""


@pytest.mark.parametrize(
    ("status", "headers"),
    [
        (302, {"content-type": "text/html"}),
        (200, {"content-type": "application/json"}),
        (200, {"content-type": "text/html", "content-length": "invalid"}),
        (200, {"content-type": "text/html", "content-length": str(2 * 1024 * 1024 + 1)}),
    ],
)
def test_alibaba_token_plan_official_fetch_rejects_status_media_and_declared_bounds(
    status: int,
    headers: dict[str, str],
):
    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    status,
                    headers=headers,
                    content=b"<html></html>",
                    request=request,
                )
            )
        ) as client:
            await fetch_alibaba_token_plan_official_video_model_ids(client)

    with pytest.raises(AlibabaTokenPlanOfficialCatalogError):
        asyncio.run(run())


def test_alibaba_token_plan_official_fetch_rejects_streamed_oversize(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(official_catalog, "MAX_OFFICIAL_CATALOG_BYTES", 10)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    headers={"content-type": "text/html"},
                    content=b"01234567890",
                    request=request,
                )
            )
        ) as client:
            await fetch_alibaba_token_plan_official_video_model_ids(client)

    with pytest.raises(AlibabaTokenPlanOfficialCatalogError, match="size limit"):
        asyncio.run(run())


def test_alibaba_token_plan_official_merge_adds_only_unambiguous_happyhorse_video():
    models = build_alibaba_token_plan_models_from_models_dev(
        {
            "alibaba-token-plan": {
                "models": {"live-image": {"modalities": {"input": ["text"], "output": ["image"]}}}
            }
        },
        ["live-image"],
        [
            "happyhorse-official-t2v",
            "happyhorse-official-i2v-r2v",
            "other-official-t2v",
            "live-image",
        ],
    )

    assert [model.id for model in models] == [
        "alibaba-token-plan/happyhorse-official-t2v",
        "alibaba-token-plan/live-image",
    ]
    video = models[0]
    assert video.architecture.input_modalities == ["text"]
    assert video.architecture.output_modalities == ["video"]
    assert video.toolsSupport is False
    encoded = encode_model_catalog(ResponseModel(data=[video]))
    assert encoded.version == 1
    assert encoded.data[0].capabilities & (1 << 2)


def test_alibaba_token_plan_live_failure_preserves_official_video(caplog: pytest.LogCaptureFixture):
    async def run() -> list[ModelInfo]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(503, request=request))
        ) as client:
            return await get_alibaba_token_plan_models_safe(
                models_dev_catalog=None,
                api_key="sentinel-secret",
                http_client=client,
                official_video_model_ids=["happyhorse-official-r2v"],
            )

    models = asyncio.run(run())
    assert [model.id for model in models] == ["alibaba-token-plan/happyhorse-official-r2v"]
    assert "sentinel-secret" not in caplog.text


def test_alibaba_token_plan_official_cache_ttls_and_failed_refresh_drop_stale(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    app = SimpleNamespace(state=SimpleNamespace(http_client=object()))
    clock = [100.0]
    fetch = AsyncMock(return_value=["happyhorse-first-t2v"])
    monkeypatch.setattr(inference.time, "monotonic", lambda: clock[0])

    with patch(
        "services.inference.fetch_alibaba_token_plan_official_video_model_ids",
        new=fetch,
    ):
        first = asyncio.run(inference._get_alibaba_official_video_catalog_snapshot(app))
        clock[0] += 599
        reused = asyncio.run(inference._get_alibaba_official_video_catalog_snapshot(app))
        fetch.side_effect = RuntimeError("sentinel-body")
        clock[0] += 2
        unavailable = asyncio.run(inference._get_alibaba_official_video_catalog_snapshot(app))
        clock[0] += 59
        reused_failure = asyncio.run(inference._get_alibaba_official_video_catalog_snapshot(app))
        fetch.side_effect = None
        fetch.return_value = ["happyhorse-recovered-i2v"]
        clock[0] += 2
        recovered = asyncio.run(inference._get_alibaba_official_video_catalog_snapshot(app))

    assert first is reused
    assert first.available is True
    assert unavailable is reused_failure
    assert unavailable.available is False
    assert unavailable.model_ids == ()
    assert first.fingerprint != unavailable.fingerprint != recovered.fingerprint
    assert recovered.model_ids == ("happyhorse-recovered-i2v",)
    assert fetch.await_count == 3
    assert "sentinel-body" not in caplog.text


def test_alibaba_token_plan_official_cache_shields_shared_inflight_and_cancellation():
    async def run() -> tuple[int, tuple[str, ...]]:
        app = SimpleNamespace(state=SimpleNamespace(http_client=object()))
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def fetch(_: object) -> list[str]:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return ["happyhorse-shared-t2v"]

        with patch(
            "services.inference.fetch_alibaba_token_plan_official_video_model_ids",
            new=fetch,
        ):
            cancelled_waiter = asyncio.create_task(
                inference._get_alibaba_official_video_catalog_snapshot(app)
            )
            await started.wait()
            surviving_waiter = asyncio.create_task(
                inference._get_alibaba_official_video_catalog_snapshot(app)
            )
            await asyncio.sleep(0)
            cancelled_waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled_waiter
            release.set()
            snapshot = await surviving_waiter
            await asyncio.sleep(0)
            assert app.state.alibaba_token_plan_official_video_catalog_inflight is None
            return calls, snapshot.model_ids

    assert asyncio.run(run()) == (1, ("happyhorse-shared-t2v",))


def test_alibaba_token_plan_snapshot_fingerprint_versions_and_prunes_provider_cache():
    app = FastAPI()
    app.state.http_client = object()
    app.state.models_dev_catalog = None
    legacy_key = inference._build_subscription_model_cache_key(
        ALIBABA_TOKEN_PLAN_PROVIDER_KEY,
        "credential-a",
    )
    app.state.subscription_provider_model_cache = {
        legacy_key: (0.0, [_model("alibaba-token-plan/stale-image")]),
        "unrelated:key": (0.0, [_model("unrelated/model")]),
    }
    loader = AsyncMock(return_value=[_model("alibaba-token-plan/happyhorse-current-t2v")])
    official_fetch = AsyncMock(return_value=["happyhorse-current-t2v"])

    with (
        patch(
            "services.inference.fetch_alibaba_token_plan_official_video_model_ids",
            new=official_fetch,
        ),
        patch("services.inference.get_alibaba_token_plan_models_safe", new=loader),
    ):
        models = asyncio.run(
            inference._get_cached_alibaba_token_plan_models(
                app,
                api_key="credential-a",
            )
        )
        asyncio.run(
            inference._get_cached_alibaba_token_plan_models(
                app,
                api_key="credential-b",
            )
        )
        app.state.alibaba_token_plan_official_video_catalog_cache = (
            inference._build_alibaba_official_snapshot(
                ["happyhorse-changed-i2v"],
                available=True,
            )
        )
        loader.return_value = [_model("alibaba-token-plan/happyhorse-changed-i2v")]
        changed_models = asyncio.run(
            inference._get_cached_alibaba_token_plan_models(
                app,
                api_key="credential-a",
            )
        )

    assert [model.id for model in models] == ["alibaba-token-plan/happyhorse-current-t2v"]
    assert legacy_key not in app.state.subscription_provider_model_cache
    assert "unrelated:key" in app.state.subscription_provider_model_cache
    alibaba_keys = [
        key
        for key in app.state.subscription_provider_model_cache
        if key.startswith(f"{ALIBABA_TOKEN_PLAN_PROVIDER_KEY}:")
    ]
    assert len(alibaba_keys) == 1
    assert all("official-video-v1" in key for key in alibaba_keys)
    assert [model.id for model in changed_models] == ["alibaba-token-plan/happyhorse-changed-i2v"]
    assert official_fetch.await_count == 1
    assert loader.await_count == 3
