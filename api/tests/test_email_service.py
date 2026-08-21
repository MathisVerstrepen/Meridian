import asyncio
from collections.abc import Callable
from email.message import Message
from typing import Any

import pytest

from app.services import email_service
from app.services.email_service import EmailService

EMAIL_ENV_KEYS = (
    "EMAIL_PROVIDER",
    "SMTP_SERVER",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_AUTH_PROTOCOL",
    "SMTP_FROM_EMAIL",
    "SES_REGION",
    "SES_FROM_EMAIL",
    "SES_CONFIGURATION_SET_NAME",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)


@pytest.fixture(autouse=True)
def clear_email_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in EMAIL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.message: Message | None = None
        self.instances.append(self)

    async def __aenter__(self) -> "FakeSmtp":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def starttls(self) -> None:
        self.started_tls = True

    async def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    async def send_message(self, message: Message) -> None:
        self.message = message


def configure_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_AUTH_PROTOCOL", "STARTTLS")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "sender@example.test")


@pytest.mark.parametrize("provider", [None, " SMTP "])
def test_smtp_default_and_explicit_selection(
    monkeypatch: pytest.MonkeyPatch, provider: str | None
) -> None:
    FakeSmtp.instances.clear()
    configure_smtp(monkeypatch)
    if provider is not None:
        monkeypatch.setenv("EMAIL_PROVIDER", provider)
    monkeypatch.setattr(email_service.aiosmtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(
        email_service.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("SES client created for SMTP delivery"),
    )

    asyncio.run(EmailService.send_verification_email("recipient@example.test", "123456"))

    client = FakeSmtp.instances[-1]
    assert client.kwargs == {
        "hostname": "smtp.example.test",
        "port": 587,
        "use_tls": False,
    }
    assert client.started_tls is True
    assert client.login_args == ("smtp-user", "smtp-password")
    assert client.message is not None
    assert client.message["From"] == "sender@example.test"
    assert client.message["To"] == "recipient@example.test"
    assert client.message["Subject"] == "Verify your Meridian Account"
    assert "123456" in client.message.get_payload()[0].get_payload(decode=True).decode()


@pytest.mark.parametrize("configuration_set", [None, "transactional"])
def test_ses_request_and_default_credential_chain(
    monkeypatch: pytest.MonkeyPatch, configuration_set: str | None
) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.setenv("SES_REGION", "eu-west-1")
    monkeypatch.setenv("SES_FROM_EMAIL", "verified@example.test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "access-sentinel")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-sentinel")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token-sentinel")
    if configuration_set is not None:
        monkeypatch.setenv("SES_CONFIGURATION_SET_NAME", configuration_set)

    client_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    requests: list[dict[str, object]] = []

    class FakeSesClient:
        def send_email(self, **request: object) -> None:
            requests.append(request)

    def fake_client(*args: object, **kwargs: object) -> FakeSesClient:
        client_calls.append((args, kwargs))
        return FakeSesClient()

    offloaded: list[Callable[..., object]] = []

    async def fake_to_thread(function: Callable[..., object], *args: object) -> object:
        offloaded.append(function)
        return function(*args)

    monkeypatch.setattr(email_service.boto3, "client", fake_client)
    monkeypatch.setattr(email_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(
        EmailService,
        "_send_smtp",
        lambda *args: pytest.fail("SMTP fallback attempted for SES delivery"),
    )

    asyncio.run(EmailService.send_verification_email("recipient@example.test", "654321"))

    assert offloaded == [EmailService._send_ses_sync]
    assert client_calls == [(("sesv2",), {"region_name": "eu-west-1"})]
    request = requests[0]
    assert request["FromEmailAddress"] == "verified@example.test"
    assert request["Destination"] == {"ToAddresses": ["recipient@example.test"]}
    content = request["Content"]
    assert isinstance(content, dict)
    simple = content["Simple"]
    assert simple["Subject"] == {
        "Data": "Verify your Meridian Account",
        "Charset": "UTF-8",
    }
    assert simple["Body"]["Html"]["Charset"] == "UTF-8"
    assert "654321" in simple["Body"]["Html"]["Data"]
    if configuration_set is None:
        assert "ConfigurationSetName" not in request
    else:
        assert request["ConfigurationSetName"] == configuration_set


@pytest.mark.parametrize(
    ("provider", "region", "from_email"),
    [
        ("invalid", "eu-west-1", "verified@example.test"),
        ("ses", "", "verified@example.test"),
        ("ses", "eu-west-1", ""),
    ],
)
def test_invalid_provider_or_incomplete_ses_configuration_sends_nothing(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    region: str,
    from_email: str,
) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", provider)
    monkeypatch.setenv("SES_REGION", region)
    monkeypatch.setenv("SES_FROM_EMAIL", from_email)
    monkeypatch.setattr(
        email_service.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("SES client created with invalid configuration"),
    )
    monkeypatch.setattr(
        email_service.aiosmtplib,
        "SMTP",
        lambda *args, **kwargs: pytest.fail("SMTP fallback attempted"),
    )

    asyncio.run(EmailService.send_verification_email("recipient@example.test", "123456"))


def test_ses_failure_is_sanitized_and_does_not_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    recipient = "recipient-sentinel@example.test"
    code = "otp-sentinel"
    exception = RuntimeError("secret-sentinel recipient-sentinel otp-sentinel")
    messages: list[str] = []
    captured: list[BaseException] = []

    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.setenv("SES_REGION", "eu-west-1")
    monkeypatch.setenv("SES_FROM_EMAIL", "sender-sentinel@example.test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-sentinel")
    monkeypatch.setattr(
        EmailService,
        "_send_ses_sync",
        lambda *args: (_ for _ in ()).throw(exception),
    )
    monkeypatch.setattr(
        EmailService,
        "_send_smtp",
        lambda *args: pytest.fail("SMTP fallback attempted after SES failure"),
    )
    monkeypatch.setattr(email_service.sentry_sdk, "capture_exception", captured.append)
    monkeypatch.setattr(email_service.logger, "error", messages.append)

    asyncio.run(EmailService.send_verification_email(recipient, code))

    assert captured == [exception]
    logged = " ".join(messages)
    for sentinel in (recipient, code, "sender-sentinel", "secret-sentinel"):
        assert sentinel not in logged


def test_incomplete_smtp_log_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-sentinel")
    monkeypatch.setattr(email_service.logger, "error", messages.append)

    asyncio.run(
        EmailService.send_verification_email("recipient-sentinel@example.test", "otp-sentinel")
    )

    logged = " ".join(messages)
    for sentinel in ("recipient-sentinel", "otp-sentinel", "secret-sentinel"):
        assert sentinel not in logged
