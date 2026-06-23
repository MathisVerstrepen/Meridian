import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import httpx
from database.neo4j.crud import NodeRecord
from database.pg.models import Node
from models.message import NodeTypeEnum
from services.file_sources import materialize_attachment_file
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

SANDBOX_INPUT_DIR = "/tmp/inputs"
DEFAULT_INPUT_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class SandboxInputFileReference:
    file_id: str
    storage_path: str
    relative_path: str
    name: str
    content_type: str
    size: int


def _normalize_relative_input_path(logical_path: Any, fallback_name: str) -> str | None:
    raw_path = str(logical_path or fallback_name).strip().replace("\\", "/")
    if not raw_path:
        return None

    normalized_path = raw_path.lstrip("/")
    parts = [part for part in PurePosixPath(normalized_path).parts if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None

    return PurePosixPath(*parts).as_posix()


async def collect_sandbox_input_files(
    user_id: str,
    connected_nodes: list[NodeRecord],
    connected_nodes_data: list[Node],
    pg_engine: SQLAlchemyAsyncEngine,
    http_client: httpx.AsyncClient,
) -> tuple[list[SandboxInputFileReference], list[str]]:
    connected_file_prompt_nodes = sorted(
        (node for node in connected_nodes if node.type == NodeTypeEnum.FILE_PROMPT),
        key=lambda x: -x.distance,
    )

    warnings: list[str] = []
    collected: list[SandboxInputFileReference] = []
    seen_file_ids: set[str] = set()
    seen_relative_paths: set[str] = set()

    for node in connected_file_prompt_nodes:
        node_data = next((item for item in connected_nodes_data if item.id == node.id), None)
        if not (node_data and isinstance(node_data.data, dict)):
            continue

        files_to_process = node_data.data.get("files", [])
        if not isinstance(files_to_process, list):
            continue

        for file_info in files_to_process:
            if not isinstance(file_info, dict):
                continue

            if str(file_info.get("type") or "").strip().lower() == "folder":
                continue

            file_id = str(file_info.get("id") or "").strip()
            source = str(file_info.get("source") or "meridian").strip().lower()
            seen_key = f"{source}:{file_id}"
            if not file_id or seen_key in seen_file_ids:
                continue

            try:
                materialized = await materialize_attachment_file(
                    pg_engine, http_client, uuid.UUID(str(user_id)), file_info
                )
            except Exception as exc:
                warnings.append(
                    f"Skipped attachment '{file_id}' because it could not be resolved: {exc}"
                )
                continue

            relative_path = _normalize_relative_input_path(
                file_info.get("path"),
                materialized.name,
            )
            if relative_path is None:
                warnings.append(
                    f"Skipped attachment '{materialized.name}' because its mount path was invalid."
                )
                continue

            if relative_path in seen_relative_paths:
                warnings.append(
                    f"Skipped attachment '{materialized.name}' because its mount path "
                    f"'{relative_path}' conflicted with another attachment."
                )
                continue

            size = int(materialized.size or Path(materialized.path).stat().st_size)
            content_type = str(
                materialized.content_type
                or file_info.get("content_type")
                or DEFAULT_INPUT_CONTENT_TYPE
            ).strip()
            if not content_type:
                content_type = DEFAULT_INPUT_CONTENT_TYPE

            collected.append(
                SandboxInputFileReference(
                    file_id=materialized.file_id,
                    storage_path=str(materialized.path),
                    relative_path=relative_path,
                    name=str(materialized.name),
                    content_type=content_type,
                    size=size,
                )
            )
            seen_file_ids.add(seen_key)
            seen_relative_paths.add(relative_path)

    return collected, warnings


def build_sandbox_input_manifest(
    input_files: list[SandboxInputFileReference],
    warnings: list[str],
) -> str:
    lines = [
        "<sandbox_input_manifest>",
        f"MERIDIAN_INPUT_DIR={SANDBOX_INPUT_DIR}",
    ]

    if input_files:
        lines.append("Read-only files available to execute_code:")
        for input_file in input_files:
            lines.append(
                f"- {PurePosixPath(SANDBOX_INPUT_DIR, input_file.relative_path).as_posix()}"
            )
    else:
        lines.append("No read-only attachment files are available to execute_code for this node.")

    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)

    lines.append("</sandbox_input_manifest>")
    return "\n".join(lines)
