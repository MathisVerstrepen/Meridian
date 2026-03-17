import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from database.pg.models import ToolCall, ToolCallStatusEnum
from models.message import ToolEnum
from services.tools.image_generation import IMAGE_GENERATION_TOOL, generate_image
from services.tools.mermaid_generation import MERMAID_TOOL, generate_mermaid_diagram
from services.tools.web import (
    FETCH_PAGE_CONTENT_TOOL,
    WEB_SEARCH_TOOL,
    fetch_page_content,
    web_search,
)

ToolDefinition = dict[str, Any]
ToolHandler = Callable[[dict, Any], Awaitable[Any]]


@dataclass(frozen=True)
class ToolRuntimeDefinition:
    name: str
    tool_definitions: list[ToolDefinition]
    handler: ToolHandler
    tag_names: tuple[str, ...]
    summary_renderer: Callable[[str, dict[str, Any], Any], str]

    def render_context(self, tool_call: ToolCall) -> str:
        arguments = json.dumps(tool_call.arguments, indent=2, ensure_ascii=True, sort_keys=True)
        result = json.dumps(tool_call.result, indent=2, ensure_ascii=True, sort_keys=True)
        return (
            f'\n<tool_call_context id="{tool_call.id}" name="{tool_call.tool_name}" '
            f'status="{tool_call.status}">\n'
            f"Arguments:\n{arguments}\n"
            f"Result:\n{result}\n"
            f"Model context payload:\n{tool_call.model_context_payload}\n"
            "</tool_call_context>\n"
        )


def resolve_tool_status(tool_result: Any) -> ToolCallStatusEnum:
    if isinstance(tool_result, dict):
        return ToolCallStatusEnum.ERROR if tool_result.get("error") else ToolCallStatusEnum.SUCCESS

    if isinstance(tool_result, list):
        if tool_result and isinstance(tool_result[0], dict) and tool_result[0].get("error"):
            return ToolCallStatusEnum.ERROR
        return ToolCallStatusEnum.SUCCESS

    return ToolCallStatusEnum.SUCCESS


def _render_web_search_summary(
    tool_call_public_id: str, arguments: dict[str, Any], tool_result: Any
) -> str:
    query = arguments.get("query", "")
    feedback_str = f'\n<search_query id="{tool_call_public_id}">\n"{query}"\n</search_query>\n'

    results_str = ""
    if isinstance(tool_result, list):
        if tool_result and isinstance(tool_result[0], dict) and tool_result[0].get("error"):
            error_msg = tool_result[0].get("error", "An unknown web search error occurred.")
            results_str = f"<search_error>\n{error_msg}\n</search_error>\n"
        else:
            for res in tool_result:
                if isinstance(res, dict) and not res.get("error"):
                    title = res.get("title", "")
                    url = res.get("url", "")
                    content = res.get("content", "")
                    results_str += (
                        "<search_res>\n"
                        f"Title: {title}\n"
                        f"URL: {url}\n"
                        f"Content: {content}\n"
                        "</search_res>\n"
                    )

    return feedback_str + results_str if results_str else feedback_str


def _render_fetch_page_summary(
    tool_call_public_id: str, arguments: dict[str, Any], tool_result: Any
) -> str:
    url = arguments.get("url", "")
    feedback_str = (
        f'\n<fetch_url id="{tool_call_public_id}">\nReading content from:\n{url}\n</fetch_url>\n'
    )

    if isinstance(tool_result, dict) and tool_result.get("error"):
        error_msg = tool_result.get("error", "An unknown error occurred.")
        feedback_str += f"<fetch_error>\n{error_msg}\n</fetch_error>\n"

    return feedback_str


def _render_generate_image_summary(
    tool_call_public_id: str, arguments: dict[str, Any], tool_result: Any
) -> str:
    prompt = arguments.get("prompt", "")
    if isinstance(tool_result, dict) and tool_result.get("success"):
        return (
            f'\n<generating_image id="{tool_call_public_id}">\n'
            f'Prompt: "{prompt}"\n'
            "</generating_image>\n"
        )
    error_msg = (
        tool_result.get("error") if isinstance(tool_result, dict) else "Image generation failed."
    )
    return (
        f'\n<generating_image_error id="{tool_call_public_id}">\n'
        f"{error_msg}\n"
        "</generating_image_error>\n"
    )


def _render_mermaid_summary(
    tool_call_public_id: str, arguments: dict[str, Any], tool_result: Any
) -> str:
    instructions = arguments.get("instructions", "")
    if isinstance(tool_result, dict) and tool_result.get("mermaid"):
        return (
            f'\n<generating_mermaid_diagram id="{tool_call_public_id}">\n'
            f"{instructions}\n"
            "</generating_mermaid_diagram>\n"
        )
    error_msg = (
        tool_result.get("error") if isinstance(tool_result, dict) else "Mermaid generation failed."
    )
    return (
        f'\n<generating_mermaid_diagram_error id="{tool_call_public_id}">\n'
        f"{error_msg}\n"
        "</generating_mermaid_diagram_error>\n"
    )


RUNTIME_DEFINITIONS: dict[str, ToolRuntimeDefinition] = {
    "web_search": ToolRuntimeDefinition(
        name="web_search",
        tool_definitions=[WEB_SEARCH_TOOL],
        handler=web_search,
        tag_names=("search_query",),
        summary_renderer=_render_web_search_summary,
    ),
    "fetch_page_content": ToolRuntimeDefinition(
        name="fetch_page_content",
        tool_definitions=[FETCH_PAGE_CONTENT_TOOL],
        handler=fetch_page_content,
        tag_names=("fetch_url",),
        summary_renderer=_render_fetch_page_summary,
    ),
    "generate_image": ToolRuntimeDefinition(
        name="generate_image",
        tool_definitions=[IMAGE_GENERATION_TOOL],
        handler=generate_image,
        tag_names=("generating_image", "generating_image_error"),
        summary_renderer=_render_generate_image_summary,
    ),
    "generate_mermaid_diagram": ToolRuntimeDefinition(
        name="generate_mermaid_diagram",
        tool_definitions=[MERMAID_TOOL],
        handler=generate_mermaid_diagram,
        tag_names=("generating_mermaid_diagram", "generating_mermaid_diagram_error"),
        summary_renderer=_render_mermaid_summary,
    ),
}

TOOLS_BY_ENUM: dict[ToolEnum, list[ToolDefinition]] = {
    ToolEnum.WEB_SEARCH: RUNTIME_DEFINITIONS["web_search"].tool_definitions,
    ToolEnum.LINK_EXTRACTION: RUNTIME_DEFINITIONS["fetch_page_content"].tool_definitions,
    ToolEnum.IMAGE_GENERATION: RUNTIME_DEFINITIONS["generate_image"].tool_definitions,
    ToolEnum.MERMAID_GENERATION: RUNTIME_DEFINITIONS["generate_mermaid_diagram"].tool_definitions,
}

TOOL_HANDLERS_BY_NAME: dict[str, ToolHandler] = {
    name: runtime.handler for name, runtime in RUNTIME_DEFINITIONS.items()
}

TOOL_RUNTIME_BY_TAG_NAME: dict[str, ToolRuntimeDefinition] = {
    tag_name: runtime for runtime in RUNTIME_DEFINITIONS.values() for tag_name in runtime.tag_names
}

WEB_TOOL_NAMES = {"web_search", "fetch_page_content"}


def get_openrouter_tools(selected_tools: list[ToolEnum]) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    for tool in selected_tools:
        tools.extend(TOOLS_BY_ENUM.get(tool, []))
    return tools


def get_tool_runtime(tool_name: str) -> ToolRuntimeDefinition | None:
    return RUNTIME_DEFINITIONS.get(tool_name)


def get_tool_runtime_by_tag_name(tag_name: str) -> ToolRuntimeDefinition | None:
    return TOOL_RUNTIME_BY_TAG_NAME.get(tag_name)
