import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx
from database.pg.chat_ops import create_tool_call
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.models import ToolCallStatusEnum
from database.pg.token_ops.provider_token_crud import store_provider_token
from database.redis.redis_ops import RedisManager
from models.message import MessageContentTypeEnum, NodeTypeEnum, ToolEnum
from models.tool_question import AskUserPendingResult
from pydantic import BaseModel
from services.crypto import encrypt_api_key
from services.openrouter import (
    ASK_USER_BATCH_ERROR,
    ASK_USER_TOOL_NAME,
    _normalize_tool_storage_value,
)
from services.providers.openai_codex_catalog import (
    OPENAI_CODEX_MODEL_PREFIX,
    OPENAI_CODEX_PROVIDER_KEY,
    normalize_openai_codex_model,
)
from services.sandbox_inputs import SandboxInputFileReference
from services.tools import (
    TOOL_HANDLERS_BY_NAME,
    get_openrouter_tools,
    get_tool_runtime,
    resolve_tool_status,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

OPENAI_CODEX_RUNTIME_PREFIX = "meridian-openai-codex-"
OPENAI_CODEX_RUNTIME_ROOT = Path("/tmp")
OPENAI_CODEX_RUNTIME_TTL_SECONDS = 60 * 60
OPENAI_CODEX_RPC_TIMEOUT_SECONDS = 30.0
OPENAI_CODEX_TURN_TIMEOUT_SECONDS = 300.0
OPENAI_CODEX_FALLBACK_USER_CONTENT = "Please respond to the available context."
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
OPENAI_CODEX_FORBIDDEN_EXTERNAL_TOOL_NAMES = (
    "functions.update_plan",
    "functions.request_user_input",
    "functions.view_image",
    "functions.apply_patch",
    "multi_tool_use.parallel",
)
OPENAI_CODEX_EXTERNAL_TOOL_LINE_PATTERN = re.compile(
    r"(?im)^.*(?:functions\.[a-z0-9_]+|multi_tool_use\.[a-z0-9_]+).*$"
)
OPENAI_CODEX_EXTERNAL_TOOL_DISCLAIMER = (
    "Ignore any references to external coding-assistant tools such as functions.* or "
    "multi_tool_use.*. For this Meridian request, only use the tools explicitly exposed by "
    "the host runtime."
)


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
        self._stderr_lines: list[str] = []
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


class OpenAICodexReqChat:
    def __init__(
        self,
        auth_json: str,
        model: str,
        messages: list[Any] | list[dict[str, Any]],
        config,
        user_id: str,
        pg_engine: SQLAlchemyAsyncEngine,
        model_id: Optional[str] = None,
        node_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        is_title_generation: bool = False,
        node_type: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT,
        schema: Optional[type[BaseModel]] = None,
        stream: bool = True,
        http_client: Optional[httpx.AsyncClient] = None,
        file_uuids: Optional[list[str]] = None,
        file_hashes: Optional[dict[str, str]] = None,
        pdf_engine: str = "default",
        selected_tools: Optional[list[ToolEnum]] = None,
        sandbox_input_files: Optional[list[SandboxInputFileReference]] = None,
        sandbox_input_warnings: Optional[list[str]] = None,
    ):
        self.auth_json = auth_json
        self.openai_codex_auth_json = auth_json
        self.model = model
        self.model_id = model_id
        self.messages = [
            mess.model_dump(exclude_none=True) if hasattr(mess, "model_dump") else mess
            for mess in messages
        ]
        self.config = config
        self.user_id = user_id
        self.pg_engine = pg_engine
        self.node_id = node_id
        self.graph_id = graph_id
        self.is_title_generation = is_title_generation
        self.node_type = node_type
        self.schema = schema
        self.stream = stream
        self.http_client = http_client
        self.file_uuids = file_uuids or []
        self.file_hashes = file_hashes or {}
        self.pdf_engine = pdf_engine
        self.selected_tools = selected_tools or []
        self.sandbox_input_files = sandbox_input_files or []
        self.sandbox_input_warnings = sandbox_input_warnings or []

    def validate_request(self) -> None:
        if self.file_uuids or self.file_hashes or _has_file_attachments(self.messages):
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


def _model_alias(model_id: str) -> str:
    if model_id.startswith(OPENAI_CODEX_MODEL_PREFIX):
        return model_id[len(OPENAI_CODEX_MODEL_PREFIX) :]
    return model_id


def _normalize_role_value(role: Any) -> str:
    raw_role = str(getattr(role, "value", role) or "").strip().lower()
    return raw_role or "user"


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == MessageContentTypeEnum.text.value and item.get("text"):
            parts.append(str(item["text"]).strip())
    return "\n".join(part for part in parts if part)


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


def _has_file_attachments(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == MessageContentTypeEnum.file.value:
                return True
    return False


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

    try:
        payload_bytes = base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError("OpenAI Codex image input contains invalid base64 data.") from exc

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


def _cleanup_stale_runtime_dirs() -> None:
    now = time.time()
    for runtime_dir in OPENAI_CODEX_RUNTIME_ROOT.glob(f"{OPENAI_CODEX_RUNTIME_PREFIX}*"):
        try:
            if not runtime_dir.is_dir():
                continue
            age_seconds = now - runtime_dir.stat().st_mtime
            if age_seconds > OPENAI_CODEX_RUNTIME_TTL_SECONDS:
                shutil.rmtree(runtime_dir, ignore_errors=True)
        except Exception:
            logger.warning(
                "Failed to clean stale OpenAI Codex runtime dir %s",
                runtime_dir,
                exc_info=True,
            )


def _build_codex_config_toml(model_instructions_path: Path | None = None) -> str:
    config_toml = OPENAI_CODEX_CONFIG_TOML
    if model_instructions_path is not None:
        config_toml = (
            f"model_instructions_file = {json.dumps(str(model_instructions_path))}\n\n"
            f"{config_toml}"
        )
    return config_toml


def _sanitize_model_instructions(raw_instructions: str) -> str:
    if not raw_instructions.strip():
        return ""

    filtered_lines: list[str] = []
    removed_external_tool_reference = False

    for raw_line in raw_instructions.splitlines():
        stripped_line = raw_line.strip()
        if stripped_line and any(
            tool_name in stripped_line for tool_name in OPENAI_CODEX_FORBIDDEN_EXTERNAL_TOOL_NAMES
        ):
            removed_external_tool_reference = True
            continue

        if OPENAI_CODEX_EXTERNAL_TOOL_LINE_PATTERN.match(raw_line):
            removed_external_tool_reference = True
            continue

        filtered_lines.append(raw_line.rstrip())

    sanitized = "\n".join(filtered_lines).strip()
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    if removed_external_tool_reference:
        if sanitized:
            sanitized = f"{sanitized}\n\n{OPENAI_CODEX_EXTERNAL_TOOL_DISCLAIMER}"
        else:
            sanitized = OPENAI_CODEX_EXTERNAL_TOOL_DISCLAIMER

    return sanitized.strip()


def _extract_system_instructions(messages: list[dict[str, Any]]) -> str:
    instructions: list[str] = []

    for message in messages:
        if _normalize_role_value(message.get("role")) != "system":
            continue

        content = message.get("content")
        text_content = _extract_text_content(content if not isinstance(content, str) else content)
        if text_content:
            instructions.append(text_content)

    return _sanitize_model_instructions("\n\n".join(part for part in instructions if part))


def _build_runtime_context(
    auth_json: str,
    *,
    model_instructions: str | None = None,
) -> OpenAICodexRuntimeContext:
    _cleanup_stale_runtime_dirs()

    root_dir = Path(
        tempfile.mkdtemp(prefix=OPENAI_CODEX_RUNTIME_PREFIX, dir=str(OPENAI_CODEX_RUNTIME_ROOT))
    )
    cwd = root_dir / "workspace"
    home_dir = root_dir / "home"
    config_dir = root_dir / "config"
    data_dir = root_dir / "data"
    state_dir = root_dir / "state"
    cache_dir = root_dir / "cache"
    input_dir = root_dir / "input"
    codex_home = home_dir / ".codex"
    auth_json_path = codex_home / "auth.json"
    config_toml_path = codex_home / "config.toml"
    model_instructions_path = codex_home / "meridian_instructions.md"

    for directory in (
        cwd,
        home_dir,
        config_dir,
        data_dir,
        state_dir,
        cache_dir,
        input_dir,
        codex_home,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    auth_json_path.write_text(auth_json, encoding="utf-8")
    normalized_model_instructions = (model_instructions or "").strip()
    if normalized_model_instructions:
        model_instructions_path.write_text(normalized_model_instructions + "\n", encoding="utf-8")
        config_toml_path.write_text(
            _build_codex_config_toml(model_instructions_path),
            encoding="utf-8",
        )
    else:
        config_toml_path.write_text(_build_codex_config_toml(), encoding="utf-8")

    return OpenAICodexRuntimeContext(
        root_dir=root_dir,
        cwd=cwd,
        env={
            "HOME": str(home_dir),
            "CODEX_HOME": str(codex_home),
            "XDG_CONFIG_HOME": str(config_dir),
            "XDG_DATA_HOME": str(data_dir),
            "XDG_STATE_HOME": str(state_dir),
            "XDG_CACHE_HOME": str(cache_dir),
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
    try:
        shutil.rmtree(runtime_context.root_dir, ignore_errors=True)
    except Exception:
        logger.warning(
            "Failed to cleanup OpenAI Codex runtime dir %s",
            runtime_context.root_dir,
            exc_info=True,
        )


def _read_runtime_auth_json(runtime_context: OpenAICodexRuntimeContext) -> str | None:
    if not runtime_context.auth_json_path.is_file():
        return None

    raw_auth_json = runtime_context.auth_json_path.read_text(encoding="utf-8").strip()
    if not raw_auth_json:
        return None
    return _normalize_auth_json(raw_auth_json)


async def _persist_refreshed_auth_json(
    *,
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    current_auth_json: str,
    refreshed_auth_json: str | None,
) -> None:
    if not refreshed_auth_json:
        return

    normalized_current = _normalize_auth_json(current_auth_json)
    normalized_refreshed = _normalize_auth_json(refreshed_auth_json)
    if normalized_current == normalized_refreshed:
        return

    encrypted_auth_json = await encrypt_api_key(normalized_refreshed)
    if not encrypted_auth_json:
        raise ValueError("Failed to encrypt refreshed OpenAI Codex auth.json.")

    await store_provider_token(pg_engine, user_id, OPENAI_CODEX_PROVIDER_KEY, encrypted_auth_json)


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
            env={**os.environ, **runtime_context.env},
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


def _extract_account_label(account_payload: Any) -> str | None:
    if not isinstance(account_payload, dict):
        return None

    account_type = str(account_payload.get("type") or "").strip()
    if account_type == "chatgpt":
        plan_type = str(account_payload.get("planType") or "").strip()
        if plan_type:
            return f"ChatGPT ({plan_type})"
        return "ChatGPT"
    if account_type == "apiKey":
        return "API key"
    return None


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


async def _list_available_models(
    client: _CodexAppServerClient,
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        params: dict[str, Any] = {"limit": 100, "includeHidden": False}
        if cursor:
            params["cursor"] = cursor

        result = await client.request("model/list", params)
        page_models = result.get("data")
        if isinstance(page_models, list):
            for model_payload in page_models:
                if isinstance(model_payload, dict):
                    models.append(model_payload)

        next_cursor = result.get("nextCursor")
        cursor = str(next_cursor).strip() if next_cursor is not None else None
        if not cursor:
            break

    return models


async def validate_openai_codex_auth_json(auth_json: str) -> str:
    normalized_auth_json = _normalize_auth_json(auth_json)
    runtime_context = _build_runtime_context(normalized_auth_json)
    client: _CodexAppServerClient | None = None

    try:
        client = await _start_codex_client(runtime_context)
        account_result = await _ensure_openai_auth(client, refresh_token=True)
        available_models = await _list_available_models(client)
        if not available_models:
            account_label = _extract_account_label(account_result.get("account"))
            if account_label:
                raise ValueError(f"OpenAI Codex returned no models for {account_label}.")
            raise ValueError("OpenAI Codex returned no models for this account.")
        return _read_runtime_auth_json(runtime_context) or normalized_auth_json
    finally:
        if client is not None:
            await client.close()
        _cleanup_runtime_context(runtime_context)


async def list_openai_codex_models(
    auth_json: str,
    *,
    user_id: str | None = None,
    pg_engine: SQLAlchemyAsyncEngine | None = None,
) -> list[Any]:
    normalized_auth_json = _normalize_auth_json(auth_json)
    runtime_context = _build_runtime_context(normalized_auth_json)
    client: _CodexAppServerClient | None = None

    try:
        client = await _start_codex_client(runtime_context)
        await _ensure_openai_auth(client, refresh_token=True)
        raw_models = await _list_available_models(client)

        normalized_models = []
        seen_model_ids: set[str] = set()
        for raw_model in raw_models:
            normalized_model = normalize_openai_codex_model(raw_model)
            if normalized_model is None or normalized_model.id in seen_model_ids:
                continue
            seen_model_ids.add(normalized_model.id)
            normalized_models.append(normalized_model)

        return normalized_models
    finally:
        try:
            refreshed_auth_json = _read_runtime_auth_json(runtime_context)
            if user_id and pg_engine is not None:
                await _persist_refreshed_auth_json(
                    user_id=user_id,
                    pg_engine=pg_engine,
                    current_auth_json=normalized_auth_json,
                    refreshed_auth_json=refreshed_auth_json,
                )
        finally:
            if client is not None:
                await client.close()
            _cleanup_runtime_context(runtime_context)


def _normalize_reasoning_effort(config: Any, is_title_generation: bool) -> str | None:
    if is_title_generation or bool(getattr(config, "exclude_reasoning", False)):
        return None

    raw_effort = str(getattr(config, "reasoning_effort", "") or "").strip().lower()
    if raw_effort in {"low", "medium", "high"}:
        return raw_effort
    if raw_effort in {"max", "xhigh"}:
        return "high"
    return None


async def _build_turn_input(
    req: OpenAICodexReqChat,
    runtime_context: OpenAICodexRuntimeContext,
) -> list[dict[str, Any]]:
    input_items: list[dict[str, Any]] = []
    image_index = 0

    for message in req.messages:
        role = _normalize_role_value(message.get("role"))
        if role not in {"system", "user", "assistant", "tool"}:
            continue

        if role == "system":
            continue

        content = message.get("content")
        image_urls = _extract_image_urls(content)
        text_blocks: list[str] = []

        if role == "tool":
            tool_name = str(message.get("name") or "tool").strip() or "tool"
            tool_text = _extract_text_content(content if not isinstance(content, str) else content)
            if not tool_text and content is not None and not isinstance(content, list):
                tool_text = str(content).strip()
            if tool_text:
                input_items.append({"type": "text", "text": f"Tool ({tool_name}):\n{tool_text}"})
            continue

        text_content = _extract_text_content(content if not isinstance(content, str) else content)
        if text_content:
            text_blocks.append(text_content)

        tool_calls_text = _summarize_tool_calls(message.get("tool_calls"))
        if tool_calls_text:
            text_blocks.append(f"Tool calls:\n{tool_calls_text}")

        for placeholder_index in range(len(image_urls)):
            text_blocks.append(f"Attached image {placeholder_index + 1} follows.")

        if text_blocks:
            input_items.append(
                {
                    "type": "text",
                    "text": f"{role.capitalize()}:\n" + "\n\n".join(text_blocks),
                }
            )

        for image_url in image_urls:
            image_index += 1
            local_image_path = await _write_local_image_input(
                image_url,
                input_dir=runtime_context.input_dir,
                image_index=image_index,
                http_client=req.http_client,
            )
            input_items.append({"type": "localImage", "path": str(local_image_path)})

    if input_items:
        return input_items

    return [{"type": "text", "text": f"User:\n{OPENAI_CODEX_FALLBACK_USER_CONTENT}"}]


def _format_turn_error(turn_payload: Any) -> str:
    if not isinstance(turn_payload, dict):
        return "OpenAI Codex turn failed."

    error_payload = turn_payload.get("error")
    if isinstance(error_payload, dict):
        message = str(error_payload.get("message") or "").strip()
        if message:
            return message
    return "OpenAI Codex turn failed."


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


def _serialize_sandbox_input_files(
    input_files: list[SandboxInputFileReference],
) -> list[dict[str, Any]]:
    return [
        {
            "file_id": input_file.file_id,
            "storage_path": input_file.storage_path,
            "relative_path": input_file.relative_path,
            "name": input_file.name,
            "content_type": input_file.content_type,
            "size": input_file.size,
        }
        for input_file in input_files
    ]


async def _persist_codex_pending_tool_continuation(
    redis_manager: RedisManager,
    *,
    public_tool_call_id: str,
    req: OpenAICodexReqChat,
    messages: list[dict[str, Any]],
) -> None:
    await redis_manager.set_pending_tool_continuation(
        public_tool_call_id,
        {
            "messages": messages,
            "model": req.model,
            "model_id": req.model_id,
            "config": req.config.model_dump(mode="json"),
            "user_id": req.user_id,
            "node_id": req.node_id,
            "graph_id": req.graph_id,
            "node_type": req.node_type.value,
            "file_hashes": req.file_hashes,
            "pdf_engine": req.pdf_engine,
            "selected_tools": [tool.value for tool in req.selected_tools],
            "sandbox_input_files": _serialize_sandbox_input_files(req.sandbox_input_files),
            "sandbox_input_warnings": req.sandbox_input_warnings,
        },
    )


async def _persist_tool_call(
    *,
    req: OpenAICodexReqChat,
    tool_call_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    normalized_result: Any,
    model_context_payload: str,
    status: ToolCallStatusEnum,
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


async def _run_openai_codex_turn(
    req: OpenAICodexReqChat,
    runtime_context: OpenAICodexRuntimeContext,
    *,
    on_chunk: Callable[[str], Awaitable[None]] | None = None,
    redis_manager: RedisManager | None = None,
    usage_data_sink: dict[str, Any] | None = None,
) -> str:
    thinking_started = False
    client = await _start_codex_client(runtime_context)
    try:
        await _ensure_openai_auth(client, refresh_token=True)
        turn_input = await _build_turn_input(req, runtime_context)
        dynamic_tools = _build_dynamic_tools(req.selected_tools)

        thread_result = await client.request(
            "thread/start",
            {
                "model": _model_alias(req.model),
                "cwd": str(runtime_context.cwd),
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "readOnly"},
                "serviceName": "meridian",
                "dynamicTools": dynamic_tools,
            },
        )
        thread_payload = thread_result.get("thread")
        if not isinstance(thread_payload, dict) or not thread_payload.get("id"):
            raise ValueError("OpenAI Codex failed to start a conversation thread.")

        turn_params: dict[str, Any] = {
            "threadId": str(thread_payload["id"]),
            "input": turn_input,
        }
        if req.schema is not None:
            turn_params["outputSchema"] = req.schema.model_json_schema()
        if not req.is_title_generation and not bool(
            getattr(req.config, "exclude_reasoning", False)
        ):
            turn_params["summary"] = "auto"

        reasoning_effort = _normalize_reasoning_effort(req.config, req.is_title_generation)
        if reasoning_effort:
            turn_params["effort"] = reasoning_effort

        turn_result = await client.request("turn/start", turn_params)
        turn_payload = turn_result.get("turn")
        if not isinstance(turn_payload, dict) or not turn_payload.get("id"):
            raise ValueError("OpenAI Codex failed to start a turn.")
        turn_id = str(turn_payload["id"])

        commentary_item_ids: set[str] = set()
        reasoning_item_ids: set[str] = set()
        reasoning_summary_indices: dict[str, set[int]] = {}
        emitted_text_by_item_id: dict[str, str] = {}
        emitted_commentary_by_item_id: dict[str, str] = {}
        final_text_parts: list[str] = []
        commentary_text_parts: list[str] = []
        feedback_parts: list[str] = []
        awaiting_user_input = False

        async def close_thinking() -> None:
            nonlocal thinking_started
            if thinking_started and on_chunk is not None:
                await on_chunk("\n[!THINK]\n")
            thinking_started = False

        async def emit_commentary(item_id: str, text: str) -> None:
            nonlocal thinking_started
            if not text:
                return
            emitted_commentary_by_item_id[item_id] = (
                emitted_commentary_by_item_id.get(item_id, "") + text
            )
            commentary_text_parts.append(text)
            if on_chunk is not None:
                if not thinking_started:
                    await on_chunk("[THINK]\n")
                    thinking_started = True
                await on_chunk(text)

        async def emit_text(item_id: str, text: str) -> None:
            if not text:
                return
            await close_thinking()
            emitted_text_by_item_id[item_id] = emitted_text_by_item_id.get(item_id, "") + text
            final_text_parts.append(text)
            if on_chunk is not None:
                await on_chunk(text)

        async def emit_feedback(text: str) -> None:
            if not text:
                return
            await close_thinking()
            feedback_parts.append(text)
            if on_chunk is not None:
                await on_chunk(text)

        while True:
            event = await client.next_event()
            method = str(event.get("method") or "")
            raw_params = event.get("params")
            params_dict: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
            request_id = event.get("id")

            if method == "item/tool/call" and request_id is not None:
                tool_name = str(params_dict.get("tool") or "").strip()
                tool_call_id = str(params_dict.get("callId") or "").strip() or None
                resolved_tool_call_id = tool_call_id or f"openai-codex-call-{uuid.uuid4().hex}"
                arguments = _parse_dynamic_tool_arguments(params_dict.get("arguments"))
                runtime = get_tool_runtime(tool_name)
                handler = TOOL_HANDLERS_BY_NAME.get(tool_name)

                if runtime is None or handler is None:
                    tool_result: Any = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        tool_result = await handler(arguments, req)
                    except Exception as exc:
                        tool_result = {"error": f"Tool execution failed: {str(exc)}"}

                if tool_name == ASK_USER_TOOL_NAME and feedback_parts:
                    tool_result = {"error": ASK_USER_BATCH_ERROR}

                normalized_result = _normalize_tool_storage_value(tool_result)
                status = resolve_tool_status(tool_result)
                model_context_payload = json.dumps(normalized_result, separators=(",", ":"))

                if (
                    tool_name == ASK_USER_TOOL_NAME
                    and status != ToolCallStatusEnum.ERROR
                    and on_chunk is None
                ):
                    tool_result = {"error": "OpenAI Codex ask_user requires streaming mode."}
                    normalized_result = _normalize_tool_storage_value(tool_result)
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
                    tool_call_id=resolved_tool_call_id,
                    tool_name=tool_name,
                    arguments=persisted_arguments,
                    normalized_result=persisted_result,
                    model_context_payload=persisted_payload,
                    status=persisted_status,
                )

                if runtime is not None:
                    await emit_feedback(
                        runtime.summary_renderer(
                            public_tool_call_id,
                            arguments,
                            persisted_result if tool_name == ASK_USER_TOOL_NAME else tool_result,
                        )
                    )

                if tool_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
                    if redis_manager is None:
                        raise ValueError("OpenAI Codex ask_user requires Redis continuation state.")

                    await _persist_codex_pending_tool_continuation(
                        redis_manager,
                        public_tool_call_id=public_tool_call_id,
                        req=req,
                        messages=[
                            *req.messages,
                            _build_pending_assistant_message(
                                tool_name=tool_name,
                                tool_call_id=resolved_tool_call_id,
                                arguments=arguments,
                                assistant_text="".join(final_text_parts).strip(),
                            ),
                        ],
                    )
                    awaiting_user_input = True

                await client.respond(
                    request_id,
                    _build_dynamic_tool_result(
                        persisted_payload,
                        success=status != ToolCallStatusEnum.ERROR,
                    ),
                )

                if awaiting_user_input:
                    await client.request(
                        "turn/interrupt",
                        {"threadId": str(thread_payload["id"]), "turnId": turn_id},
                    )
                continue

            if request_id is not None:
                await client.respond_error(
                    request_id,
                    code=-32601,
                    message=f"Unsupported OpenAI Codex server request: {method or 'unknown'}",
                )
                continue

            if method == "thread/tokenUsage/updated":
                usage_data = _normalize_codex_usage_data(params_dict.get("tokenUsage"))
                if usage_data is not None and usage_data_sink is not None:
                    usage_data_sink.clear()
                    usage_data_sink.update(usage_data)
                continue

            if method == "item/started":
                item = params_dict.get("item")
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                item_type = str(item.get("type") or "").strip()
                if item_type == "reasoning":
                    reasoning_item_ids.add(item_id)
                    continue
                if item_type != "agentMessage":
                    continue
                phase = str(item.get("phase") or "").strip().lower()
                if phase == "commentary":
                    commentary_item_ids.add(item_id)
                continue

            if method == "item/reasoning/summaryPartAdded":
                item_id = str(params_dict.get("itemId") or "")
                summary_index = params_dict.get("summaryIndex")
                if not item_id or not isinstance(summary_index, int) or summary_index <= 0:
                    continue
                seen_indices = reasoning_summary_indices.setdefault(item_id, set())
                if summary_index in seen_indices:
                    continue
                seen_indices.add(summary_index)
                await emit_commentary(item_id, "\n\n")
                continue

            if method in {
                "item/reasoning/summaryTextDelta",
                "item/reasoning/textDelta",
            }:
                item_id = str(params_dict.get("itemId") or "")
                delta = str(params_dict.get("delta") or "")
                if not item_id or not delta:
                    continue
                await emit_commentary(item_id, delta)
                continue

            if method == "item/agentMessage/delta":
                item_id = str(params_dict.get("itemId") or "")
                delta = str(params_dict.get("delta") or "")
                if not delta:
                    continue
                if item_id in commentary_item_ids:
                    await emit_commentary(item_id, delta)
                    continue
                await emit_text(item_id, delta)
                continue

            if method == "item/completed":
                item = params_dict.get("item")
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                item_type = str(item.get("type") or "").strip()
                if item_type == "reasoning" or item_id in reasoning_item_ids:
                    item_text = _extract_reasoning_item_text(item)
                    if not item_text:
                        continue
                    already_emitted = emitted_commentary_by_item_id.get(item_id, "")
                    if item_text.startswith(already_emitted):
                        await emit_commentary(item_id, item_text[len(already_emitted) :])
                    elif not already_emitted:
                        await emit_commentary(item_id, item_text)
                    continue
                if item_type != "agentMessage":
                    continue
                item_text = str(item.get("text") or "")
                if not item_text:
                    continue

                phase = str(item.get("phase") or "").strip().lower()
                if phase == "commentary" or item_id in commentary_item_ids:
                    already_emitted = emitted_commentary_by_item_id.get(item_id, "")
                    if item_text.startswith(already_emitted):
                        await emit_commentary(item_id, item_text[len(already_emitted) :])
                    elif not already_emitted:
                        await emit_commentary(item_id, item_text)
                    continue

                already_emitted = emitted_text_by_item_id.get(item_id, "")
                if item_text.startswith(already_emitted):
                    await emit_text(item_id, item_text[len(already_emitted) :])
                elif not already_emitted:
                    await emit_text(item_id, item_text)
                continue

            if method == "turn/completed":
                turn_data = params_dict.get("turn")
                if not isinstance(turn_data, dict) or str(turn_data.get("id") or "") != turn_id:
                    continue

                turn_status = str(turn_data.get("status") or "").strip().lower()
                if turn_status == "completed":
                    await close_thinking()
                    break
                if turn_status == "interrupted" and awaiting_user_input:
                    await close_thinking()
                    break
                raise ValueError(_format_turn_error(turn_data))

        commentary_text = "".join(commentary_text_parts).strip()
        final_text = "".join(final_text_parts).strip()
        feedback_output = "".join(feedback_parts)
        commentary_output = f"[THINK]\n{commentary_text}\n[!THINK]\n" if commentary_text else ""
        if feedback_output or commentary_output or final_text:
            return feedback_output + commentary_output + final_text
        if awaiting_user_input:
            return ""

        raise ValueError("OpenAI Codex completed without returning any text.")
    finally:
        if thinking_started and on_chunk is not None:
            await on_chunk("\n[!THINK]\n")
        await client.close()


async def make_openai_codex_request_non_streaming(
    req: OpenAICodexReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if ToolEnum.ASK_USER in req.selected_tools:
        raise ValueError("OpenAI Codex ask_user requires streaming mode.")
    usage_data: dict[str, Any] = {}
    runtime_context = _build_runtime_context(
        _normalize_auth_json(req.auth_json),
        model_instructions=_extract_system_instructions(req.messages),
    )
    try:
        response_text = await _run_openai_codex_turn(
            req,
            runtime_context,
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
        try:
            await _persist_refreshed_auth_json(
                user_id=req.user_id,
                pg_engine=pg_engine,
                current_auth_json=req.auth_json,
                refreshed_auth_json=_read_runtime_auth_json(runtime_context),
            )
        finally:
            _cleanup_runtime_context(runtime_context)


async def stream_openai_codex_response(
    req: OpenAICodexReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()
    usage_data: dict[str, Any] = {}
    runtime_context = _build_runtime_context(
        _normalize_auth_json(req.auth_json),
        model_instructions=_extract_system_instructions(req.messages),
    )
    try:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def push_chunk(chunk: str) -> None:
            await queue.put(chunk)

        turn_task = asyncio.create_task(
            _run_openai_codex_turn(
                req,
                runtime_context,
                on_chunk=push_chunk,
                redis_manager=redis_manager,
                usage_data_sink=usage_data,
            )
        )

        while True:
            if turn_task.done() and queue.empty():
                await turn_task
                break

            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if chunk is not None:
                yield chunk

        if usage_data and not req.is_title_generation and final_data_container is not None:
            final_data_container["usage_data"] = usage_data

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
        yield f"[ERROR]{str(exc)}[!ERROR]"
    finally:
        try:
            await _persist_refreshed_auth_json(
                user_id=req.user_id,
                pg_engine=pg_engine,
                current_auth_json=req.auth_json,
                refreshed_auth_json=_read_runtime_auth_json(runtime_context),
            )
        finally:
            _cleanup_runtime_context(runtime_context)
