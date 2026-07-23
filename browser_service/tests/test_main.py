import json
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from browser_service.app.browser_fetch import AdmissionQueueFullError
from browser_service.app.config import BrowserServiceSettings
from browser_service.app.main import create_app
from browser_service.app.models import BrowserFetchError, FailureReason
from browser_service.app.process_hardening import ProcessHardeningError

TOKEN = "b" * 64


class FakeHardening:
    def __init__(self) -> None:
        self.applied = False
        self.valid = True

    def apply(self) -> None:
        self.applied = True

    def assert_applied(self) -> None:
        if not self.applied or not self.valid:
            raise ProcessHardeningError()


class FakeManager:
    def __init__(self, proxy_config=None, error=None) -> None:
        self.proxy_config = proxy_config
        self.error = error
        self.calls = []
        self.closed = 0

    async def fetch(self, url: str) -> str:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return "<html>safe</html>"

    async def close(self) -> None:
        self.closed += 1


def settings(proxy: str | None = None) -> BrowserServiceSettings:
    return BrowserServiceSettings(
        LINK_EXTRACTION_BROWSER_SERVICE_PORT=5010,
        LINK_EXTRACTION_BROWSER_SERVICE_TOKEN=SecretStr(TOKEN),
        LINK_EXTRACTION_BROWSER_PROXY_URL=SecretStr(proxy) if proxy else None,
    )


def build_app(manager: FakeManager, hardening: FakeHardening):
    return create_app(
        hardening_factory=lambda: hardening,  # type: ignore[arg-type]
        settings_loader=settings,
        manager_factory=lambda **kwargs: manager,
        artifact_verifier=lambda: None,
        browser_version_loader=lambda: "152.0.4-beta.27",
        cache_preflight=lambda version, geoip: None,
    )


def test_health_auth_fetch_environment_scrub_and_shutdown(monkeypatch) -> None:
    monkeypatch.setenv("LINK_EXTRACTION_BROWSER_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("LINK_EXTRACTION_BROWSER_PROXY_URL", "http://proxy.example:8080")
    manager = FakeManager()
    hardening = FakeHardening()
    app = build_app(manager, hardening)
    request_id = str(uuid4())

    with TestClient(app) as client:
        assert hardening.applied
        assert "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN" not in os.environ
        assert "LINK_EXTRACTION_BROWSER_PROXY_URL" not in os.environ
        assert client.get("/health").json() == {
            "status": "ok",
            "browser_build": "152.0.4-beta.27",
            "capacity": 4,
            "queue_capacity": 8,
        }
        payload = {"request_id": request_id, "url": "https://example.com/private"}
        missing = client.post("/v1/fetch", json=payload)
        wrong = client.post("/v1/fetch", json=payload, headers={"Authorization": "Bearer wrong"})
        assert missing.status_code == wrong.status_code == 401
        assert missing.json() == wrong.json() == {"detail": "unauthorized"}
        inherited = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "import os; print(int(any(k in os.environ for k in "
                "('LINK_EXTRACTION_BROWSER_SERVICE_TOKEN', "
                "'LINK_EXTRACTION_BROWSER_PROXY_URL'))))",
            ],
            text=True,
        )
        assert inherited.strip() == "0"
        response = client.post(
            "/v1/fetch", json=payload, headers={"Authorization": f"Bearer {TOKEN}"}
        )
        assert response.status_code == 200
        assert response.json() == {
            "request_id": request_id,
            "html": "<html>safe</html>",
        }
    assert manager.closed == 1


def test_raw_non_ascii_bearer_returns_constant_401_before_body_parsing(caplog) -> None:
    manager = FakeManager()
    app = build_app(manager, FakeHardening())

    async def raw_request():
        messages = [{"type": "http.request", "body": b"not-json", "more_body": False}]
        sent = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/v1/fetch",
                "raw_path": b"/v1/fetch",
                "query_string": b"",
                "root_path": "",
                "headers": [(b"authorization", b"Bearer " + b"x" * 31 + b"\xff")],
                "client": ("127.0.0.1", 1),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )
        return sent

    with TestClient(app) as client:
        assert client.portal is not None
        sent = client.portal.call(raw_request)

    start = next(message for message in sent if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"") for message in sent if message["type"] == "http.response.body"
    )
    assert start["status"] == 401
    assert json.loads(body) == {"detail": "unauthorized"}
    assert manager.calls == []
    assert "ÿ" not in caplog.text


def test_later_hardening_failure_is_constant_and_prevents_admission() -> None:
    manager = FakeManager()
    hardening = FakeHardening()
    app = build_app(manager, hardening)
    with TestClient(app) as client:
        hardening.valid = False
        assert client.get("/health").json() == {"status": "not_ready"}
        request_id = str(uuid4())
        response = client.post(
            "/v1/fetch",
            json={"request_id": request_id, "url": "https://example.com"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert response.status_code == 503
        assert response.json()["error"] == {
            "reason": "browser_failed",
            "status_code": None,
        }
        assert manager.calls == []


def test_queue_full_and_target_errors_use_constant_protocol() -> None:
    request_id = str(uuid4())
    for error, expected_status in (
        (AdmissionQueueFullError(), 429),
        (BrowserFetchError(FailureReason.HTTP_REJECTED, 403), 502),
        (BrowserFetchError(FailureReason.CONNECTIVITY_EXHAUSTED), 504),
    ):
        app = build_app(FakeManager(error=error), FakeHardening())
        with TestClient(app) as client:
            response = client.post(
                "/v1/fetch",
                json={"request_id": request_id, "url": "https://example.com"},
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
        assert response.status_code == expected_status
        assert set(response.json()) == {"request_id", "error"}
        assert "detail" not in response.json()


def test_hardening_failure_precedes_settings_and_never_starts() -> None:
    calls = []

    class FailingHardening(FakeHardening):
        def apply(self) -> None:
            calls.append("hardening")
            raise ProcessHardeningError()

    app = create_app(
        hardening_factory=FailingHardening,  # type: ignore[arg-type]
        settings_loader=lambda: calls.append("settings") or settings(),
        artifact_verifier=lambda: None,
    )
    with pytest.raises(ProcessHardeningError):
        with TestClient(app):
            pass
    assert calls == ["hardening"]


@pytest.mark.parametrize(
    "token",
    [
        "x" * 31,
        " " + "x" * 32,
        "x" * 32 + " ",
        "x" * 16 + " " + "x" * 16,
        "x" * 16 + "\t" + "x" * 16,
        "x" * 16 + "\r" + "x" * 16,
        "x" * 16 + "\n" + "x" * 16,
        "x" * 32 + "\x7f",
        "x" * 32 + "\x1f",
        "é" * 32,
        "🦊" * 8,
        "",
        "change-me",
        "replace-me",
        "example",
    ],
)
def test_invalid_header_tokens_fail_settings_validation(token: str) -> None:
    with pytest.raises(ValidationError):
        BrowserServiceSettings(
            LINK_EXTRACTION_BROWSER_SERVICE_PORT=5010,
            LINK_EXTRACTION_BROWSER_SERVICE_TOKEN=SecretStr(token),
        )


@pytest.mark.parametrize("token", ["!" * 32, "0123456789abcdef" * 4])
def test_visible_ascii_tokens_pass_settings_validation(token: str) -> None:
    configured = BrowserServiceSettings(
        LINK_EXTRACTION_BROWSER_SERVICE_PORT=5010,
        LINK_EXTRACTION_BROWSER_SERVICE_TOKEN=SecretStr(token),
    )
    assert configured.token.get_secret_value() == token


def test_invalid_token_prevents_lifespan_readiness() -> None:
    manager_created = False

    def manager_factory(**kwargs):
        nonlocal manager_created
        manager_created = True
        return FakeManager()

    app = create_app(
        hardening_factory=FakeHardening,  # type: ignore[arg-type]
        settings_loader=lambda: BrowserServiceSettings(
            LINK_EXTRACTION_BROWSER_SERVICE_PORT=5010,
            LINK_EXTRACTION_BROWSER_SERVICE_TOKEN=SecretStr("x" * 32 + "\n"),
        ),
        manager_factory=manager_factory,
        artifact_verifier=lambda: None,
    )
    with pytest.raises(ValidationError):
        with TestClient(app):
            pass
    assert not manager_created
