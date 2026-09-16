"""Derived historical data, never tool execution or raw-result reconstruction."""

import json
import logging
import re

from database.pg.chat_ops import get_completed_tool_calls_for_history
from models.message import (
    Message,
    MessageContent,
    MessageContentTypeEnum,
    MessageRoleEnum,
    MessageToolCall,
    MessageToolFunction,
)
from services.tool_calls import extract_tool_call_references
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("uvicorn.error")
_LEGACY_OPEN = re.compile(r"<tool_call_context(?=[\s/>])")
_LEGACY_CLOSE = "</tool_call_context>"


def clean_legacy_tool_context(text: str) -> str:
    """Remove reserved spans only; an opened but unfinished span ends at EOF."""
    parts: list[str] = []
    position = 0
    while match := _LEGACY_OPEN.search(text, position):
        parts.append(text[position : match.start()])
        end = text.find(_LEGACY_CLOSE, match.end())
        if end < 0:
            return "".join(parts)
        position = end + len(_LEGACY_CLOSE)
    parts.append(text[position:])
    return "".join(parts)


async def build_tool_history(
    reply: str,
    *,
    pg_engine: AsyncEngine,
    user_id: str,
    graph_id: str,
    node_id: str,
    model_id: str | None = None,
) -> list[Message]:
    references = extract_tool_call_references(clean_legacy_tool_context(reply))
    if not references:
        return []
    rows = await get_completed_tool_calls_for_history(
        pg_engine,
        user_id=user_id,
        graph_id=graph_id,
        node_id=node_id,
        model_id=model_id,
        tool_call_ids=list(references),
    )
    messages: list[Message] = []
    for row in rows:
        if row.id is None or row.tool_name not in references.get(str(row.id), set()):
            continue
        payload = row.model_context_payload
        if (
            not isinstance(row.arguments, dict)
            or not isinstance(payload, str)
            or not payload.strip()
        ):
            logger.warning("Omitting invalid historical tool pair id=%s", row.id)
            continue
        try:
            arguments = json.dumps(row.arguments, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            logger.warning("Omitting invalid historical tool arguments id=%s", row.id)
            continue
        call_id = f"hist_{row.id.hex}"
        messages.extend(
            [
                Message(
                    role=MessageRoleEnum.assistant,
                    content=[],
                    tool_calls=[
                        MessageToolCall(
                            id=call_id,
                            function=MessageToolFunction(name=row.tool_name, arguments=arguments),
                        )
                    ],
                ),
                Message(
                    role=MessageRoleEnum.tool,
                    content=[MessageContent(type=MessageContentTypeEnum.text, text=payload)],
                    tool_call_id=call_id,
                    name=row.tool_name,
                ),
            ]
        )
    return messages
