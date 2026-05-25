import httpx
from services.provider_image_generation import ImageGenerationProviderError


def is_rate_limit_error(exc: ImageGenerationProviderError) -> bool:
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "rate limit" in message


def is_transient_provider_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current:
        if isinstance(current, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        current = current.__cause__ or current.__context__

    message = str(exc).lower()
    return "connect timeout" in message or "timed out" in message or "connection error" in message


def is_empty_image_result_error(exc: ImageGenerationProviderError) -> bool:
    message = str(exc).lower()
    if is_codex_auth_error(exc):
        return False
    return (
        "no images returned" in message
        or "no image generation result" in message
        or "image url missing" in message
        or "completed without returning an image" in message
    )


def is_codex_auth_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return (
        "openai codex authentication" in message
        or "failed to refresh token" in message
        or "refresh_token_reused" in message
        or "your refresh token has already been used" in message
    )


def codex_auth_failed_message() -> str:
    return (
        "OpenAI Codex authentication failed while refreshing token. "
        "Sign in again and update your Codex auth.json before generating images."
    )


def rate_limit_retry_message(delay_seconds: int) -> str:
    return f"Rate limited by image provider. Retrying in {delay_seconds}s."


def rate_limit_failed_message(attempts: int) -> str:
    return (
        f"Rate limited by image provider after {attempts} attempts. "
        "Try again later or reduce batch size."
    )


def transient_provider_retry_message(delay_seconds: int) -> str:
    return f"Image provider connection timed out. Retrying in {delay_seconds}s."


def transient_provider_failed_message(attempts: int) -> str:
    return (
        f"Image provider stayed unreachable after {attempts} attempts. "
        "Try again later or reduce batch size."
    )


def empty_image_result_retry_message(delay_seconds: int) -> str:
    return f"Image provider returned no image. Retrying in {delay_seconds}s."


def empty_image_result_failed_message(attempts: int) -> str:
    return (
        f"Image provider returned no image after {attempts} attempts. "
        "Try again later or choose another model."
    )
