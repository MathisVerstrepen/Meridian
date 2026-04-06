import logging
from typing import Any

from models.message import MessageContentTypeEnum, MessageRoleEnum
from pydantic import BaseModel
from services.graph_service import get_effective_graph_config
from services.openrouter import OpenRouterReqChat, make_openrouter_request_non_streaming
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


async def run_structured_prompt(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
    model_id: str,
    schema: type[BaseModel],
    system_prompt: str,
    user_prompt: str | list[dict[str, Any]],
    http_client,
) -> BaseModel:
    if isinstance(user_prompt, str):
        user_content: str | list[dict[str, Any]] = user_prompt
    else:
        text_block = next(
            (
                item.get("text")
                for item in user_prompt
                if item.get("type") == MessageContentTypeEnum.text.value and item.get("text")
            ),
            "[multimodal prompt improver payload]",
        )
        user_content = user_prompt

    graph_config, _, open_router_api_key = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=graph_id,
        user_id=user_id,
    )
    messages: list[dict[str, Any]] = [
        {"role": MessageRoleEnum.system.value, "content": system_prompt},
        {"role": MessageRoleEnum.user.value, "content": user_content},
    ]
    req = OpenRouterReqChat(
        api_key=open_router_api_key,
        model=model_id,
        messages=messages,
        config=graph_config,
        user_id=user_id,
        pg_engine=pg_engine,
        schema=schema,
        stream=False,
        http_client=http_client,
    )
    content = await make_openrouter_request_non_streaming(req, pg_engine)
    return schema.model_validate_json(content)
