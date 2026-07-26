import uuid

from database.pg.chat_ops import get_successful_inspect_image_calls_for_node
from models.message import Message, MessageContent, MessageContentTypeEnum
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

MAX_INSPECTION_PROVENANCE_ENTRIES = 8


def _inspection_file_id(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    try:
        return str(uuid.UUID(str(result.get("file_id") or "")))
    except (AttributeError, TypeError, ValueError):
        return None


async def enrich_message_with_inspection_provenance(
    message: Message,
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    graph_id: str,
    node_id: str,
) -> Message:
    tool_calls = await get_successful_inspect_image_calls_for_node(
        pg_engine,
        user_id=user_id,
        graph_id=graph_id,
        node_id=node_id,
        limit=MAX_INSPECTION_PROVENANCE_ENTRIES,
    )
    file_ids = [
        file_id
        for tool_call in tool_calls[:MAX_INSPECTION_PROVENANCE_ENTRIES]
        if (file_id := _inspection_file_id(tool_call.result)) is not None
    ]
    if not file_ids:
        return message

    entries = "\n".join(
        (
            '<inspection tool_name="inspect_image" status="success" '
            f'file_id="{file_id}">Image pixels were supplied transiently through inspect_image '
            "for that immediate continuation and are not retained in conversation history. Call "
            "inspect_image again with this file UUID if visual access is needed.</inspection>"
        )
        for file_id in file_ids
    )
    provenance = f"<internal_tool_provenance>\n{entries}\n</internal_tool_provenance>"

    enriched = message.model_copy(deep=True)
    for content in reversed(enriched.content):
        if content.type == MessageContentTypeEnum.text:
            content.text = f"{content.text or ''}\n{provenance}".strip()
            break
    else:
        enriched.content.append(MessageContent(type=MessageContentTypeEnum.text, text=provenance))
    return enriched
