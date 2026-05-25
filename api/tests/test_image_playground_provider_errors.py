import sys
from pathlib import Path

import httpx


sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.image_playground.provider_errors import (
    codex_auth_failed_message,
    empty_image_result_failed_message,
    empty_image_result_retry_message,
    is_codex_auth_error,
    is_empty_image_result_error,
    is_rate_limit_error,
    is_transient_provider_error,
    rate_limit_failed_message,
    rate_limit_retry_message,
    transient_provider_failed_message,
    transient_provider_retry_message,
)
from services.provider_image_generation import ImageGenerationProviderError


def test_provider_error_classification_detects_retryable_failures():
    assert is_rate_limit_error(ImageGenerationProviderError("429 rate limit exceeded"))
    assert is_empty_image_result_error(
        ImageGenerationProviderError("OpenAI Codex completed without returning an image.")
    )
    assert is_transient_provider_error(httpx.ConnectTimeout("connect timeout"))


def test_transient_provider_error_walks_exception_causes():
    root = httpx.ConnectError("network unavailable")
    wrapped = RuntimeError("provider failed")
    wrapped.__cause__ = root

    assert is_transient_provider_error(wrapped)


def test_codex_auth_errors_are_not_treated_as_empty_image_results():
    exc = ImageGenerationProviderError(
        "OpenAI Codex authentication failed while refreshing token: refresh_token_reused"
    )

    assert is_codex_auth_error(exc)
    assert not is_empty_image_result_error(exc)
    assert "Sign in again" in codex_auth_failed_message()


def test_provider_error_messages_are_user_facing_and_attempt_aware():
    assert rate_limit_retry_message(30) == "Rate limited by image provider. Retrying in 30s."
    assert "after 6 attempts" in rate_limit_failed_message(6)
    assert transient_provider_retry_message(10).endswith("Retrying in 10s.")
    assert "stayed unreachable" in transient_provider_failed_message(3)
    assert empty_image_result_retry_message(20).endswith("Retrying in 20s.")
    assert "choose another model" in empty_image_result_failed_message(6)
