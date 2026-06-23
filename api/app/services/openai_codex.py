import asyncio
import base64
import contextlib
import json
import logging
import mimetypes
import re
import tempfile
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

import httpx
from database.pg.chat_ops import create_tool_call
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.models import ToolCallStatusEnum
from database.redis.redis_ops import RedisManager
from models.message import MessageContentTypeEnum, ToolEnum
from models.tool_question import AskUserPendingResult
from pydantic import BaseModel
from services.provider_runtime import (
    build_runtime_directory_layout,
    build_subprocess_env,
    cleanup_runtime_dir,
    ensure_private_directory,
)
from services.providers.common import (
    GENERIC_STREAM_ERROR_MESSAGE,
    BaseProviderReq,
    ThinkingState,
    extract_text_content,
    has_file_attachments,
    normalize_role_value,
    normalize_tool_storage_value,
    persist_refreshed_provider_token,
    sanitize_external_tool_references,
    stream_background_task_chunks,
    strip_model_prefix,
    write_private_file,
)
from services.providers.openai_codex_catalog import (
    OPENAI_CODEX_MODEL_PREFIX,
    OPENAI_CODEX_PROVIDER_KEY,
    get_models_dev_openai_codex_models,
    get_openai_codex_image_generation_base_model_id,
)
from services.providers.tool_continuation import persist_pending_tool_continuation
from services.tools import (
    TOOL_HANDLERS_BY_NAME,
    get_openrouter_tools,
    get_tool_runtime,
    resolve_tool_status,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

ASK_USER_TOOL_NAME = ToolEnum.ASK_USER.value
ASK_USER_BATCH_ERROR = (
    "ask_user must be the only interactive tool call in a tool round. "
    "Ask one question at a time and wait for the user response before requesting more tools."
)
OPENAI_CODEX_RUNTIME_PREFIX = "meridian-openai-codex-"
OPENAI_CODEX_RUNTIME_ROOT = Path(tempfile.gettempdir())
OPENAI_CODEX_RUNTIME_TTL_SECONDS = 60 * 60
OPENAI_CODEX_RPC_TIMEOUT_SECONDS = 30.0
OPENAI_CODEX_TURN_TIMEOUT_SECONDS = 300.0
OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_CODEX_ISSUER = "https://auth.openai.com"
OPENAI_CODEX_API_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
OPENAI_RESPONSES_API_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODELS_API_ENDPOINT = "https://api.openai.com/v1/models"
OPENAI_CODEX_DEVICE_VERIFICATION_URL = f"{OPENAI_CODEX_ISSUER}/codex/device"
OPENAI_CODEX_DEVICE_REDIRECT_URI = f"{OPENAI_CODEX_ISSUER}/deviceauth/callback"
OPENAI_CODEX_OAUTH_TIMEOUT_SECONDS = 5 * 60
OPENAI_CODEX_DEVICE_SESSION_REDIS_PREFIX = "openai_codex_device_oauth:"
OPENAI_CODEX_REFRESH_MARGIN_SECONDS = 60
OPENAI_CODEX_DEVICE_POLL_SAFETY_SECONDS = 3
OPENAI_CODEX_AUTH_PROBE_INPUT = "Reply with OK."
OPENAI_CODEX_AUTH_PROBE_INSTRUCTIONS = "Validate this OpenAI Codex session. Reply with OK."
OPENAI_CODEX_IMAGE_GENERATION_INSTRUCTIONS = (
    "You are an image generation assistant. Follow the user's prompt and reference images. "
    "Use the image_generation tool exactly once and return the generated image."
)
OPENAI_CODEX_FALLBACK_USER_CONTENT = "Please respond to the available context."
OPENAI_CODEX_STDERR_MAX_LINES = 200
OPENAI_CODEX_STDIO_LIMIT_BYTES = 128 * 1024 * 1024
OPENAI_CODEX_MAX_DATA_URI_BYTES = 20 * 1024 * 1024
OPENAI_CODEX_MAX_DATA_URI_BASE64_CHARS = ((OPENAI_CODEX_MAX_DATA_URI_BYTES + 2) // 3) * 4
OPENAI_CODEX_CONFIG_TOML = """cli_auth_credentials_store = \"file\"
web_search = \"disabled\"

[features]
apps = false
multi_agent = false
shell_tool = false

[tools]
disable_defaults = true

[tools.shell]
enabled = false

[tools.filesystem]
enabled = false

[tools.javascript]
enabled = false

[tools.agents]
enabled = false

[tools.agent_jobs]
enabled = false

[tools.planning]
enabled = false

[tools.user_input]
enabled = false

[tools.web_search]
enabled = false

[tools.image_generation]
enabled = false

[tools.document_generation]
enabled = false

[apps._default]
enabled = false
destructive_enabled = false
open_world_enabled = false
"""
JSON_WHITESPACE_TRANSLATION = str.maketrans(
    {
        "\ufeff": "",
        "\u00a0": " ",
        "\u2007": " ",
        "\u202f": " ",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\u2060": "",
    }
)


@dataclass
class OpenAICodexDeviceAuthSession:
    session_id: str
    device_auth_id: str
    user_code: str
    interval_seconds: int
    expires_at: float


_openai_codex_device_sessions: dict[str, OpenAICodexDeviceAuthSession] = {}
_openai_codex_refresh_tasks: dict[str, asyncio.Task[str]] = {}


@dataclass
class OpenAICodexRuntimeContext:
    root_dir: Path
    cwd: Path
    env: dict[str, str]
    codex_home: Path
    auth_json_path: Path
    model_instructions_path: Path | None
    input_dir: Path


class _CodexAppServerClient:
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._notifications: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._stderr_lines: deque[str] = deque(maxlen=OPENAI_CODEX_STDERR_MAX_LINES)
        self._stdout_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())

    @property
    def stderr_text(self) -> str:
        return "\n".join(line for line in self._stderr_lines if line).strip()

    async def _read_stdout(self) -> None:
        try:
            assert self.process.stdout is not None
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    message = json.loads(line.decode("utf-8", errors="replace").strip())
                except json.JSONDecodeError:
                    continue

                message_id = message.get("id")
                if message_id is not None and (
                    isinstance(message, dict)
                    and ("result" in message or "error" in message)
                    and isinstance(message_id, int)
                ):
                    pending = self._pending.pop(message_id, None)
                    if pending is not None and not pending.done():
                        pending.set_result(message)
                    continue

                await self._notifications.put(message)
        except asyncio.CancelledError:
            raise
        finally:
            for pending in self._pending.values():
                if not pending.done():
                    pending.set_exception(
                        RuntimeError(self.stderr_text or "OpenAI Codex app-server stopped.")
                    )
            self._pending.clear()
            await self._notifications.put(None)

    async def _read_stderr(self) -> None:
        try:
            assert self.process.stderr is not None
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8", errors="replace").strip()
                if decoded_line:
                    self._stderr_lines.append(decoded_line)
        except asyncio.CancelledError:
            raise

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = OPENAI_CODEX_RPC_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        if self.process.stdin is None:
            raise RuntimeError("OpenAI Codex app-server stdin is unavailable.")

        message_id = self._next_id
        self._next_id += 1

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[message_id] = future

        payload = {"method": method, "id": message_id, "params": params or {}}
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except Exception:
            self._pending.pop(message_id, None)
            raise

        if isinstance(response, dict) and response.get("error"):
            error_payload = response["error"]
            if isinstance(error_payload, dict):
                raise ValueError(
                    str(error_payload.get("message") or "OpenAI Codex request failed.")
                )
            raise ValueError(str(error_payload))

        result = response.get("result") if isinstance(response, dict) else None
        return result if isinstance(result, dict) else {}

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self.process.stdin is None:
            raise RuntimeError("OpenAI Codex app-server stdin is unavailable.")

        payload = {"method": method, "params": params or {}}
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def respond(self, message_id: Any, result: dict[str, Any] | None = None) -> None:
        if self.process.stdin is None:
            raise RuntimeError("OpenAI Codex app-server stdin is unavailable.")

        payload = {"id": message_id, "result": result or {}}
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def respond_error(self, message_id: Any, *, code: int, message: str) -> None:
        if self.process.stdin is None:
            raise RuntimeError("OpenAI Codex app-server stdin is unavailable.")

        payload = {"id": message_id, "error": {"code": code, "message": message}}
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def next_event(
        self,
        *,
        timeout: float = OPENAI_CODEX_TURN_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        event = await asyncio.wait_for(self._notifications.get(), timeout=timeout)
        if event is None:
            raise RuntimeError(self.stderr_text or "OpenAI Codex app-server stopped.")
        return event

    async def close(self) -> None:
        if self.process.stdin is not None and not self.process.stdin.is_closing():
            self.process.stdin.close()

        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

        for task in (self._stdout_task, self._stderr_task):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


@dataclass(kw_only=True)
class OpenAICodexReqChat(BaseProviderReq):
    auth_json: str
    http_client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.auth_json = _normalize_auth_json(self.auth_json)
        self.openai_codex_auth_json = self.auth_json

    def validate_request(self) -> None:
        if self.file_uuids or self.file_hashes or has_file_attachments(self.messages):
            raise ValueError(
                "OpenAI Codex models currently support only text and image inputs. "
                "PDF and generic file attachments are not supported yet."
            )


def _resolve_runtime_bin() -> Path:
    runtime_dir = Path(__file__).resolve().parents[1] / "openai_codex_runtime"
    runtime_bin = runtime_dir / "node_modules" / ".bin" / "codex"
    if not runtime_bin.is_file():
        raise ValueError(
            "OpenAI Codex runtime is unavailable. Install dependencies in "
            "api/app/openai_codex_runtime first."
        )
    return runtime_bin


def _normalize_auth_json(raw_value: str) -> str:
    try:
        payload = json.loads(raw_value.translate(JSON_WHITESPACE_TRANSLATION))
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI Codex auth.json must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("OpenAI Codex auth.json must be a JSON object.")

    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _parse_jwt_claims(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3 or not parts[1]:
        return None

    try:
        padded_payload = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = base64.urlsafe_b64decode(padded_payload.encode("ascii"))
        claims = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    return claims if isinstance(claims, dict) else None


def _extract_account_id_from_claims(claims: dict[str, Any] | None) -> str | None:
    if not isinstance(claims, dict):
        return None

    root_account_id = str(claims.get("chatgpt_account_id") or "").strip()
    if root_account_id:
        return root_account_id

    auth_claims = claims.get("https://api.openai.com/auth")
    if isinstance(auth_claims, dict):
        nested_account_id = str(auth_claims.get("chatgpt_account_id") or "").strip()
        if nested_account_id:
            return nested_account_id

    organizations = claims.get("organizations")
    if isinstance(organizations, list) and organizations:
        first_org = organizations[0]
        if isinstance(first_org, dict):
            organization_id = str(first_org.get("id") or "").strip()
            if organization_id:
                return organization_id
    return None


def _extract_account_id_from_tokens(tokens: dict[str, Any]) -> str | None:
    for key in ("id_token", "access_token"):
        token = str(tokens.get(key) or "").strip()
        if not token:
            continue
        account_id = _extract_account_id_from_claims(_parse_jwt_claims(token))
        if account_id:
            return account_id
    return None


def _extract_jwt_expiration_ms(token: str) -> int | None:
    claims = _parse_jwt_claims(token)
    if not claims:
        return None
    exp = claims.get("exp")
    if isinstance(exp, (int, float)):
        return int(exp * 1000)
    return None


def _build_codex_auth_json_from_tokens(
    tokens: dict[str, Any],
    *,
    account_id: str | None = None,
) -> str:
    access_token = str(tokens.get("access_token") or "").strip()
    id_token = str(tokens.get("id_token") or access_token).strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        raise ValueError("OpenAI Codex OAuth response did not include usable tokens.")

    resolved_account_id = account_id or _extract_account_id_from_tokens(tokens)
    auth_payload: dict[str, Any] = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {
            "id_token": id_token,
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        "last_refresh": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if resolved_account_id:
        auth_payload["tokens"]["account_id"] = resolved_account_id
    return _normalize_auth_json(json.dumps(auth_payload))


def _build_codex_auth_json_from_api_key(api_key: str) -> str:
    normalized_api_key = api_key.strip()
    if not normalized_api_key:
        raise ValueError("OpenAI Codex API key is required.")
    return _normalize_auth_json(
        json.dumps(
            {
                "auth_mode": "apikey",
                "OPENAI_API_KEY": normalized_api_key,
            }
        )
    )


def _coerce_openai_codex_auth_json(normalized_auth_json: str) -> str:
    try:
        payload = json.loads(normalized_auth_json)
    except json.JSONDecodeError:
        return normalized_auth_json

    if not isinstance(payload, dict):
        return normalized_auth_json
    if payload.get("type") == "api":
        return _build_codex_auth_json_from_api_key(str(payload.get("key") or ""))
    if payload.get("type") == "oauth":
        tokens = _extract_codex_auth_tokens(normalized_auth_json)
        if tokens:
            return _build_codex_auth_json_from_tokens(tokens)
    return normalized_auth_json


def _extract_codex_auth_tokens(normalized_auth_json: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(normalized_auth_json)
    except json.JSONDecodeError:
        return None

    tokens = payload.get("tokens")
    if isinstance(tokens, dict):
        return tokens

    if payload.get("type") == "oauth":
        refresh = str(payload.get("refresh") or "").strip()
        access = str(payload.get("access") or "").strip()
        if refresh and access:
            return {
                "id_token": str(payload.get("id_token") or ""),
                "access_token": access,
                "refresh_token": refresh,
                "account_id": str(payload.get("accountId") or payload.get("account_id") or ""),
            }
    return None


def _codex_auth_needs_refresh(normalized_auth_json: str, *, force: bool = False) -> bool:
    if force:
        return True
    tokens = _extract_codex_auth_tokens(normalized_auth_json)
    if not tokens:
        return False
    access_token = str(tokens.get("access_token") or "").strip()
    if not access_token:
        return True
    expires_ms = _extract_jwt_expiration_ms(access_token)
    if expires_ms is None:
        return False
    return expires_ms <= int((time.time() + OPENAI_CODEX_REFRESH_MARGIN_SECONDS) * 1000)


async def _exchange_openai_codex_code(
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OPENAI_CODEX_ISSUER}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": OPENAI_CODEX_CLIENT_ID,
                "code_verifier": code_verifier,
            },
        )
    if response.status_code >= 400:
        raise ValueError(f"OpenAI Codex token exchange failed: {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OpenAI Codex token exchange returned an invalid response.")
    return payload


async def _refresh_openai_codex_auth(normalized_auth_json: str) -> str:
    tokens = _extract_codex_auth_tokens(normalized_auth_json)
    refresh_token = str(tokens.get("refresh_token") or "").strip() if tokens else ""
    if not refresh_token:
        return normalized_auth_json

    account_id = str(tokens.get("account_id") or "").strip() if tokens else None
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OPENAI_CODEX_ISSUER}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": OPENAI_CODEX_CLIENT_ID,
            },
        )
    if response.status_code >= 400:
        raise ValueError(f"OpenAI Codex token refresh failed: {response.status_code}")

    refreshed_tokens = response.json()
    if not isinstance(refreshed_tokens, dict):
        raise ValueError("OpenAI Codex token refresh returned an invalid response.")
    if not refreshed_tokens.get("refresh_token"):
        refreshed_tokens["refresh_token"] = refresh_token
    if not refreshed_tokens.get("id_token") and tokens and tokens.get("id_token"):
        refreshed_tokens["id_token"] = tokens.get("id_token")
    return _build_codex_auth_json_from_tokens(refreshed_tokens, account_id=account_id or None)


async def _refresh_openai_codex_auth_if_needed(
    normalized_auth_json: str,
    *,
    force: bool = False,
) -> str:
    normalized_auth_json = _coerce_openai_codex_auth_json(normalized_auth_json)
    if not _codex_auth_needs_refresh(normalized_auth_json, force=force):
        return normalized_auth_json

    tokens = _extract_codex_auth_tokens(normalized_auth_json)
    refresh_token = str(tokens.get("refresh_token") or "").strip() if tokens else ""
    if not refresh_token:
        return normalized_auth_json

    task = _openai_codex_refresh_tasks.get(refresh_token)
    if task is None:
        task = asyncio.create_task(_refresh_openai_codex_auth(normalized_auth_json))
        _openai_codex_refresh_tasks[refresh_token] = task
        task.add_done_callback(lambda _: _openai_codex_refresh_tasks.pop(refresh_token, None))
    return await task


async def _validate_openai_codex_auth_tokens(normalized_auth_json: str) -> str:
    normalized_auth_json = _coerce_openai_codex_auth_json(normalized_auth_json)
    try:
        payload = json.loads(normalized_auth_json)
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict) and str(payload.get("OPENAI_API_KEY") or "").strip():
        await _probe_openai_codex_auth(normalized_auth_json)
        return normalized_auth_json

    refreshed_auth_json = await _refresh_openai_codex_auth_if_needed(
        normalized_auth_json,
        force=True,
    )
    tokens = _extract_codex_auth_tokens(refreshed_auth_json)
    if not tokens or not str(tokens.get("access_token") or "").strip():
        raise ValueError("OpenAI Codex credentials do not contain OAuth access tokens.")
    await _probe_openai_codex_auth(refreshed_auth_json)
    return refreshed_auth_json


async def validate_openai_codex_oauth_auth_json(auth_json: str) -> str:
    return await _validate_openai_codex_auth_tokens(_normalize_auth_json(auth_json))


def _cleanup_openai_codex_oauth_sessions() -> None:
    now = time.time()
    expired_device_sessions = [
        session_id
        for session_id, session in _openai_codex_device_sessions.items()
        if session.expires_at <= now
    ]
    for session_id in expired_device_sessions:
        _openai_codex_device_sessions.pop(session_id, None)


def _openai_codex_device_session_redis_key(session_id: str) -> str:
    return f"{OPENAI_CODEX_DEVICE_SESSION_REDIS_PREFIX}{session_id}"


def _serialize_openai_codex_device_session(session: OpenAICodexDeviceAuthSession) -> str:
    return json.dumps(
        {
            "session_id": session.session_id,
            "device_auth_id": session.device_auth_id,
            "user_code": session.user_code,
            "interval_seconds": session.interval_seconds,
            "expires_at": session.expires_at,
        },
        separators=(",", ":"),
    )


def _deserialize_openai_codex_device_session(
    raw_value: str,
) -> OpenAICodexDeviceAuthSession | None:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    session_id = str(payload.get("session_id") or "").strip()
    device_auth_id = str(payload.get("device_auth_id") or "").strip()
    user_code = str(payload.get("user_code") or "").strip()
    if not session_id or not device_auth_id or not user_code:
        return None

    try:
        interval_seconds = max(int(payload.get("interval_seconds") or 5), 1)
        expires_at = float(payload.get("expires_at") or 0)
    except (TypeError, ValueError):
        return None

    return OpenAICodexDeviceAuthSession(
        session_id=session_id,
        device_auth_id=device_auth_id,
        user_code=user_code,
        interval_seconds=interval_seconds,
        expires_at=expires_at,
    )


async def _store_openai_codex_device_session(
    session: OpenAICodexDeviceAuthSession,
    redis_manager: RedisManager | None,
) -> None:
    if redis_manager is None:
        _openai_codex_device_sessions[session.session_id] = session
        return

    ttl_seconds = max(int(session.expires_at - time.time()), 1)
    await redis_manager.client.set(
        _openai_codex_device_session_redis_key(session.session_id),
        _serialize_openai_codex_device_session(session),
        ex=ttl_seconds,
    )


async def _get_openai_codex_device_session(
    session_id: str,
    redis_manager: RedisManager | None,
) -> OpenAICodexDeviceAuthSession | None:
    if redis_manager is None:
        _cleanup_openai_codex_oauth_sessions()
        return _openai_codex_device_sessions.get(session_id)

    key = _openai_codex_device_session_redis_key(session_id)
    raw_value = await redis_manager.client.get(key)
    if not raw_value:
        return None

    session = _deserialize_openai_codex_device_session(str(raw_value))
    if session is None or session.expires_at <= time.time():
        await redis_manager.client.delete(key)
        return None
    return session


async def _delete_openai_codex_device_session(
    session_id: str,
    redis_manager: RedisManager | None,
) -> None:
    if redis_manager is None:
        _openai_codex_device_sessions.pop(session_id, None)
        return

    await redis_manager.client.delete(_openai_codex_device_session_redis_key(session_id))


async def start_openai_codex_device_oauth(
    redis_manager: RedisManager | None = None,
) -> dict[str, Any]:
    _cleanup_openai_codex_oauth_sessions()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OPENAI_CODEX_ISSUER}/api/accounts/deviceauth/usercode",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "meridian/1.0.0",
            },
            json={"client_id": OPENAI_CODEX_CLIENT_ID},
        )
    if response.status_code >= 400:
        raise ValueError("Failed to start OpenAI Codex device authorization.")

    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OpenAI Codex device authorization returned an invalid response.")
    device_auth_id = str(payload.get("device_auth_id") or "").strip()
    user_code = str(payload.get("user_code") or "").strip()
    if not device_auth_id or not user_code:
        raise ValueError("OpenAI Codex device authorization did not return a user code.")

    interval_seconds = max(int(str(payload.get("interval") or "5")), 1)
    session_id = uuid.uuid4().hex
    session = OpenAICodexDeviceAuthSession(
        session_id=session_id,
        device_auth_id=device_auth_id,
        user_code=user_code,
        interval_seconds=interval_seconds,
        expires_at=time.time() + OPENAI_CODEX_OAUTH_TIMEOUT_SECONDS,
    )
    await _store_openai_codex_device_session(session, redis_manager)
    return {
        "session_id": session_id,
        "verification_url": OPENAI_CODEX_DEVICE_VERIFICATION_URL,
        "user_code": user_code,
        "interval_seconds": interval_seconds,
        "instructions": f"Open {OPENAI_CODEX_DEVICE_VERIFICATION_URL} and enter code {user_code}.",
    }


async def complete_openai_codex_device_oauth(
    session_id: str,
    redis_manager: RedisManager | None = None,
) -> str:
    session = await _get_openai_codex_device_session(session_id, redis_manager)
    if session is None:
        raise ValueError("OpenAI Codex device sign-in session expired. Start sign-in again.")

    while time.time() < session.expires_at:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OPENAI_CODEX_ISSUER}/api/accounts/deviceauth/token",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "meridian/1.0.0",
                },
                json={
                    "device_auth_id": session.device_auth_id,
                    "user_code": session.user_code,
                },
            )

        if response.status_code < 400:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("OpenAI Codex device token response was invalid.")
            authorization_code = str(payload.get("authorization_code") or "").strip()
            code_verifier = str(payload.get("code_verifier") or "").strip()
            if not authorization_code or not code_verifier:
                raise ValueError(
                    "OpenAI Codex device sign-in did not return an authorization code."
                )
            await _delete_openai_codex_device_session(session_id, redis_manager)
            tokens = await _exchange_openai_codex_code(
                code=authorization_code,
                redirect_uri=OPENAI_CODEX_DEVICE_REDIRECT_URI,
                code_verifier=code_verifier,
            )
            return _build_codex_auth_json_from_tokens(tokens)

        if response.status_code not in {403, 404}:
            await _delete_openai_codex_device_session(session_id, redis_manager)
            raise ValueError(f"OpenAI Codex device sign-in failed: {response.status_code}")

        await asyncio.sleep(session.interval_seconds + OPENAI_CODEX_DEVICE_POLL_SAFETY_SECONDS)

    await _delete_openai_codex_device_session(session_id, redis_manager)
    raise ValueError("OpenAI Codex device sign-in timed out. Start sign-in again.")


def _build_output_schema(schema: type[BaseModel]) -> dict[str, Any]:
    json_schema = schema.model_json_schema()
    sanitized = _sanitize_output_schema_node({"type": "object", **json_schema})
    if not isinstance(sanitized, dict):
        raise TypeError("OpenAI Codex output schema must be a JSON object.")
    return sanitized


def _sanitize_output_schema_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitize_output_schema_node(item) for item in node]

    if not isinstance(node, dict):
        return node

    sanitized = {key: _sanitize_output_schema_node(value) for key, value in node.items()}
    node_type = sanitized.get("type")
    is_object_node = node_type == "object" or (
        isinstance(node_type, list) and "object" in node_type
    )
    properties = sanitized.get("properties")
    if is_object_node or "properties" in sanitized:
        sanitized.setdefault("additionalProperties", False)
    if isinstance(properties, dict):
        sanitized["required"] = list(properties.keys())
    return sanitized


def _extract_image_urls(content: Any) -> list[str]:
    if not isinstance(content, list):
        return []

    image_urls: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != MessageContentTypeEnum.image_url.value:
            continue
        image_payload = item.get("image_url")
        if not isinstance(image_payload, dict):
            continue
        image_url = str(image_payload.get("url") or "").strip()
        if image_url:
            image_urls.append(image_url)
    return image_urls


def _summarize_tool_calls(tool_calls: Any) -> str:
    if not isinstance(tool_calls, list) or not tool_calls:
        return ""

    normalized_tool_calls: list[str] = []
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue

        function_payload = tool_call.get("function")
        if not isinstance(function_payload, dict):
            continue

        function_name = str(function_payload.get("name") or "tool").strip() or "tool"
        arguments = function_payload.get("arguments")
        if isinstance(arguments, str):
            arguments_text = arguments.strip() or "{}"
        else:
            arguments_text = json.dumps(arguments or {}, indent=2)
        normalized_tool_calls.append(f"- {function_name}: {arguments_text}")

    return "\n".join(normalized_tool_calls)


def _extract_reasoning_item_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""

    parts: list[str] = []

    summary = item.get("summary")
    if isinstance(summary, list):
        for entry in summary:
            if isinstance(entry, dict):
                text = str(entry.get("text") or "").strip()
            else:
                text = str(entry or "").strip()
            if text:
                parts.append(text)

    content = item.get("content")
    if isinstance(content, list):
        for entry in content:
            if isinstance(entry, dict):
                text = str(entry.get("text") or "").strip()
            else:
                text = str(entry or "").strip()
            if text:
                parts.append(text)

    return "\n\n".join(parts)


def _extract_data_uri_payload(data_uri: str) -> tuple[bytes, str]:
    try:
        header, encoded = data_uri.split(",", 1)
    except ValueError as exc:
        raise ValueError("OpenAI Codex image input contains an invalid data URI.") from exc

    encoded = re.sub(r"\s+", "", encoded)
    if len(encoded) > OPENAI_CODEX_MAX_DATA_URI_BASE64_CHARS:
        raise ValueError("OpenAI Codex image input exceeds the maximum supported data URI size.")

    try:
        payload_bytes = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("OpenAI Codex image input contains invalid base64 data.") from exc

    if len(payload_bytes) > OPENAI_CODEX_MAX_DATA_URI_BYTES:
        raise ValueError("OpenAI Codex image input exceeds the maximum supported data URI size.")

    mime_type = "image/png"
    if ";" in header and ":" in header:
        mime_type = header.split(":", 1)[1].split(";", 1)[0].strip() or mime_type
    extension = mimetypes.guess_extension(mime_type) or ".png"
    return payload_bytes, extension


async def _write_local_image_input(
    image_url: str,
    *,
    input_dir: Path,
    image_index: int,
    http_client: Optional[httpx.AsyncClient],
) -> Path:
    if image_url.startswith("data:"):
        image_bytes, extension = _extract_data_uri_payload(image_url)
    else:
        if http_client is None:
            raise ValueError(
                "OpenAI Codex image inputs require an HTTP client when using remote image URLs."
            )
        response = await http_client.get(image_url)
        response.raise_for_status()
        image_bytes = response.content
        content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip()
        extension = mimetypes.guess_extension(content_type or "image/png") or ".png"

    file_path = input_dir / f"input-image-{image_index}{extension}"
    file_path.write_bytes(image_bytes)
    return file_path


@dataclass(frozen=True)
class OpenAICodexGeneratedImage:
    image_bytes: bytes
    extension: str
    model: str


def _extract_generated_image_payload(item: dict[str, Any]) -> tuple[bytes, str] | None:
    saved_path = item.get("savedPath") or item.get("saved_path")
    if saved_path:
        image_path = Path(str(saved_path))
        if image_path.is_file():
            extension = image_path.suffix.lstrip(".").lower() or "png"
            return image_path.read_bytes(), extension

    result = str(item.get("result") or "").strip()
    if not result:
        return None

    extension = "png"
    if result.startswith("data:"):
        header, result = result.split(",", 1)
        if "jpeg" in header or "jpg" in header:
            extension = "jpg"
        elif "webp" in header:
            extension = "webp"

    return base64.b64decode(re.sub(r"\s+", "", result), validate=True), extension


def _extract_completed_image_generation_item(event: dict[str, Any]) -> dict[str, Any] | None:
    if str(event.get("method") or "") != "item/completed":
        return None

    params = event.get("params")
    if not isinstance(params, dict):
        return None
    item = params.get("item")
    if not isinstance(item, dict):
        return None

    item_type = str(item.get("type") or "").strip()
    if item_type not in {"ImageGeneration", "imageGeneration", "image_generation"}:
        return None

    return item


def _summarize_codex_image_generation_item(item: dict[str, Any]) -> dict[str, Any]:
    result = str(item.get("result") or "")
    saved_path = item.get("savedPath") or item.get("saved_path")
    summary: dict[str, Any] = {
        "id": item.get("id"),
        "type": item.get("type"),
        "status": item.get("status"),
        "has_result": bool(result),
        "result_length": len(result),
        "has_saved_path": bool(saved_path),
        "saved_path_exists": Path(str(saved_path)).is_file() if saved_path else False,
        "keys": sorted(str(key) for key in item.keys()),
    }
    for key in ("error", "message", "failure", "revisedPrompt", "revised_prompt"):
        value = item.get(key)
        if value:
            summary[key] = str(value)[:500]
    return summary


def _summarize_codex_turn_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    summarized_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        summarized_items.append(
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "status": item.get("status"),
                "keys": sorted(str(key) for key in item.keys()),
            }
        )
    return summarized_items


def _find_completed_image_generation_item(items: Any) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type in {"ImageGeneration", "imageGeneration", "image_generation"}:
            return item
    return None


async def _build_image_generation_turn_input(
    message_content: str | list[dict[str, Any]],
    *,
    runtime_context: OpenAICodexRuntimeContext,
    aspect_ratio: str,
    resolution: str,
    http_client: Optional[httpx.AsyncClient],
) -> list[dict[str, Any]]:
    content_items = (
        [{"type": "text", "text": message_content}]
        if isinstance(message_content, str)
        else message_content
    )
    input_items: list[dict[str, Any]] = []
    image_index = 0

    for item in content_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            input_items.append({"type": "text", "text": str(item.get("text") or "")})
            continue
        if item.get("type") != "image_url":
            continue
        image_payload = item.get("image_url")
        if not isinstance(image_payload, dict):
            continue
        image_url = str(image_payload.get("url") or "").strip()
        if not image_url:
            continue
        image_index += 1
        local_image_path = await _write_local_image_input(
            image_url,
            input_dir=runtime_context.input_dir,
            image_index=image_index,
            http_client=http_client,
        )
        input_items.append({"type": "localImage", "path": str(local_image_path)})

    prompt_suffix = (
        "\n\nUse the built-in image_generation tool exactly once. "
        "Generate one PNG image only. "
        f"Aspect ratio: {aspect_ratio}. Target resolution: {resolution}. "
        "Do not create SVG, HTML, code, or text-only output."
    )
    if input_items and input_items[0].get("type") == "text":
        input_items[0]["text"] = f"{input_items[0].get('text')}{prompt_suffix}"
    else:
        input_items.insert(0, {"type": "text", "text": prompt_suffix.strip()})

    return input_items


def _build_codex_config_toml(
    model_instructions_path: Path | None = None,
    *,
    enable_image_generation: bool = False,
) -> str:
    config_toml = OPENAI_CODEX_CONFIG_TOML
    if enable_image_generation:
        config_toml = config_toml.replace(
            "[features]\n",
            "[features]\nimage_generation = true\n",
            1,
        ).replace(
            "[tools.image_generation]\nenabled = false",
            "[tools.image_generation]\nenabled = true",
            1,
        )
    if model_instructions_path is not None:
        config_toml = (
            f"model_instructions_file = {json.dumps(str(model_instructions_path))}\n\n"
            f"{config_toml}"
        )
    return config_toml


def _sanitize_model_instructions(raw_instructions: str) -> str:
    return sanitize_external_tool_references(raw_instructions)


def _extract_system_instructions(messages: list[dict[str, Any]]) -> str:
    instructions: list[str] = []

    for message in messages:
        if normalize_role_value(message.get("role")) != "system":
            continue

        text_content = extract_text_content(message.get("content"))
        if text_content:
            instructions.append(text_content)

    return _sanitize_model_instructions("\n\n".join(part for part in instructions if part))


def _build_runtime_context(
    auth_json: str,
    *,
    model_instructions: str | None = None,
    enable_image_generation: bool = False,
) -> OpenAICodexRuntimeContext:
    layout = build_runtime_directory_layout(
        OPENAI_CODEX_RUNTIME_ROOT,
        prefix=OPENAI_CODEX_RUNTIME_PREFIX,
        ttl_seconds=OPENAI_CODEX_RUNTIME_TTL_SECONDS,
        provider_label="OpenAI Codex",
    )
    input_dir = ensure_private_directory(layout.root_dir / "input")
    codex_home = ensure_private_directory(layout.home_dir / ".codex")
    auth_json_path = codex_home / "auth.json"
    config_toml_path = codex_home / "config.toml"
    model_instructions_path = codex_home / "meridian_instructions.md"

    write_private_file(auth_json_path, auth_json)
    normalized_model_instructions = (model_instructions or "").strip()
    if normalized_model_instructions:
        write_private_file(model_instructions_path, normalized_model_instructions + "\n")
        write_private_file(
            config_toml_path,
            _build_codex_config_toml(
                model_instructions_path,
                enable_image_generation=enable_image_generation,
            ),
        )
    else:
        write_private_file(
            config_toml_path,
            _build_codex_config_toml(enable_image_generation=enable_image_generation),
        )

    return OpenAICodexRuntimeContext(
        root_dir=layout.root_dir,
        cwd=layout.cwd,
        env={
            "HOME": str(layout.home_dir),
            "CODEX_HOME": str(codex_home),
            "XDG_CONFIG_HOME": str(layout.config_dir),
            "XDG_DATA_HOME": str(layout.data_dir),
            "XDG_STATE_HOME": str(layout.state_dir),
            "XDG_CACHE_HOME": str(layout.cache_dir),
            "NO_COLOR": "1",
        },
        codex_home=codex_home,
        auth_json_path=auth_json_path,
        model_instructions_path=(
            model_instructions_path if normalized_model_instructions else None
        ),
        input_dir=input_dir,
    )


def _cleanup_runtime_context(runtime_context: OpenAICodexRuntimeContext) -> None:
    cleanup_runtime_dir(runtime_context.root_dir, provider_label="OpenAI Codex")


async def _persist_refreshed_auth_json(
    *,
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    current_auth_json: str,
    refreshed_auth_json: str | None,
) -> None:
    await persist_refreshed_provider_token(
        pg_engine=pg_engine,
        user_id=user_id,
        provider_key=OPENAI_CODEX_PROVIDER_KEY,
        current_value=current_auth_json,
        refreshed_value=refreshed_auth_json,
        normalize_fn=_normalize_auth_json,
        value_label="OpenAI Codex auth.json",
    )


async def _start_codex_client(
    runtime_context: OpenAICodexRuntimeContext,
) -> _CodexAppServerClient:
    runtime_bin = _resolve_runtime_bin()

    try:
        process = await asyncio.create_subprocess_exec(
            str(runtime_bin),
            "app-server",
            "--listen",
            "stdio://",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(runtime_context.cwd),
            env=build_subprocess_env(runtime_context.env),
            limit=OPENAI_CODEX_STDIO_LIMIT_BYTES,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "OpenAI Codex runtime is unavailable. Ensure Node.js and the runtime npm package "
            "are installed."
        ) from exc

    client = _CodexAppServerClient(process)
    try:
        await client.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "meridian",
                    "title": "Meridian",
                    "version": "1.0.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        await client.notify("initialized", {})
    except Exception:
        await client.close()
        raise
    return client


async def _ensure_openai_auth(
    client: _CodexAppServerClient,
    *,
    refresh_token: bool,
) -> dict[str, Any]:
    result = await client.request("account/read", {"refreshToken": refresh_token})
    account_payload = result.get("account")
    requires_openai_auth = bool(result.get("requiresOpenaiAuth", False))
    if account_payload or not requires_openai_auth:
        return result

    raise ValueError(
        "OpenAI Codex authentication is invalid or expired. Paste a fresh ~/.codex/auth.json file."
    )


def _is_codex_auth_stderr(stderr_text: str) -> bool:
    normalized_stderr = stderr_text.lower()
    return (
        "failed to refresh token" in normalized_stderr
        or "refresh_token_reused" in normalized_stderr
        or "your refresh token has already been used" in normalized_stderr
    )


def _codex_auth_error_message() -> str:
    return (
        "OpenAI Codex authentication failed while refreshing token. "
        "Sign in again and update your Codex auth.json before generating images."
    )


async def list_openai_codex_models(
    auth_json: str,
    *,
    user_id: str | None = None,
    pg_engine: SQLAlchemyAsyncEngine | None = None,
    models_dev_catalog: Any | None = None,
) -> list[Any]:
    normalized_auth_json = _normalize_auth_json(auth_json)
    original_auth_json = normalized_auth_json
    normalized_auth_json = await _validate_openai_codex_auth_tokens(normalized_auth_json)
    try:
        try:
            return await get_models_dev_openai_codex_models(models_dev_catalog)
        except Exception:
            logger.warning(
                "OpenAI Codex models.dev catalog unavailable; omitting Codex models.",
                exc_info=True,
            )
            return []
    finally:
        if user_id and pg_engine is not None:
            refreshed_auth_json = normalized_auth_json
            await _persist_refreshed_auth_json(
                user_id=user_id,
                pg_engine=pg_engine,
                current_auth_json=original_auth_json,
                refreshed_auth_json=refreshed_auth_json,
            )


def _normalize_reasoning_effort(config: Any, is_title_generation: bool) -> str | None:
    if is_title_generation or bool(getattr(config, "exclude_reasoning", False)):
        return None

    raw_effort = str(getattr(config, "reasoning_effort", "") or "").strip().lower()
    if raw_effort in {"low", "medium", "high"}:
        return raw_effort
    if raw_effort in {"max", "xhigh"}:
        return "high"
    return None


def _build_dynamic_tools(selected_tools: list[ToolEnum]) -> list[dict[str, Any]]:
    dynamic_tools: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for tool_definition in get_openrouter_tools(selected_tools):
        function_payload = tool_definition.get("function")
        if not isinstance(function_payload, dict):
            continue

        tool_name = str(function_payload.get("name") or "").strip()
        if not tool_name or tool_name in seen_names:
            continue

        input_schema = function_payload.get("parameters")
        if not isinstance(input_schema, dict):
            continue

        seen_names.add(tool_name)
        dynamic_tools.append(
            {
                "name": tool_name,
                "description": str(function_payload.get("description") or "").strip(),
                "inputSchema": input_schema,
            }
        )

    return dynamic_tools


def _build_dynamic_tool_result(
    model_context_payload: str,
    *,
    success: bool,
) -> dict[str, Any]:
    return {
        "contentItems": [{"type": "inputText", "text": model_context_payload}],
        "success": success,
    }


def _build_pending_assistant_message(
    *,
    tool_name: str,
    tool_call_id: str,
    arguments: dict[str, Any],
    assistant_text: str,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "tool_calls": [
            {
                "type": "function",
                "id": tool_call_id,
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments, separators=(",", ":")),
                },
            }
        ],
    }
    if assistant_text:
        message["content"] = assistant_text
    return message


async def _persist_tool_call(
    *,
    req: OpenAICodexReqChat,
    tool_call_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    normalized_result: Any,
    model_context_payload: str,
    status: ToolCallStatusEnum,
    duration_ms: int | None,
) -> str:
    public_tool_call_id = tool_call_id or f"openai-codex-tool-{uuid.uuid4().hex}"
    if req.graph_id and req.node_id and req.user_id:
        try:
            persisted_tool_call = await create_tool_call(
                req.pg_engine,
                user_id=req.user_id,
                graph_id=req.graph_id,
                node_id=req.node_id,
                model_id=req.model_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                status=status,
                duration_ms=duration_ms,
                arguments=arguments,
                result=normalized_result,
                model_context_payload=model_context_payload,
            )
            if persisted_tool_call.id is not None:
                public_tool_call_id = str(persisted_tool_call.id)
        except Exception:
            logger.warning(
                "Failed to persist OpenAI Codex tool call %s for node %s",
                tool_name,
                req.node_id,
                exc_info=True,
            )

    return public_tool_call_id


def _parse_dynamic_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _normalize_codex_usage_data(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    usage_breakdown = payload.get("last")
    if not isinstance(usage_breakdown, dict):
        usage_breakdown = payload.get("total")
    if not isinstance(usage_breakdown, dict):
        return None

    prompt_tokens = int(usage_breakdown.get("inputTokens", 0) or 0)
    completion_tokens = int(usage_breakdown.get("outputTokens", 0) or 0)
    cached_tokens = int(usage_breakdown.get("cachedInputTokens", 0) or 0)
    reasoning_tokens = int(usage_breakdown.get("reasoningOutputTokens", 0) or 0)
    total_tokens = int(usage_breakdown.get("totalTokens", 0) or 0)
    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens

    if not any(
        (
            prompt_tokens,
            completion_tokens,
            cached_tokens,
            reasoning_tokens,
            total_tokens,
        )
    ):
        return None

    return {
        "cost": 0.0,
        "is_byok": False,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_tokens_details": {"cached_tokens": cached_tokens},
        "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }


@dataclass
class _OpenAICodexTurnState:
    thread_id: str = ""
    turn_id: str = ""
    awaiting_user_input: bool = False
    commentary_item_ids: set[str] = field(default_factory=set)
    reasoning_item_ids: set[str] = field(default_factory=set)
    reasoning_summary_indices: dict[str, set[int]] = field(default_factory=dict)
    thinking_state: ThinkingState = field(default_factory=ThinkingState)


class _OpenAICodexOutputAssembler:
    def __init__(
        self,
        req: OpenAICodexReqChat,
        state: _OpenAICodexTurnState,
        on_chunk: Callable[[str], Awaitable[None]] | None,
    ) -> None:
        self.req = req
        self.state = state
        self.on_chunk = on_chunk
        self.emitted_text_by_item_id: dict[str, str] = {}
        self.emitted_commentary_by_item_id: dict[str, str] = {}
        self.final_text_parts: list[str] = []
        self.commentary_text_parts: list[str] = []
        self.feedback_parts: list[str] = []

    async def finalize_stream(self) -> None:
        closing_chunk = self.state.thinking_state.close_chunk()
        if closing_chunk and self.on_chunk is not None:
            await self.on_chunk(closing_chunk)

    async def close_thinking(self) -> None:
        closing_chunk = self.state.thinking_state.close_chunk()
        if closing_chunk and self.on_chunk is not None:
            await self.on_chunk(closing_chunk)

    async def emit_commentary(self, item_id: str, text: str) -> None:
        if not text:
            return
        self.emitted_commentary_by_item_id[item_id] = (
            self.emitted_commentary_by_item_id.get(item_id, "") + text
        )
        self.commentary_text_parts.append(text)
        if self.on_chunk is not None:
            opening_chunk = self.state.thinking_state.open_chunk()
            if opening_chunk:
                await self.on_chunk(opening_chunk)
            await self.on_chunk(text)

    async def emit_text(self, item_id: str, text: str) -> None:
        if not text:
            return
        await self.close_thinking()
        self.emitted_text_by_item_id[item_id] = self.emitted_text_by_item_id.get(item_id, "") + text
        self.final_text_parts.append(text)
        if self.on_chunk is not None:
            await self.on_chunk(text)

    async def emit_feedback(self, text: str) -> None:
        if not text:
            return
        await self.close_thinking()
        self.feedback_parts.append(text)
        if self.on_chunk is not None:
            await self.on_chunk(text)

    async def emit_reasoning_summary_break(self, item_id: str) -> None:
        await self.emit_commentary(item_id, "\n\n")

    async def sync_completed_reasoning(self, item_id: str, item_text: str) -> None:
        if not item_text:
            return
        already_emitted = self.emitted_commentary_by_item_id.get(item_id, "")
        if item_text.startswith(already_emitted):
            await self.emit_commentary(item_id, item_text[len(already_emitted) :])
        elif not already_emitted:
            await self.emit_commentary(item_id, item_text)

    async def sync_completed_agent_message(
        self,
        item_id: str,
        item_text: str,
        *,
        is_commentary: bool,
    ) -> None:
        if not item_text:
            return
        if is_commentary:
            already_emitted = self.emitted_commentary_by_item_id.get(item_id, "")
            if item_text.startswith(already_emitted):
                await self.emit_commentary(item_id, item_text[len(already_emitted) :])
            elif not already_emitted:
                await self.emit_commentary(item_id, item_text)
            return

        already_emitted = self.emitted_text_by_item_id.get(item_id, "")
        if item_text.startswith(already_emitted):
            await self.emit_text(item_id, item_text[len(already_emitted) :])
        elif not already_emitted:
            await self.emit_text(item_id, item_text)

    def build_output(self) -> str:
        commentary_text = "".join(self.commentary_text_parts).strip()
        final_text = "".join(self.final_text_parts).strip()
        feedback_output = "".join(self.feedback_parts)
        commentary_output = (
            f"[THINK]\n{commentary_text}\n[!THINK]\n"
            if commentary_text and self.req.schema is None
            else ""
        )
        if feedback_output or commentary_output or final_text:
            return feedback_output + commentary_output + final_text
        if self.state.awaiting_user_input:
            return ""
        raise ValueError("OpenAI Codex completed without returning any text.")

    def assistant_text(self) -> str:
        return "".join(self.final_text_parts).strip()


class _OpenAICodexToolCallBridge:
    def __init__(
        self,
        req: OpenAICodexReqChat,
        state: _OpenAICodexTurnState,
        output: _OpenAICodexOutputAssembler,
        *,
        redis_manager: RedisManager | None,
        pending_tool_call_id_sink: dict[str, Any] | None,
    ) -> None:
        self.req = req
        self.state = state
        self.output = output
        self.redis_manager = redis_manager
        self.pending_tool_call_id_sink = pending_tool_call_id_sink

    async def handle(
        self, client: _CodexAppServerClient, params_dict: dict[str, Any], request_id: Any
    ) -> None:
        tool_name = str(params_dict.get("tool") or "").strip()
        tool_call_id = str(params_dict.get("callId") or "").strip() or None
        resolved_tool_call_id = tool_call_id or f"openai-codex-call-{uuid.uuid4().hex}"
        arguments = _parse_dynamic_tool_arguments(params_dict.get("arguments"))
        runtime = get_tool_runtime(tool_name)
        handler = TOOL_HANDLERS_BY_NAME.get(tool_name)
        tool_result, duration_ms = await self._run_tool(handler, tool_name, arguments)

        if tool_name == ASK_USER_TOOL_NAME and self.output.feedback_parts:
            tool_result = {"error": ASK_USER_BATCH_ERROR}

        normalized_result = normalize_tool_storage_value(tool_result)
        status = resolve_tool_status(tool_result)
        model_context_payload = json.dumps(normalized_result, separators=(",", ":"))
        if (
            tool_name == ASK_USER_TOOL_NAME
            and status != ToolCallStatusEnum.ERROR
            and self.output.on_chunk is None
        ):
            tool_result = {"error": "OpenAI Codex ask_user requires streaming mode."}
            normalized_result = normalize_tool_storage_value(tool_result)
            status = resolve_tool_status(tool_result)
            model_context_payload = json.dumps(normalized_result, separators=(",", ":"))

        persisted_arguments = arguments
        persisted_result = normalized_result
        persisted_status = status
        persisted_payload = model_context_payload
        if tool_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
            pending_result = AskUserPendingResult().model_dump()
            persisted_arguments = (
                normalized_result if isinstance(normalized_result, dict) else arguments
            )
            persisted_result = pending_result
            persisted_status = ToolCallStatusEnum.PENDING_USER_INPUT
            persisted_payload = json.dumps(pending_result, separators=(",", ":"))

        public_tool_call_id = await _persist_tool_call(
            req=self.req,
            tool_call_id=resolved_tool_call_id,
            tool_name=tool_name,
            arguments=persisted_arguments,
            normalized_result=persisted_result,
            model_context_payload=persisted_payload,
            status=persisted_status,
            duration_ms=duration_ms,
        )

        if runtime is not None:
            await self.output.emit_feedback(
                runtime.summary_renderer(
                    public_tool_call_id,
                    arguments,
                    persisted_result if tool_name == ASK_USER_TOOL_NAME else tool_result,
                    duration_ms,
                )
            )

        if tool_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
            await self._persist_pending_tool_continuation(
                public_tool_call_id=public_tool_call_id,
                tool_name=tool_name,
                tool_call_id=resolved_tool_call_id,
                arguments=arguments,
            )

        await client.respond(
            request_id,
            _build_dynamic_tool_result(
                persisted_payload,
                success=status != ToolCallStatusEnum.ERROR,
            ),
        )
        if self.state.awaiting_user_input:
            await client.request(
                "turn/interrupt",
                {"threadId": self.state.thread_id, "turnId": self.state.turn_id},
            )

    async def _run_tool(
        self,
        handler: Callable[[dict[str, Any], OpenAICodexReqChat], Awaitable[Any]] | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[Any, int]:
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}, 0
        started_at = time.perf_counter()
        try:
            tool_result = await handler(arguments, self.req)
        except Exception as exc:
            tool_result = {"error": f"Tool execution failed: {str(exc)}"}
        return tool_result, int((time.perf_counter() - started_at) * 1000)

    async def _persist_pending_tool_continuation(
        self,
        *,
        public_tool_call_id: str,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> None:
        if self.redis_manager is None:
            raise ValueError("OpenAI Codex ask_user requires Redis continuation state.")
        if self.pending_tool_call_id_sink is not None:
            self.pending_tool_call_id_sink["pending_tool_call_id"] = public_tool_call_id
        await persist_pending_tool_continuation(
            self.redis_manager,
            public_tool_call_id=public_tool_call_id,
            req=self.req,
            messages=[
                *self.req.messages,
                _build_pending_assistant_message(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    arguments=arguments,
                    assistant_text=self.output.assistant_text(),
                ),
            ],
        )
        self.state.awaiting_user_input = True


def _build_openai_codex_direct_content_items(
    content: Any,
    *,
    assistant: bool = False,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    text_content = extract_text_content(content)
    if text_content:
        items.append({"type": "output_text" if assistant else "input_text", "text": text_content})

    if assistant:
        return items

    for image_url in _extract_image_urls(content):
        items.append({"type": "input_image", "image_url": image_url})
    return items


def _build_openai_codex_direct_input(req: OpenAICodexReqChat) -> list[dict[str, Any]]:
    input_items: list[dict[str, Any]] = []

    for message in req.messages:
        role = normalize_role_value(message.get("role"))
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        if role == "system":
            continue

        if role == "tool":
            tool_name = str(message.get("name") or "tool").strip() or "tool"
            tool_text = extract_text_content(message.get("content"))
            if not tool_text and message.get("content") is not None:
                tool_text = str(message.get("content") or "").strip()
            if tool_text:
                input_items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": f"Tool ({tool_name}):\n{tool_text}"}
                        ],
                    }
                )
            continue

        content_items = _build_openai_codex_direct_content_items(
            message.get("content"),
            assistant=role == "assistant",
        )
        tool_calls_text = _summarize_tool_calls(message.get("tool_calls"))
        if tool_calls_text:
            content_items.append(
                {
                    "type": "output_text" if role == "assistant" else "input_text",
                    "text": f"Tool calls:\n{tool_calls_text}",
                }
            )
        if not content_items:
            continue
        input_items.append({"type": "message", "role": role, "content": content_items})

    if input_items:
        return input_items
    return [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": OPENAI_CODEX_FALLBACK_USER_CONTENT}],
        }
    ]


def _build_openai_codex_direct_tools(selected_tools: list[ToolEnum]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for dynamic_tool in _build_dynamic_tools(selected_tools):
        tools.append(
            {
                "type": "function",
                "name": dynamic_tool["name"],
                "description": dynamic_tool.get("description") or "",
                "parameters": dynamic_tool.get("inputSchema") or {"type": "object"},
            }
        )
    return tools


def _build_openai_codex_text_controls(schema: type[BaseModel] | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    return {
        "format": {
            "type": "json_schema",
            "name": schema.__name__ or "response_schema",
            "schema": _build_output_schema(schema),
            "strict": True,
        }
    }


def _build_openai_codex_reasoning(
    req: OpenAICodexReqChat,
) -> dict[str, Any] | None:
    reasoning: dict[str, Any] = {}
    effort = _normalize_reasoning_effort(req.config, req.is_title_generation)
    if effort:
        reasoning["effort"] = effort
    if (
        req.schema is None
        and not req.is_title_generation
        and not bool(getattr(req.config, "exclude_reasoning", False))
    ):
        reasoning["summary"] = "auto"
    return reasoning or None


def _build_openai_codex_direct_payload(
    req: OpenAICodexReqChat,
    input_items: list[dict[str, Any]],
) -> dict[str, Any]:
    instructions = _extract_system_instructions(req.messages)
    payload: dict[str, Any] = {
        "model": strip_model_prefix(req.model, OPENAI_CODEX_MODEL_PREFIX),
        "input": input_items,
        "tools": _build_openai_codex_direct_tools(req.selected_tools),
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "store": False,
        "stream": True,
        "include": [],
    }
    if instructions:
        payload["instructions"] = instructions
    reasoning = _build_openai_codex_reasoning(req)
    if reasoning is not None:
        payload["reasoning"] = reasoning
        payload["include"] = ["reasoning.encrypted_content"]
    text_controls = _build_openai_codex_text_controls(req.schema)
    if text_controls is not None:
        payload["text"] = text_controls
    return payload


def _build_openai_codex_direct_headers(
    normalized_auth_json: str,
    *,
    req: OpenAICodexReqChat,
) -> tuple[str, dict[str, str]]:
    return _build_openai_codex_response_headers(
        normalized_auth_json,
        session_id=req.graph_id or req.node_id or req.user_id,
    )


def _build_openai_codex_response_headers(
    normalized_auth_json: str,
    *,
    session_id: str,
) -> tuple[str, dict[str, str]]:
    try:
        payload = json.loads(normalized_auth_json)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI Codex auth JSON is invalid.") from exc

    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "User-Agent": "meridian/1.0.0",
        "originator": "meridian",
        "session-id": session_id or f"meridian-{uuid.uuid4().hex}",
    }

    tokens = _extract_codex_auth_tokens(normalized_auth_json)
    access_token = str(tokens.get("access_token") or "").strip() if tokens else ""
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        account_id = str(tokens.get("account_id") or "").strip() if tokens else ""
        if not account_id:
            account_id = _extract_account_id_from_tokens(tokens or {}) or ""
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id
        return OPENAI_CODEX_API_ENDPOINT, headers

    api_key = str(payload.get("OPENAI_API_KEY") or payload.get("key") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        return OPENAI_RESPONSES_API_ENDPOINT, headers

    raise ValueError("OpenAI Codex OAuth tokens or API key are required.")


def _select_openai_codex_probe_model_id() -> str:
    return "gpt-5.5"


def _format_openai_codex_auth_probe_error(status_code: int, body: str) -> str:
    detail = body[:500].strip()
    suffix = f" ({status_code} {detail})" if detail else f" ({status_code})"
    return "OpenAI Codex authentication is invalid or unavailable. Sign in again." + suffix


async def _probe_openai_api_key_auth(api_key: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            OPENAI_MODELS_API_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if response.status_code >= 400:
        raise ValueError(
            _format_openai_codex_auth_probe_error(
                response.status_code,
                response.text,
            )
        )


async def _probe_openai_codex_auth(normalized_auth_json: str) -> None:
    payload = json.loads(normalized_auth_json)
    api_key = str(payload.get("OPENAI_API_KEY") or payload.get("key") or "").strip()
    if api_key:
        await _probe_openai_api_key_auth(api_key)
        return

    endpoint, headers = _build_openai_codex_response_headers(
        normalized_auth_json,
        session_id=f"auth-probe-{uuid.uuid4().hex}",
    )
    probe_payload = {
        "model": _select_openai_codex_probe_model_id(),
        "instructions": OPENAI_CODEX_AUTH_PROBE_INSTRUCTIONS,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": OPENAI_CODEX_AUTH_PROBE_INPUT}],
            }
        ],
        "store": False,
        "stream": True,
        "include": [],
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        async with client.stream("POST", endpoint, headers=headers, json=probe_payload) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise ValueError(_format_openai_codex_auth_probe_error(response.status_code, body))
            async for event_type, event_data in _iter_openai_codex_sse_events(response):
                error_payload = event_data.get("error")
                if event_type in {"error", "response.failed"} or error_payload:
                    error_text = json.dumps(error_payload or event_data, separators=(",", ":"))
                    raise ValueError(_format_openai_codex_auth_probe_error(200, error_text))
                return


async def _iter_openai_codex_sse_events(
    response: httpx.Response,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    event_type = ""
    data_lines: list[str] = []
    buffer = ""

    async def emit_event() -> tuple[str, dict[str, Any]] | None:
        nonlocal event_type, data_lines
        if not data_lines:
            event_type = ""
            return None
        data = "\n".join(data_lines).strip()
        data_lines = []
        current_event_type = event_type
        event_type = ""
        if not data or data == "[DONE]":
            return None
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return current_event_type or str(parsed.get("type") or ""), parsed

    async for byte_chunk in response.aiter_bytes():
        buffer += byte_chunk.decode("utf-8", errors="ignore")
        lines = buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            buffer = lines.pop()
        else:
            buffer = ""

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                emitted = await emit_event()
                if emitted is not None:
                    yield emitted
                continue
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())

    if buffer:
        line = buffer.strip()
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())

    if data_lines:
        emitted = await emit_event()
        if emitted is not None:
            yield emitted


def _extract_openai_codex_message_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    content = item.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for content_item in content:
        if not isinstance(content_item, dict):
            continue
        if content_item.get("type") not in {"output_text", "input_text"}:
            continue
        text = str(content_item.get("text") or "")
        if text:
            parts.append(text)
    return "".join(parts)


def _normalize_openai_responses_usage_data(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        usage = payload

    prompt_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    completion_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0) or prompt_tokens + completion_tokens
    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")
    cached_tokens = (
        int(input_details.get("cached_tokens", 0) or 0) if isinstance(input_details, dict) else 0
    )
    reasoning_tokens = (
        int(output_details.get("reasoning_tokens", 0) or 0)
        if isinstance(output_details, dict)
        else 0
    )
    if not any((prompt_tokens, completion_tokens, total_tokens, cached_tokens, reasoning_tokens)):
        return None
    return {
        "cost": 0.0,
        "is_byok": False,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_tokens_details": {"cached_tokens": cached_tokens},
        "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
    }


def _extract_openai_codex_completed_usage(event_data: dict[str, Any]) -> dict[str, Any] | None:
    response_payload = event_data.get("response")
    if isinstance(response_payload, dict):
        usage_data = _normalize_openai_responses_usage_data(response_payload.get("usage"))
        if usage_data is not None:
            return usage_data
    return _normalize_openai_responses_usage_data(event_data.get("usage"))


async def _run_openai_codex_direct_tool_call(
    *,
    req: OpenAICodexReqChat,
    state: _OpenAICodexTurnState,
    output: _OpenAICodexOutputAssembler,
    redis_manager: RedisManager | None,
    pending_tool_call_id_sink: dict[str, Any] | None,
    item: dict[str, Any],
    mixed_tool_round: bool = False,
) -> dict[str, Any]:
    tool_name = str(item.get("name") or "").strip()
    call_id = str(item.get("call_id") or item.get("id") or "").strip()
    if not call_id:
        call_id = f"openai-codex-call-{uuid.uuid4().hex}"
    arguments = _parse_dynamic_tool_arguments(item.get("arguments"))
    runtime = get_tool_runtime(tool_name)
    handler = TOOL_HANDLERS_BY_NAME.get(tool_name)
    bridge = _OpenAICodexToolCallBridge(
        req,
        state,
        output,
        redis_manager=redis_manager,
        pending_tool_call_id_sink=pending_tool_call_id_sink,
    )
    tool_result, duration_ms = await bridge._run_tool(handler, tool_name, arguments)

    if tool_name == ASK_USER_TOOL_NAME and mixed_tool_round:
        tool_result = {"error": ASK_USER_BATCH_ERROR}

    normalized_result = normalize_tool_storage_value(tool_result)
    status = resolve_tool_status(tool_result)
    model_context_payload = json.dumps(normalized_result, separators=(",", ":"))
    if (
        tool_name == ASK_USER_TOOL_NAME
        and status != ToolCallStatusEnum.ERROR
        and output.on_chunk is None
    ):
        tool_result = {"error": "OpenAI Codex ask_user requires streaming mode."}
        normalized_result = normalize_tool_storage_value(tool_result)
        status = resolve_tool_status(tool_result)
        model_context_payload = json.dumps(normalized_result, separators=(",", ":"))

    persisted_arguments = arguments
    persisted_result = normalized_result
    persisted_status = status
    persisted_payload = model_context_payload
    if tool_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
        pending_result = AskUserPendingResult().model_dump()
        persisted_arguments = (
            normalized_result if isinstance(normalized_result, dict) else arguments
        )
        persisted_result = pending_result
        persisted_status = ToolCallStatusEnum.PENDING_USER_INPUT
        persisted_payload = json.dumps(pending_result, separators=(",", ":"))

    public_tool_call_id = await _persist_tool_call(
        req=req,
        tool_call_id=call_id,
        tool_name=tool_name,
        arguments=persisted_arguments,
        normalized_result=persisted_result,
        model_context_payload=persisted_payload,
        status=persisted_status,
        duration_ms=duration_ms,
    )

    if runtime is not None:
        await output.emit_feedback(
            runtime.summary_renderer(
                public_tool_call_id,
                arguments,
                persisted_result if tool_name == ASK_USER_TOOL_NAME else tool_result,
                duration_ms,
            )
        )

    if tool_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
        await bridge._persist_pending_tool_continuation(
            public_tool_call_id=public_tool_call_id,
            tool_name=tool_name,
            tool_call_id=call_id,
            arguments=arguments,
        )

    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": persisted_payload,
    }


class _OpenAICodexDirectTurnRunner:
    def __init__(
        self,
        req: OpenAICodexReqChat,
        normalized_auth_json: str,
        *,
        on_chunk: Callable[[str], Awaitable[None]] | None = None,
        redis_manager: RedisManager | None = None,
        usage_data_sink: dict[str, Any] | None = None,
        pending_tool_call_id_sink: dict[str, Any] | None = None,
    ) -> None:
        self.req = req
        self.normalized_auth_json = normalized_auth_json
        self.on_chunk = on_chunk
        self.redis_manager = redis_manager
        self.usage_data_sink = usage_data_sink
        self.pending_tool_call_id_sink = pending_tool_call_id_sink
        self.state = _OpenAICodexTurnState(turn_id=f"direct-{uuid.uuid4().hex}")
        self.output = _OpenAICodexOutputAssembler(req, self.state, on_chunk)
        self.function_call_argument_deltas: dict[str, str] = {}

    async def run(self) -> str:
        endpoint, headers = _build_openai_codex_direct_headers(
            self.normalized_auth_json,
            req=self.req,
        )
        input_items = _build_openai_codex_direct_input(self.req)
        owned_client: httpx.AsyncClient | None = None
        client = self.req.http_client
        if client is None:
            timeout = httpx.Timeout(OPENAI_CODEX_TURN_TIMEOUT_SECONDS, connect=30.0)
            owned_client = httpx.AsyncClient(timeout=timeout)
            client = owned_client

        try:
            for _ in range(8):
                function_calls = await self._stream_one_request(
                    client,
                    endpoint=endpoint,
                    headers=headers,
                    input_items=input_items,
                )
                if self.state.awaiting_user_input:
                    return self.output.build_output()
                if not function_calls:
                    return self.output.build_output()
                input_items.extend(function_calls)
                mixed_tool_round = len(function_calls) > 1
                for function_call in function_calls:
                    function_output = await _run_openai_codex_direct_tool_call(
                        req=self.req,
                        state=self.state,
                        output=self.output,
                        redis_manager=self.redis_manager,
                        pending_tool_call_id_sink=self.pending_tool_call_id_sink,
                        item=function_call,
                        mixed_tool_round=mixed_tool_round,
                    )
                    if self.state.awaiting_user_input:
                        return self.output.build_output()
                    input_items.append(function_output)
                if self.state.awaiting_user_input:
                    return self.output.build_output()
            raise ValueError("OpenAI Codex exceeded the maximum tool continuation rounds.")
        finally:
            await self.output.finalize_stream()
            if owned_client is not None:
                await owned_client.aclose()

    async def _stream_one_request(
        self,
        client: httpx.AsyncClient,
        *,
        endpoint: str,
        headers: dict[str, str],
        input_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = _build_openai_codex_direct_payload(self.req, input_items)
        function_calls: list[dict[str, Any]] = []
        async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
            if response.status_code >= 400:
                error_content = await response.aread()
                raise ValueError(
                    "OpenAI Codex request failed: "
                    f"{response.status_code} {error_content.decode('utf-8', errors='ignore')}"
                )

            async for event_type, event_data in _iter_openai_codex_sse_events(response):
                await self._handle_response_event(event_type, event_data, function_calls)
        return function_calls

    async def _handle_response_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        function_calls: list[dict[str, Any]],
    ) -> None:
        event_type = event_type or str(event_data.get("type") or "")
        if event_type == "response.output_text.delta":
            delta = str(event_data.get("delta") or "")
            item_id = str(event_data.get("item_id") or event_data.get("output_index") or "message")
            await self.output.emit_text(item_id, delta)
            return
        if event_type in {"response.reasoning_summary_text.delta", "response.reasoning_text.delta"}:
            delta = str(event_data.get("delta") or "")
            await self.output.emit_commentary("reasoning", delta)
            return
        if event_type == "response.reasoning_summary_part.added":
            await self.output.emit_reasoning_summary_break("reasoning")
            return
        if event_type == "response.function_call_arguments.delta":
            item_id = str(event_data.get("item_id") or event_data.get("output_index") or "")
            if item_id:
                self.function_call_argument_deltas[item_id] = (
                    self.function_call_argument_deltas.get(item_id, "")
                    + str(event_data.get("delta") or "")
                )
            return
        if event_type == "response.output_item.done":
            item = event_data.get("item")
            if not isinstance(item, dict):
                return
            item_type = str(item.get("type") or "")
            item_id = str(item.get("id") or event_data.get("item_id") or "")
            if item_type == "message":
                await self.output.sync_completed_agent_message(
                    item_id or "message",
                    _extract_openai_codex_message_text(item),
                    is_commentary=str(item.get("phase") or "").strip().lower() == "commentary",
                )
                return
            if item_type == "reasoning":
                await self.output.sync_completed_reasoning(
                    item_id or "reasoning", _extract_reasoning_item_text(item)
                )
                return
            if item_type == "function_call":
                if item_id and not item.get("arguments"):
                    item["arguments"] = self.function_call_argument_deltas.get(item_id, "")
                function_calls.append(item)
                return
        if event_type == "response.completed":
            usage_data = _extract_openai_codex_completed_usage(event_data)
            if usage_data is not None and self.usage_data_sink is not None:
                self.usage_data_sink.clear()
                self.usage_data_sink.update(usage_data)


async def _run_openai_codex_direct_turn(
    req: OpenAICodexReqChat,
    normalized_auth_json: str,
    *,
    on_chunk: Callable[[str], Awaitable[None]] | None = None,
    redis_manager: RedisManager | None = None,
    usage_data_sink: dict[str, Any] | None = None,
    pending_tool_call_id_sink: dict[str, Any] | None = None,
) -> str:
    return await _OpenAICodexDirectTurnRunner(
        req,
        normalized_auth_json,
        on_chunk=on_chunk,
        redis_manager=redis_manager,
        usage_data_sink=usage_data_sink,
        pending_tool_call_id_sink=pending_tool_call_id_sink,
    ).run()


def _build_openai_codex_direct_image_input(
    message_content: str | list[dict[str, Any]],
    *,
    aspect_ratio: str,
    resolution: str,
) -> list[dict[str, Any]]:
    content_items = _build_openai_codex_direct_content_items(message_content)
    prompt_suffix = (
        "\n\nUse the built-in image_generation tool exactly once. "
        "Generate one PNG image only. "
        f"Aspect ratio: {aspect_ratio}. Target resolution: {resolution}. "
        "Do not create SVG, HTML, code, or text-only output."
    )
    for content_item in content_items:
        if content_item.get("type") == "input_text":
            content_item["text"] = f"{content_item.get('text') or ''}{prompt_suffix}"
            break
    else:
        content_items.insert(0, {"type": "input_text", "text": prompt_suffix.strip()})

    return [{"type": "message", "role": "user", "content": content_items}]


def _build_openai_codex_direct_image_payload(
    *,
    model: str,
    input_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "model": get_openai_codex_image_generation_base_model_id(model),
        "instructions": OPENAI_CODEX_IMAGE_GENERATION_INSTRUCTIONS,
        "input": input_items,
        "tools": [{"type": "image_generation", "action": "generate", "partial_images": 0}],
        "store": False,
        "stream": True,
    }


def _extract_openai_codex_direct_image_result(
    event_data: dict[str, Any],
) -> tuple[bytes, str] | None:
    response = event_data.get("response")
    output_items = response.get("output") if isinstance(response, dict) else None
    if not isinstance(output_items, list):
        output_items = event_data.get("output")
    if not isinstance(output_items, list):
        return None

    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "image_generation_call":
            continue
        image_payload = _extract_generated_image_payload(item)
        if image_payload is not None:
            return image_payload
    return None


async def generate_image_with_openai_codex(
    *,
    auth_json: str,
    model: str,
    message_content: str | list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str,
    http_client: Optional[httpx.AsyncClient],
) -> OpenAICodexGeneratedImage:
    normalized_auth_json = _normalize_auth_json(auth_json)
    normalized_auth_json = await _refresh_openai_codex_auth_if_needed(normalized_auth_json)
    endpoint, headers = _build_openai_codex_response_headers(
        normalized_auth_json,
        session_id=f"image-{uuid.uuid4().hex}",
    )
    payload = _build_openai_codex_direct_image_payload(
        model=model,
        input_items=_build_openai_codex_direct_image_input(
            message_content,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        ),
    )
    owned_client: httpx.AsyncClient | None = None
    client = http_client
    if client is None:
        owned_client = httpx.AsyncClient(
            timeout=httpx.Timeout(OPENAI_CODEX_TURN_TIMEOUT_SECONDS, connect=30.0)
        )
        client = owned_client

    try:
        async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise ValueError(
                    f"OpenAI Codex image generation failed: {response.status_code} {body[:500]}"
                )
            async for event_type, event_data in _iter_openai_codex_sse_events(response):
                if event_type == "response.output_item.done":
                    item = event_data.get("item")
                    if isinstance(item, dict) and item.get("type") == "image_generation_call":
                        generated_payload = _extract_generated_image_payload(item)
                        if generated_payload is not None:
                            image_bytes, extension = generated_payload
                            return OpenAICodexGeneratedImage(
                                image_bytes=image_bytes,
                                extension=extension,
                                model=model,
                            )
                if event_type != "response.completed":
                    continue
                generated_payload = _extract_openai_codex_direct_image_result(event_data)
                if generated_payload is not None:
                    image_bytes, extension = generated_payload
                    return OpenAICodexGeneratedImage(
                        image_bytes=image_bytes,
                        extension=extension,
                        model=model,
                    )
        raise ValueError("OpenAI Codex completed without returning an image.")
    finally:
        if owned_client is not None:
            await owned_client.aclose()


async def make_openai_codex_request_non_streaming(
    req: OpenAICodexReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if ToolEnum.ASK_USER in req.selected_tools:
        raise ValueError("OpenAI Codex ask_user requires streaming mode.")
    usage_data: dict[str, Any] = {}
    normalized_auth_json = await _refresh_openai_codex_auth_if_needed(
        _normalize_auth_json(req.auth_json)
    )
    try:
        response_text = await _run_openai_codex_direct_turn(
            req,
            normalized_auth_json,
            usage_data_sink=usage_data,
        )
        if usage_data and req.graph_id and req.node_id and not req.is_title_generation:
            await update_node_usage_data(
                pg_engine=pg_engine,
                graph_id=req.graph_id,
                node_id=req.node_id,
                usage_data=usage_data,
                node_type=req.node_type,
                model_id=req.model_id,
            )
        return response_text
    finally:
        await _persist_refreshed_auth_json(
            user_id=req.user_id,
            pg_engine=pg_engine,
            current_auth_json=req.auth_json,
            refreshed_auth_json=normalized_auth_json,
        )


async def stream_openai_codex_response(
    req: OpenAICodexReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()
    usage_data: dict[str, Any] = {}
    turn_task: asyncio.Task[str] | None = None
    normalized_auth_json = await _refresh_openai_codex_auth_if_needed(
        _normalize_auth_json(req.auth_json)
    )
    try:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        pending_tool_call_state: dict[str, Any] = {}

        async def push_chunk(chunk: str) -> None:
            await queue.put(chunk)

        turn_task = asyncio.create_task(
            _run_openai_codex_direct_turn(
                req,
                normalized_auth_json,
                on_chunk=push_chunk,
                redis_manager=redis_manager,
                usage_data_sink=usage_data,
                pending_tool_call_id_sink=pending_tool_call_state,
            )
        )

        async for chunk in stream_background_task_chunks(queue, task=turn_task):
            if chunk is not None:
                yield chunk

        await turn_task

        if usage_data and not req.is_title_generation and final_data_container is not None:
            final_data_container["usage_data"] = usage_data

        if pending_tool_call_state.get("pending_tool_call_id") and final_data_container is not None:
            final_data_container["pending_tool_call_id"] = pending_tool_call_state[
                "pending_tool_call_id"
            ]

        if usage_data and req.graph_id and req.node_id and not req.is_title_generation:
            await update_node_usage_data(
                pg_engine=pg_engine,
                graph_id=req.graph_id,
                node_id=req.node_id,
                usage_data=usage_data,
                node_type=req.node_type,
                model_id=req.model_id,
            )
    except asyncio.CancelledError:
        logger.info("OpenAI Codex stream for node %s was cancelled.", req.node_id)
        raise
    except Exception as exc:
        logger.error("OpenAI Codex streaming error: %s", exc, exc_info=True)
        yield f"[ERROR]{GENERIC_STREAM_ERROR_MESSAGE}[!ERROR]"
    finally:
        if turn_task is not None and not turn_task.done():
            turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await turn_task
        await _persist_refreshed_auth_json(
            user_id=req.user_id,
            pg_engine=pg_engine,
            current_auth_json=req.auth_json,
            refreshed_auth_json=normalized_auth_json,
        )
