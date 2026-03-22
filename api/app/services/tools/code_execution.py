import base64
import binascii
import hashlib
import logging
import os
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
from database.pg.file_ops.file_crud import (
    create_db_file,
    create_db_folder,
    delete_db_item_recursively,
    get_folder_contents,
    get_root_folder_for_user,
)
from database.pg.user_ops.storage_crud import check_and_reserve_storage, release_storage
from fastapi import HTTPException
from services.files import create_user_root_folder, delete_file_from_disk, save_file_to_disk

logger = logging.getLogger("uvicorn.error")

INLINE_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}
GENERATED_FILES_FOLDER_NAME = "Generated Files"
CODE_EXECUTION_FOLDER_NAME = "Code Execution"

EXECUTE_CODE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_code",
        "description": (
            "Execute a self-contained Python snippet in a sandboxed environment. "
            "Use this when running code materially improves accuracy for computation, "
            "debugging, or verification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Self-contained Python code to run. The environment is ephemeral, "
                        "sandboxed, and should not assume network access or persisted files."
                    ),
                }
            },
            "required": ["code"],
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


def _is_inline_image_content_type(content_type: str) -> bool:
    return content_type.lower() in INLINE_IMAGE_CONTENT_TYPES


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
    }


async def _get_or_create_child_folder(
    pg_engine,
    user_id: uuid.UUID,
    parent_id: uuid.UUID,
    name: str,
):
    contents = await get_folder_contents(pg_engine, user_id, parent_id)
    for item, _ in contents:
        if item.type == "folder" and item.name == name:
            return item

    return await create_db_folder(
        pg_engine=pg_engine,
        user_id=user_id,
        name=name,
        parent_id=parent_id,
    )


async def _cleanup_persisted_run(
    pg_engine,
    user_id: uuid.UUID,
    run_folder_id: uuid.UUID | None,
    reserved_bytes: int,
    extra_file_paths: list[str],
    storage_reserved: bool,
) -> None:
    disk_paths_to_delete = set(extra_file_paths)

    if run_folder_id is not None:
        file_paths = await delete_db_item_recursively(
            pg_engine=pg_engine,
            item_id=run_folder_id,
            user_id=user_id,
        )
        disk_paths_to_delete.update(file_paths)

    for file_path in disk_paths_to_delete:
        await delete_file_from_disk(user_id, file_path)

    if storage_reserved and reserved_bytes > 0:
        await release_storage(pg_engine, user_id, reserved_bytes)


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
            warnings.append(
                f"Skipped sandbox artifact #{index} because the payload was invalid."
            )
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

    reserved_bytes = sum(int(artifact["size"]) for artifact in normalized_artifacts)
    run_folder_id: uuid.UUID | None = None
    persisted_disk_paths: list[str] = []
    storage_reserved = False

    try:
        await check_and_reserve_storage(req.pg_engine, parsed_user_id, reserved_bytes)
        storage_reserved = True
        root_folder = await get_root_folder_for_user(req.pg_engine, parsed_user_id)
        if root_folder is None:
            root_folder = await create_user_root_folder(req.pg_engine, parsed_user_id)
        if root_folder is None or root_folder.id is None:
            raise RuntimeError("Root folder not found for user.")

        generated_folder = await _get_or_create_child_folder(
            req.pg_engine,
            parsed_user_id,
            root_folder.id,
            GENERATED_FILES_FOLDER_NAME,
        )
        code_execution_folder = await _get_or_create_child_folder(
            req.pg_engine,
            parsed_user_id,
            generated_folder.id,
            CODE_EXECUTION_FOLDER_NAME,
        )
        run_folder = await create_db_folder(
            pg_engine=req.pg_engine,
            user_id=parsed_user_id,
            name=f"Sandbox Run {execution_id[:8]}",
            parent_id=code_execution_folder.id,
        )
        run_folder_id = run_folder.id
        if run_folder_id is None:
            raise RuntimeError("Failed to create sandbox artifact run folder.")

        folder_cache: dict[PurePosixPath, uuid.UUID] = {PurePosixPath("."): run_folder_id}
        base_subdirectory = PurePosixPath("generated_files") / "code_execution" / execution_id
        persisted_artifacts: list[dict[str, Any]] = []

        for artifact in normalized_artifacts:
            relative_path = PurePosixPath(str(artifact["relative_path"]))
            parent_path = relative_path.parent

            if parent_path not in folder_cache:
                current_parent_id = run_folder_id
                current_path = PurePosixPath(".")
                for segment in parent_path.parts:
                    if segment in {"", "."}:
                        continue

                    current_path = current_path / segment
                    cached_id = folder_cache.get(current_path)
                    if cached_id is None:
                        folder = await create_db_folder(
                            pg_engine=req.pg_engine,
                            user_id=parsed_user_id,
                            name=segment,
                            parent_id=current_parent_id,
                        )
                        if folder.id is None:
                            raise RuntimeError(f"Failed to create artifact folder '{segment}'.")
                        cached_id = folder.id
                        folder_cache[current_path] = cached_id

                    current_parent_id = cached_id

            parent_id = folder_cache[parent_path]
            disk_subdirectory = base_subdirectory / parent_path
            file_bytes = artifact["bytes"]
            unique_filename = await save_file_to_disk(
                user_id=parsed_user_id,
                file_contents=file_bytes,
                original_filename=str(artifact["name"]),
                subdirectory=str(disk_subdirectory),
            )
            persisted_disk_paths.append(str(Path(str(disk_subdirectory)) / unique_filename))

            file_record = await create_db_file(
                pg_engine=req.pg_engine,
                user_id=parsed_user_id,
                parent_id=parent_id,
                name=str(artifact["name"]),
                file_path=persisted_disk_paths[-1],
                size=int(artifact["size"]),
                content_type=str(artifact["content_type"]),
                hash=hashlib.sha256(file_bytes).hexdigest(),
            )
            if file_record.id is None:
                raise RuntimeError(f"Failed to persist artifact '{artifact['relative_path']}'.")

            content_type = str(artifact["content_type"])
            persisted_artifacts.append(
                {
                    "id": str(file_record.id),
                    "name": str(artifact["name"]),
                    "relative_path": str(artifact["relative_path"]),
                    "content_type": content_type,
                    "size": int(artifact["size"]),
                    "kind": "image" if _is_inline_image_content_type(content_type) else "file",
                }
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

    await _cleanup_persisted_run(
        req.pg_engine,
        parsed_user_id,
        run_folder_id,
        reserved_bytes,
        persisted_disk_paths,
        storage_reserved,
    )
    return [], warnings


async def execute_code(arguments: dict[str, Any], req) -> dict[str, Any]:
    code = arguments.get("code")
    if not code:
        return {"error": "Code is required for execution."}

    execute_url = f"{_get_sandbox_manager_url()}/execute"

    try:
        response = await req.http_client.post(
            execute_url,
            json={"language": "python", "code": code},
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
    persisted_artifacts, warnings = await _persist_execution_artifacts(payload, req)
    sanitized_payload["artifacts"] = persisted_artifacts
    sanitized_payload["artifact_warnings"] = warnings

    return sanitized_payload
