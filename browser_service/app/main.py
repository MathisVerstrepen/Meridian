import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .artifacts import verify_cache_manifest
from .browser_fetch import AdmissionQueueFullError, BrowserFetchManager
from .camoufox_runtime import (
    EXPECTED_BROWSER_BUILD,
    BrowserProxyConfig,
    load_browser_version,
    parse_browser_proxy,
    preflight_camoufox_cache,
)
from .config import PROXY_ENV, TOKEN_ENV, BrowserServiceSettings, load_settings
from .models import BrowserFetchError, FailureReason, FetchFailure, FetchRequest, FetchSuccess
from .process_hardening import ProcessHardening, ProcessHardeningError

logger = logging.getLogger("uvicorn.error")


def _valid_supplied_token(token: str) -> bool:
    return len(token) >= 32 and all("\x21" <= character <= "\x7e" for character in token)


@dataclass
class ServiceState:
    hardening: ProcessHardening | None = None
    settings: BrowserServiceSettings | None = None
    manager: BrowserFetchManager | None = None
    ready: bool = False

    def assert_ready(self) -> None:
        if not self.ready or self.hardening is None or self.manager is None:
            raise ProcessHardeningError()
        self.hardening.assert_applied()


def create_app(
    *,
    hardening_factory: Callable[[], ProcessHardening] = ProcessHardening,
    settings_loader: Callable[[], BrowserServiceSettings] = load_settings,
    manager_factory: Callable[..., BrowserFetchManager] = BrowserFetchManager,
    artifact_verifier: Callable[[], None] = verify_cache_manifest,
    browser_version_loader: Callable[[], str] = load_browser_version,
    cache_preflight: Callable[[str, bool], None] = preflight_camoufox_cache,
) -> FastAPI:
    state = ServiceState()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        hardening = hardening_factory()
        hardening.apply()
        state.hardening = hardening
        settings = settings_loader()
        state.settings = settings
        proxy_value = settings.proxy_url.get_secret_value() if settings.proxy_url else ""
        proxy: BrowserProxyConfig | None = None
        if proxy_value.strip():
            try:
                proxy = parse_browser_proxy(proxy_value)
            except ValueError:
                logger.warning("%s is invalid; launching browser without a proxy", PROXY_ENV)
        os.environ.pop(TOKEN_ENV, None)
        os.environ.pop(PROXY_ENV, None)
        proxy_value = ""
        artifact_verifier()
        version = browser_version_loader()
        cache_preflight(version, True)
        state.manager = manager_factory(proxy_config=proxy)
        state.ready = True
        try:
            yield
        finally:
            state.ready = False
            if state.manager is not None:
                await state.manager.close()

    application = FastAPI(
        title="Meridian Browser Service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.browser_service = state

    @application.get("/health")
    async def health() -> JSONResponse:
        try:
            state.assert_ready()
        except ProcessHardeningError:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return JSONResponse(
            content={
                "status": "ok",
                "browser_build": EXPECTED_BROWSER_BUILD.rsplit("/", 1)[-1],
                "capacity": 4,
                "queue_capacity": 8,
            }
        )

    @application.post("/v1/fetch")
    async def fetch(request: Request) -> JSONResponse:
        settings = state.settings
        authorization = request.headers.get("authorization")
        supplied = ""
        if authorization and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        expected = settings.token.get_secret_value() if settings is not None else ""
        if (
            not _valid_supplied_token(supplied)
            or not expected
            or not hmac.compare_digest(supplied, expected)
        ):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        try:
            payload = FetchRequest.model_validate(await request.json())
        except Exception:
            return JSONResponse(status_code=422, content={"detail": "invalid_request"})
        try:
            state.assert_ready()
        except ProcessHardeningError:
            return _failure(payload, 503, FailureReason.BROWSER_FAILED)
        manager = state.manager
        assert manager is not None
        work = asyncio.create_task(manager.fetch(payload.url))
        disconnected = asyncio.create_task(_wait_for_disconnect(request))
        done, _ = await asyncio.wait({work, disconnected}, return_when=asyncio.FIRST_COMPLETED)
        if disconnected in done and disconnected.result():
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
            raise asyncio.CancelledError
        disconnected.cancel()
        await asyncio.gather(disconnected, return_exceptions=True)
        try:
            html = await work
        except BrowserFetchError as error:
            status = (
                429 if isinstance(error, AdmissionQueueFullError) else _failure_status(error.reason)
            )
            return _failure(payload, status, error.reason, error.status_code)
        return JSONResponse(
            status_code=200,
            content=FetchSuccess(request_id=payload.request_id, html=html).model_dump(mode="json"),
        )

    return application


async def _wait_for_disconnect(request: Request) -> bool:
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return True


def _failure_status(reason: FailureReason) -> int:
    if reason is FailureReason.CONNECTIVITY_EXHAUSTED:
        return 504
    return 502


def _failure(
    request: FetchRequest,
    status: int,
    reason: FailureReason,
    target_status: int | None = None,
) -> JSONResponse:
    body = FetchFailure(
        request_id=request.request_id,
        error={"reason": reason, "status_code": target_status},  # type: ignore[arg-type]
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


app = create_app()
