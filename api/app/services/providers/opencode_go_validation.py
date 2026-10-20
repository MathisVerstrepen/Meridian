"""Validate OpenCode Go credentials without depending on one model's availability."""

import httpx
from services.providers.opencode_go_errors import parse_opencode_go_error
from services.providers.opencode_go_headers import build_opencode_go_session_headers

OPENCODE_GO_VALIDATION_URL = "https://opencode.ai/inference/go/openai/v1/chat/completions"
# These subscription models all use the OpenAI Chat Completions protocol.
# Do not use free models here: success must require subscription credentials.
OPENCODE_GO_VALIDATION_MODELS = ("kimi-k3", "glm-5.3-flash", "deepseek-v4.1-flash")


async def validate_opencode_go_api_key(
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        **build_opencode_go_session_headers(),
    }

    async def _do_validate(client: httpx.AsyncClient) -> None:
        for model in OPENCODE_GO_VALIDATION_MODELS:
            response = await client.post(
                OPENCODE_GO_VALIDATION_URL,
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Reply with OK."}],
                    "stream": False,
                    "max_tokens": 16,
                },
            )
            if response.status_code == 200:
                return

            error_message = parse_opencode_go_error(response.content)
            model_unavailable = response.status_code in (400, 404) and any(
                marker in error_message.lower()
                for marker in ("model is unavailable", "model is not available", "model not found")
            )
            if not model_unavailable:
                raise ValueError(
                    f"OpenCode Go validation failed (status {response.status_code}): "
                    f"{error_message}"
                )

        raise ValueError(
            "OpenCode Go validation is temporarily unavailable: all validation models are "
            "unavailable. Please try again later."
        )

    if http_client is not None:
        await _do_validate(http_client)
        return

    async with httpx.AsyncClient(timeout=60.0, http2=True) as client:
        await _do_validate(client)
