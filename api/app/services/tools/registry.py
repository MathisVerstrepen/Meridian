from typing import Any, Awaitable, Callable

from models.message import ToolEnum
from services.tools.image_generation import (
    EDIT_IMAGE_TOOL,
    IMAGE_GENERATION_TOOL,
    edit_image,
    generate_image,
)
from services.tools.mermaid_generation import MERMAID_TOOL, generate_mermaid_diagram
from services.tools.web import (
    FETCH_PAGE_CONTENT_TOOL,
    WEB_SEARCH_TOOL,
    fetch_page_content,
    web_search,
)

ToolDefinition = dict[str, Any]
ToolHandler = Callable[[dict, Any], Awaitable[Any]]

TOOLS_BY_ENUM: dict[ToolEnum, list[ToolDefinition]] = {
    ToolEnum.WEB_SEARCH: [WEB_SEARCH_TOOL],
    ToolEnum.LINK_EXTRACTION: [FETCH_PAGE_CONTENT_TOOL],
    ToolEnum.IMAGE_GENERATION: [IMAGE_GENERATION_TOOL, EDIT_IMAGE_TOOL],
    ToolEnum.MERMAID_GENERATION: [MERMAID_TOOL],
}

TOOL_HANDLERS_BY_NAME: dict[str, ToolHandler] = {
    "web_search": web_search,
    "fetch_page_content": fetch_page_content,
    "generate_image": generate_image,
    "edit_image": edit_image,
    "generate_mermaid_diagram": generate_mermaid_diagram,
}

WEB_TOOL_NAMES = {"web_search", "fetch_page_content"}


def get_openrouter_tools(selected_tools: list[ToolEnum]) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    for tool in selected_tools:
        tools.extend(TOOLS_BY_ENUM.get(tool, []))
    return tools
