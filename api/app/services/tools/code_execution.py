import asyncio
import base64
import binascii
import logging
import os
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
from fastapi import HTTPException
from services.files import get_user_storage_path
from services.tools.persisted_artifacts import persist_generated_artifacts
from services.sandbox_inputs import SandboxInputFileReference

logger = logging.getLogger("uvicorn.error")

CODE_EXECUTION_FOLDER_NAME = "Code Execution"

EXECUTE_CODE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": (
            "Execute Python code in a sandboxed environment. "
            "Use this when running code materially improves accuracy for computation, "
            "debugging, or verification. Always include a short human-readable title "
            "describing what the execution does."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": (
                        "Short human-readable title for this code execution. "
                        "This is shown in the UI, so summarize the purpose of the run "
                        "instead of pasting code. Example: 'Compute compound interest table'."
                        "Do not use any $ or {{}} syntax in the title."
                    ),
                },
                "code": {
                    "type": "string",
                    "description": (
                        "Python code to run. The environment is ephemeral and sandboxed. "
                        "If the node has linked file attachments, those files are auto-mounted "
                        "read-only under MERIDIAN_INPUT_DIR using the paths listed in the "
                        "sandbox input manifest in the conversation."
                    ),
                },
            },
            "required": ["title", "code"],
        },
    },
}


def _get_sandbox_manager_url() -> str:
    return (os.getenv("SANDBOX_MANAGER_URL") or "http://localhost:5000").rstrip("/")


def _extract_http_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "Unknown sandbox manager error."

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail:
            return str(detail)

    return response.text or "Unknown sandbox manager error."


def _normalize_warning_list(raw_warnings: Any) -> list[str]:
    if not isinstance(raw_warnings, list):
        return []

    normalized: list[str] = []
    for warning in raw_warnings:
        text = str(warning).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_relative_artifact_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    raw_path = value.strip().replace("\\", "/")
    if not raw_path:
        return None

    pure_path = PurePosixPath(raw_path)
    parts = [part for part in pure_path.parts if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None

    return str(PurePosixPath(*parts))


def _escape_markdown_link_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _build_execution_artifact_embed_code(artifact: dict[str, Any], title: str | None) -> str | None:
    artifact_id = str(artifact.get("id") or "").strip()
    if not artifact_id:
        return None

    name = str(artifact.get("name") or "").strip() or "artifact"
    content_type = str(artifact.get("content_type") or "application/octet-stream").strip().lower()
    label = _escape_markdown_link_label(title or name)

    if content_type.startswith("image/"):
        return f"![{label}](<{artifact_id}>)"

    if content_type == "text/html":
        return f"[{label}](sandbox-html://{artifact_id})"

    download_label = _escape_markdown_link_label(f"Download {name}")
    return f"[{download_label}](sandbox-file://{artifact_id})"


def _build_sanitized_execution_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_id": payload.get("execution_id"),
        "status": payload.get("status"),
        "exit_code": payload.get("exit_code"),
        "stdout": payload.get("stdout", ""),
        "stderr": payload.get("stderr", ""),
        "duration_ms": payload.get("duration_ms"),
        "output_truncated": bool(payload.get("output_truncated", False)),
        "artifacts": [],
        "artifact_warnings": _normalize_warning_list(payload.get("artifact_warnings")),
        "input_warnings": _normalize_warning_list(payload.get("input_warnings")),
    }


def _extract_sandbox_input_references(req) -> list[SandboxInputFileReference]:
    raw_inputs = getattr(req, "sandbox_input_files", None)
    if not isinstance(raw_inputs, list):
        return []

    normalized: list[SandboxInputFileReference] = []
    for raw_input in raw_inputs:
        if isinstance(raw_input, SandboxInputFileReference):
            normalized.append(raw_input)
            continue

        if not isinstance(raw_input, dict):
            continue

        file_id = str(raw_input.get("file_id") or "").strip()
        storage_path = str(raw_input.get("storage_path") or "").strip()
        relative_path = str(raw_input.get("relative_path") or "").strip()
        name = str(raw_input.get("name") or "").strip()
        content_type = str(raw_input.get("content_type") or "application/octet-stream").strip()

        try:
            size = int(raw_input.get("size") or 0)
        except (TypeError, ValueError):
            size = 0

        if not all([file_id, storage_path, relative_path, name]):
            continue

        normalized.append(
            SandboxInputFileReference(
                file_id=file_id,
                storage_path=storage_path,
                relative_path=relative_path,
                name=name,
                content_type=content_type or "application/octet-stream",
                size=max(size, 0),
            )
        )

    return normalized


async def _persist_execution_artifacts(
    payload: dict[str, Any], req
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings = _normalize_warning_list(payload.get("artifact_warnings"))
    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        return [], warnings

    if not getattr(req, "user_id", None) or not getattr(req, "pg_engine", None):
        warnings.append("Sandbox artifacts could not be persisted in this execution context.")
        return [], warnings

    parsed_user_id = uuid.UUID(str(req.user_id))
    execution_id = str(payload.get("execution_id") or uuid.uuid4().hex)

    normalized_artifacts: list[dict[str, Any]] = []
    for index, raw_artifact in enumerate(raw_artifacts, start=1):
        if not isinstance(raw_artifact, dict):
            warnings.append(f"Skipped sandbox artifact #{index} because the payload was invalid.")
            continue

        relative_path = _normalize_relative_artifact_path(raw_artifact.get("relative_path"))
        content_b64 = raw_artifact.get("content_b64")
        if relative_path is None or not isinstance(content_b64, str) or not content_b64.strip():
            warnings.append(
                f"Skipped sandbox artifact #{index} because required fields were missing."
            )
            continue

        try:
            file_bytes = base64.b64decode(content_b64.encode("ascii"), validate=True)
        except (ValueError, binascii.Error):
            warnings.append(
                f"Skipped sandbox artifact '{relative_path}' because its content was invalid."
            )
            continue

        size = len(file_bytes)
        content_type = str(raw_artifact.get("content_type") or "application/octet-stream").strip()
        if not content_type:
            content_type = "application/octet-stream"

        normalized_artifacts.append(
            {
                "relative_path": relative_path,
                "name": PurePosixPath(relative_path).name,
                "content_type": content_type,
                "size": size,
                "bytes": file_bytes,
            }
        )

    if not normalized_artifacts:
        return [], warnings

    try:
        persisted_artifacts = await persist_generated_artifacts(
            req=req,
            user_id=parsed_user_id,
            artifacts=normalized_artifacts,
            category_folder_name=CODE_EXECUTION_FOLDER_NAME,
            run_folder_name=f"Sandbox Run {execution_id[:8]}",
            disk_base_subdirectory=(
                PurePosixPath("generated_files") / "code_execution" / execution_id
            ),
        )
        return persisted_artifacts, warnings
    except HTTPException as exc:
        logger.warning(
            "Sandbox artifact persistence rejected for user %s: %s",
            parsed_user_id,
            exc.detail,
        )
        warnings.append(f"Sandbox artifacts were not saved: {exc.detail}")
    except Exception as exc:
        logger.exception("Failed to persist sandbox artifacts for execution %s", execution_id)
        warnings.append(f"Sandbox artifacts were not saved: {exc}")
    return [], warnings


async def execute_code(arguments: dict[str, Any], req) -> dict[str, Any]:
    code = arguments.get("code")
    title = str(arguments.get("title") or "").strip()
    if not code:
        return {"error": "Code is required for execution."}

    execute_url = f"{_get_sandbox_manager_url()}/execute"
    input_warnings = _normalize_warning_list(getattr(req, "sandbox_input_warnings", []))
    sandbox_inputs = _extract_sandbox_input_references(req)
    serialized_input_files: list[dict[str, Any]] = []

    for sandbox_input in sandbox_inputs:
        disk_path = Path(get_user_storage_path(req.user_id)) / sandbox_input.storage_path
        try:
            file_bytes = await asyncio.to_thread(disk_path.read_bytes)
        except OSError as exc:
            input_warnings.append(
                f"Skipped attachment '{sandbox_input.name}' because it could not be read: {exc}."
            )
            continue

        serialized_input_files.append(
            {
                "relative_path": sandbox_input.relative_path,
                "name": sandbox_input.name,
                "content_type": sandbox_input.content_type,
                "size": len(file_bytes),
                "content_b64": base64.b64encode(file_bytes).decode("ascii"),
            }
        )

    try:
        response = await req.http_client.post(
            execute_url,
            json={
                "language": "python",
                "code": code,
                "input_files": serialized_input_files,
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = _extract_http_error_detail(exc.response)
        return {
            "error": f"Code execution failed (status {exc.response.status_code}): {detail}",
            "status_code": exc.response.status_code,
            "detail": detail,
        }
    except httpx.RequestError as exc:
        logger.warning("Failed to reach sandbox manager at %s: %s", execute_url, exc)
        return {
            "error": "Code execution service is unavailable.",
            "detail": str(exc),
        }

    try:
        payload = response.json()
    except ValueError:
        logger.error("Sandbox manager returned invalid JSON for %s", execute_url)
        return {"error": "Code execution service returned invalid JSON."}

    if not isinstance(payload, dict):
        return {"error": "Code execution service returned an invalid response payload."}

    sanitized_payload = _build_sanitized_execution_result(payload)
    sanitized_payload["input_warnings"] = [
        *input_warnings,
        *_normalize_warning_list(payload.get("input_warnings")),
    ]
    persisted_artifacts, warnings = await _persist_execution_artifacts(payload, req)
    enriched_artifacts = []
    for artifact in persisted_artifacts:
        enriched_artifact = dict(artifact)
        embed_code = _build_execution_artifact_embed_code(enriched_artifact, title)
        if embed_code:
            enriched_artifact["embed_code"] = embed_code
        enriched_artifacts.append(enriched_artifact)
    sanitized_payload["artifacts"] = enriched_artifacts
    sanitized_payload["artifact_warnings"] = warnings

    return sanitized_payload
