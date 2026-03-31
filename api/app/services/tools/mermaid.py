import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

DEFAULT_MERMAID_MAX_RETRY = 3
MAX_MERMAID_MAX_RETRY = 10
MAX_MERMAID_ERROR_DETAIL_LENGTH = 4000
MERMAID_VALIDATOR_TIMEOUT_SECONDS = 15


class MermaidValidationError(Exception):
    def __init__(self, message: str, *, last_content: str | None = None):
        super().__init__(message)
        self.last_content = last_content


class MermaidValidatorRuntimeError(RuntimeError):
    pass


def build_mermaid_user_prompt(title: str, instructions: str, context: str) -> str:
    return (
        f"Title:\n{title or 'None provided'}\n\n"
        f"Instructions:\n{instructions}\n\n"
        f"Context:\n{context}"
    )


def build_mermaid_retry_prompt(
    title: str,
    instructions: str,
    context: str,
    last_content: str,
    error_detail: str,
) -> str:
    return (
        "Your previous Mermaid output failed backend validation.\n"
        "Return corrected Mermaid source for the same diagram request.\n"
        "Keep the same intent and scope. Return structured data only.\n\n"
        f"Title:\n{title or 'None provided'}\n\n"
        f"Instructions:\n{instructions}\n\n"
        f"Context:\n{context}\n\n"
        f"Previous Mermaid:\n{last_content or '[empty]'}\n\n"
        f"Validation Error:\n{error_detail}"
    )


def normalize_mermaid_retry_count(value: Any) -> int:
    try:
        retry_count = int(value)
    except (TypeError, ValueError):
        retry_count = DEFAULT_MERMAID_MAX_RETRY
    return max(0, min(retry_count, MAX_MERMAID_MAX_RETRY))


def format_mermaid_error_detail(error: str) -> str:
    normalized = " ".join(str(error).split()) if "\n" not in str(error) else str(error).strip()
    if len(normalized) <= MAX_MERMAID_ERROR_DETAIL_LENGTH:
        return normalized
    return normalized[: MAX_MERMAID_ERROR_DETAIL_LENGTH - 3].rstrip() + "..."


def get_default_mermaid_validator_script() -> Path:
    return Path(__file__).resolve().parents[4] / "ui" / "shared" / "mermaid" / "validate.mjs"


def resolve_mermaid_validator_script() -> Path:
    script_path = str(os.getenv("MERMAID_VALIDATOR_SCRIPT") or "").strip()
    if script_path:
        return Path(script_path)
    return get_default_mermaid_validator_script()


def coerce_mermaid_last_content(
    raw_content: str,
    strip_outer_fence: Callable[[str], str],
) -> str | None:
    normalized = strip_outer_fence(raw_content)
    return normalized or None


def validate_mermaid_candidate(
    raw_content: str,
    *,
    parse_response: Callable[[str, str], Any],
    validate_fragment: Callable[[str, str], str],
    strip_outer_fence: Callable[[str], str],
) -> tuple[Any, str]:
    last_content = coerce_mermaid_last_content(raw_content, strip_outer_fence)

    try:
        parsed = parse_response(raw_content, "mermaid")
    except Exception as exc:
        raise MermaidValidationError(
            "The visual generator returned malformed Mermaid output.",
            last_content=last_content,
        ) from exc

    if parsed.mode != "mermaid":
        raise MermaidValidationError(
            f"The visual generator returned mode '{parsed.mode}' but 'mermaid' was requested.",
            last_content=strip_outer_fence(parsed.content),
        )

    try:
        validated_content = validate_fragment(parsed.mode, parsed.content)
    except Exception as exc:
        raise MermaidValidationError(
            str(exc),
            last_content=strip_outer_fence(parsed.content),
        ) from exc

    return parsed, validated_content


async def validate_mermaid_with_runtime(content: str) -> None:
    validator_script = resolve_mermaid_validator_script()
    if not validator_script.is_file():
        raise MermaidValidatorRuntimeError(
            "Mermaid validation runtime is unavailable: validator script was not found."
        )

    try:
        process = await asyncio.create_subprocess_exec(
            "node",
            str(validator_script),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise MermaidValidatorRuntimeError(
            "Mermaid validation runtime is unavailable: 'node' is not installed."
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=json.dumps({"content": content}).encode("utf-8")),
            timeout=MERMAID_VALIDATOR_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise MermaidValidatorRuntimeError("Mermaid validation runtime timed out.") from exc

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()

    try:
        payload = json.loads(stdout_text) if stdout_text else {}
    except json.JSONDecodeError as exc:
        raise MermaidValidatorRuntimeError(
            "Mermaid validation runtime returned malformed output."
        ) from exc

    if process.returncode != 0:
        raise MermaidValidatorRuntimeError(
            format_mermaid_error_detail(
                str(payload.get("error") or stderr_text or "Mermaid validation runtime failed.")
            )
        )

    if payload.get("ok") is True:
        return

    raise MermaidValidationError(
        format_mermaid_error_detail(str(payload.get("error") or "Mermaid parsing failed.")),
        last_content=content,
    )


async def generate_mermaid_with_retry(
    *,
    req,
    model: str,
    system_prompt: str,
    title: str,
    instructions: str,
    context: str,
    enable_retry: bool,
    max_retry: int,
    build_payload: Callable[..., dict[str, Any]],
    request_content: Callable[[Any, dict[str, Any]], Awaitable[str]],
    parse_response: Callable[[str, str], Any],
    validate_fragment: Callable[[str, str], str],
    normalize_title: Callable[[str | None, str | None, str], str | None],
    strip_outer_fence: Callable[[str], str],
    logger: logging.Logger,
) -> dict[str, Any]:
    allowed_retries = max_retry if enable_retry else 0
    last_content = ""
    last_error = ""
    last_generated_title: str | None = None

    for attempt_index in range(allowed_retries + 1):
        user_prompt = (
            build_mermaid_user_prompt(title, instructions, context)
            if attempt_index == 0
            else build_mermaid_retry_prompt(
                title,
                instructions,
                context,
                last_content,
                last_error,
            )
        )
        raw_content = await request_content(
            req,
            build_payload(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
            ),
        )

        try:
            logger
            parsed, validated_content = validate_mermaid_candidate(
                raw_content,
                parse_response=parse_response,
                validate_fragment=validate_fragment,
                strip_outer_fence=strip_outer_fence,
            )
            last_content = validated_content
            last_generated_title = parsed.title
            await validate_mermaid_with_runtime(validated_content)
            normalized_title = normalize_title(title, parsed.title, instructions)
            return {
                "mode": "mermaid",
                "content": validated_content,
                **({"title": normalized_title} if normalized_title else {}),
            }
        except MermaidValidationError as exc:
            last_content = (
                exc.last_content
                or last_content
                or (coerce_mermaid_last_content(raw_content, strip_outer_fence) or "")
            )
            last_error = format_mermaid_error_detail(str(exc))

            if attempt_index < allowed_retries:
                logger.info(
                    "Retrying Mermaid generation after validation error on attempt %s/%s: %s",
                    attempt_index + 1,
                    allowed_retries + 1,
                    last_error,
                )
                continue

            normalized_title = normalize_title(title, last_generated_title, instructions)
            return {
                "error": f"Visual generation failed: {last_error}",
                "last_content": last_content,
                "parse_error": last_error,
                "retry_attempts": attempt_index,
                **({"title": normalized_title} if normalized_title else {}),
            }

    normalized_title = normalize_title(title, last_generated_title, instructions)
    fallback_error = last_error or "Mermaid validation failed."
    return {
        "error": f"Visual generation failed: {fallback_error}",
        "last_content": last_content,
        "parse_error": fallback_error,
        "retry_attempts": allowed_retries,
        **({"title": normalized_title} if normalized_title else {}),
    }
