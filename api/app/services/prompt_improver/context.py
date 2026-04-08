import logging
from typing import Any, Optional, cast

from database.neo4j.crud import get_children_node_of_type, get_connected_prompt_nodes
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from database.pg.models import PromptImproverRun
from models.message import MessageContent, MessageContentTypeEnum, NodeTypeEnum
from models.prompt_improver import PromptImproverTarget
from services.graph_service import get_effective_graph_config
from services.node import extract_context_attachment, extract_context_github, extract_context_prompt
from services.settings import get_user_settings
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

from .schemas import PromptImproverContextBundle
from .taxonomy import DEFAULT_TARGET_ID

logger = logging.getLogger("uvicorn.error")


def build_connected_prompt_context(
    connected_records: list[Any],
    connected_nodes: list[Any],
    prompt_node_id: str,
) -> str:
    sibling_prompt_records = [
        record
        for record in connected_records
        if record.type == NodeTypeEnum.PROMPT and record.id != prompt_node_id
    ]
    if not sibling_prompt_records:
        return ""
    return str(extract_context_prompt(sibling_prompt_records, connected_nodes, True)).strip()


def build_attachment_context_summary(connected_nodes: list[Any]) -> str:
    lines: list[str] = []
    for node in connected_nodes:
        if node.type != NodeTypeEnum.FILE_PROMPT or not isinstance(node.data, dict):
            continue

        files = node.data.get("files", [])
        if not isinstance(files, list):
            continue

        for file_info in files[:20]:
            if not isinstance(file_info, dict):
                continue
            name = str(
                file_info.get("name")
                or file_info.get("filename")
                or file_info.get("fileName")
                or "Unnamed file"
            )
            content_type = str(file_info.get("content_type") or "unknown")
            if content_type == "application/pdf":
                kind = "PDF attachment"
            elif content_type.startswith("image/"):
                kind = "image attachment"
            else:
                kind = "file attachment"
            lines.append(f"- {name} ({kind}, content type: {content_type})")

    if not lines:
        return ""

    return (
        "These attachments are available to the model as multimodal context when supported:\n"
        + "\n".join(lines)
    )


def serialize_attachment_contents(contents: list[MessageContent]) -> list[dict[str, Any]]:
    return [content.model_dump(mode="json", exclude_none=True) for content in contents]


def compose_sibling_context_text(
    *,
    prompt_context: str,
    github_context: str,
    attachment_context: str,
) -> str:
    sections: list[str] = []
    if prompt_context:
        sections.append(f"<connected_prompts>\n{prompt_context}\n</connected_prompts>")
    if github_context:
        sections.append(f"<github_context>\n{github_context}\n</github_context>")
    if attachment_context:
        sections.append(f"<attachment_context>\n{attachment_context}\n</attachment_context>")
    if not sections:
        return "No additional connected context was found for the selected target."
    return "\n\n".join(sections)


async def build_target_context_bundle(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    graph_id: str,
    prompt_node_id: str,
    target_node_id: str | None,
    user_id: str,
    http_client,
) -> PromptImproverContextBundle:
    if not target_node_id:
        return PromptImproverContextBundle(
            sibling_context_text=(
                "No additional connected context was found for the selected target."
            ),
            attachment_contents=[],
        )

    connected_records = await get_connected_prompt_nodes(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        generator_node_id=target_node_id,
    )
    connected_nodes = await get_nodes_by_ids(
        pg_engine,
        graph_id,
        [record.id for record in connected_records],
    )
    graph_config, _, _ = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=graph_id,
        user_id=user_id,
    )

    prompt_context = build_connected_prompt_context(
        connected_records,
        connected_nodes,
        prompt_node_id,
    )

    try:
        github_context = (
            await extract_context_github(
                connected_records,
                connected_nodes,
                graph_config.block_github_auto_pull,
                True,
                user_id,
                pg_engine,
                http_client,
            )
        ).strip()
    except Exception:
        logger.exception("Failed to extract GitHub context for prompt improver")
        github_context = ""

    try:
        attachment_contents = await extract_context_attachment(
            user_id,
            connected_records,
            connected_nodes,
            pg_engine,
            True,
        )
    except Exception:
        logger.exception("Failed to extract attachment context for prompt improver")
        attachment_contents = []

    attachment_context = build_attachment_context_summary(connected_nodes)
    return PromptImproverContextBundle(
        sibling_context_text=compose_sibling_context_text(
            prompt_context=prompt_context,
            github_context=github_context,
            attachment_context=attachment_context,
        ),
        attachment_contents=serialize_attachment_contents(attachment_contents),
    )


def resolve_model_metadata(
    model_id: str | None, available_models: list[dict[str, Any]] | None
) -> tuple[str | None, bool]:
    if not model_id or not available_models:
        return None, False
    model = next(
        (
            item
            for item in available_models
            if (
                (isinstance(item, dict) and item.get("id") == model_id)
                or (not isinstance(item, dict) and getattr(item, "id", None) == model_id)
            )
        ),
        None,
    )
    if not model:
        return None, False
    if isinstance(model, dict):
        return cast(Optional[str], model.get("name")), bool(model.get("toolsSupport"))
    return (
        cast(Optional[str], getattr(model, "name", None)),
        bool(getattr(model, "toolsSupport", False)),
    )


async def resolve_targets(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    graph_id: str,
    node_id: str,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
) -> list[PromptImproverTarget]:
    downstream_node_ids = await get_children_node_of_type(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        node_type=[
            NodeTypeEnum.TEXT_TO_TEXT.value,
            NodeTypeEnum.PARALLELIZATION.value,
            NodeTypeEnum.ROUTING.value,
        ],
    )
    downstream_nodes = await get_nodes_by_ids(pg_engine, graph_id, downstream_node_ids or [])
    targets: list[PromptImproverTarget] = []

    for node in downstream_nodes:
        if not isinstance(node.data, dict):
            continue

        node_type = str(node.type)
        model_id = None
        label_suffix = ""
        if node.type == NodeTypeEnum.TEXT_TO_TEXT:
            model_id = cast(Optional[str], node.data.get("model"))
        elif node.type == NodeTypeEnum.PARALLELIZATION:
            aggregator = node.data.get("aggregator", {})
            if isinstance(aggregator, dict):
                model_id = cast(Optional[str], aggregator.get("model"))
            models = node.data.get("models", [])
            model_count = len(models) if isinstance(models, list) else 0
            label_suffix = f" • {model_count} parallel model(s)"
        elif node.type == NodeTypeEnum.ROUTING:
            model_id = cast(Optional[str], node.data.get("model"))
            route_group_id = cast(Optional[str], node.data.get("routeGroupId"))
            if route_group_id:
                label_suffix = f" • Route group {route_group_id}"

        model_name, tools_support = resolve_model_metadata(model_id, available_models)
        label = f"{node.type} node {node.id}"
        if model_name:
            label += f" • {model_name}"
        elif model_id:
            label += f" • {model_id}"
        if label_suffix:
            label += label_suffix

        targets.append(
            PromptImproverTarget(
                id=node.id,
                node_id=node.id,
                node_type=node_type,
                label=label,
                model_id=model_id,
                model_name=model_name,
                tools_support=tools_support,
            )
        )

    if targets:
        return targets

    settings = await get_user_settings(pg_engine, user_id)
    default_model = settings.models.defaultModel
    default_model_name, default_tools_support = resolve_model_metadata(
        default_model, available_models
    )
    return [
        PromptImproverTarget(
            id=DEFAULT_TARGET_ID,
            node_id=None,
            node_type="default",
            label=f"Default model • {default_model}",
            model_id=default_model,
            model_name=default_model_name,
            is_default_fallback=True,
            tools_support=default_tools_support,
        )
    ]


def validate_target_selection(
    targets: list[PromptImproverTarget],
    target_id: str | None,
) -> Optional[PromptImproverTarget]:
    if target_id and not any(target.id == target_id for target in targets):
        raise ValueError("Invalid prompt improver target selected")
    if len(targets) > 1 and not target_id:
        return None

    resolved_target_id = target_id or targets[0].id
    return next((target for target in targets if target.id == resolved_target_id), None)


def build_target_snapshot(target: PromptImproverTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "node_id": target.node_id,
        "node_type": target.node_type,
        "label": target.label,
        "model_id": target.model_id,
        "model_name": target.model_name,
        "is_default_fallback": target.is_default_fallback,
        "tools_support": target.tools_support,
    }


def compact_target_profile(target_snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_type": target_snapshot.get("node_type"),
        "model_id": target_snapshot.get("model_id"),
        "model_name": target_snapshot.get("model_name"),
        "is_default_fallback": target_snapshot.get("is_default_fallback"),
        "tools_support": target_snapshot.get("tools_support", False),
    }


def build_user_message_content(
    text_block: str,
    attachment_contents: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {"type": MessageContentTypeEnum.text.value, "text": text_block}
    ]
    if attachment_contents:
        content.extend(attachment_contents)
    return content


async def resolve_run_execution_context(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run: PromptImproverRun,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
    http_client,
) -> tuple[PromptImproverTarget, dict[str, Any], PromptImproverContextBundle, str, bool]:
    target_snapshot = cast(dict[str, Any], run.target_snapshot)
    target = PromptImproverTarget.model_validate(target_snapshot)
    context_bundle = await build_target_context_bundle(
        pg_engine,
        neo4j_driver,
        str(run.graph_id),
        run.node_id,
        target.node_id,
        user_id,
        http_client,
    )
    user_settings = await get_user_settings(pg_engine, user_id)

    if user_settings.blockPrompt.overridePromptImproverModel:
        optimizer_model = (
            user_settings.blockPrompt.promptImproverModel or user_settings.models.defaultModel
        )
        _, optimizer_tools_support = resolve_model_metadata(optimizer_model, available_models)
    else:
        optimizer_model = target.model_id or user_settings.models.defaultModel
        optimizer_tools_support = bool(target_snapshot.get("tools_support"))

    return (
        target,
        target_snapshot,
        context_bundle,
        optimizer_model,
        optimizer_tools_support,
    )
