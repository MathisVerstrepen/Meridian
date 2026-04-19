import json
from dataclasses import dataclass
from html import escape
from typing import Any, Awaitable, Callable

from database.pg.models import ToolCall, ToolCallStatusEnum
from models.message import ToolEnum
from services.tools.ask_user import ASK_USER_TOOL, ask_user
from services.tools.code_execution import EXECUTE_CODE_TOOL, execute_code
from services.tools.image_generation import IMAGE_GENERATION_TOOL, generate_image
from services.tools.visualise import VISUALISE_TOOL, visualise
from services.tools.web import (
    FETCH_PAGE_CONTENT_TOOL,
    WEB_SEARCH_TOOL,
    fetch_page_content,
    web_search,
)

ToolDefinition = dict[str, Any]
ToolHandler = Callable[[dict, Any], Awaitable[Any]]
EXECUTION_ERROR_STATUSES = {
    "runtime_error",
    "timeout",
    "memory_limit_exceeded",
    "output_limit_exceeded",
}


@dataclass(frozen=True)
class ToolRuntimeDefinition:
    name: str
    tool_definitions: list[ToolDefinition]
    handler: ToolHandler
    tag_names: tuple[str, ...]
    summary_renderer: Callable[[str, dict[str, Any], Any, int | None], str]

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
        if tool_result.get("error"):
            return ToolCallStatusEnum.ERROR

        status = tool_result.get("status")
        if isinstance(status, str) and status in EXECUTION_ERROR_STATUSES:
            return ToolCallStatusEnum.ERROR

        return ToolCallStatusEnum.SUCCESS

    if isinstance(tool_result, list):
        if tool_result and isinstance(tool_result[0], dict) and tool_result[0].get("error"):
            return ToolCallStatusEnum.ERROR
        return ToolCallStatusEnum.SUCCESS

    return ToolCallStatusEnum.SUCCESS


def _render_duration_attr(duration_ms: int | None) -> str:
    if duration_ms is None:
        return ""

    return f' duration_ms="{duration_ms}"'


def _render_web_search_summary(
    tool_call_public_id: str,
    arguments: dict[str, Any],
    tool_result: Any,
    duration_ms: int | None = None,
) -> str:
    query = arguments.get("query", "")
    duration_attr = _render_duration_attr(duration_ms)
    feedback_str = (
        f'\n<search_query id="{tool_call_public_id}"{duration_attr}>\n"{query}"\n</search_query>\n'
    )

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
    tool_call_public_id: str,
    arguments: dict[str, Any],
    tool_result: Any,
    duration_ms: int | None = None,
) -> str:
    url = arguments.get("url", "")
    duration_attr = _render_duration_attr(duration_ms)
    feedback_str = (
        f'\n<fetch_url id="{tool_call_public_id}"{duration_attr}>\n'
        f"Reading content from:\n{url}\n"
        "</fetch_url>\n"
    )

    if isinstance(tool_result, dict) and tool_result.get("error"):
        error_msg = tool_result.get("error", "An unknown error occurred.")
        feedback_str += f"<fetch_error>\n{error_msg}\n</fetch_error>\n"

    return feedback_str


def _render_generate_image_summary(
    tool_call_public_id: str,
    arguments: dict[str, Any],
    tool_result: Any,
    duration_ms: int | None = None,
) -> str:
    prompt = arguments.get("prompt", "")
    duration_attr = _render_duration_attr(duration_ms)
    if isinstance(tool_result, dict) and tool_result.get("success"):
        return (
            f'\n<generating_image id="{tool_call_public_id}"{duration_attr}>\n'
            f'Prompt: "{prompt}"\n'
            "</generating_image>\n"
        )
    error_msg = (
        tool_result.get("error") if isinstance(tool_result, dict) else "Image generation failed."
    )
    return (
        f'\n<generating_image_error id="{tool_call_public_id}"{duration_attr}>\n'
        f"{error_msg}\n"
        "</generating_image_error>\n"
    )


def _render_visualise_summary(
    tool_call_public_id: str,
    arguments: dict[str, Any],
    tool_result: Any,
    duration_ms: int | None = None,
) -> str:
    title = " ".join(str(arguments.get("title", "")).split()).strip()
    if not title and isinstance(tool_result, dict):
        title = " ".join(str(tool_result.get("title", "")).split()).strip()
    if not title:
        title = " ".join(str(arguments.get("instructions", "")).split()).strip()
    title = title[:120] or "Interactive visual"
    output_mode = str(arguments.get("output_mode", "")).strip().lower()
    duration_attr = _render_duration_attr(duration_ms)

    if output_mode == "mermaid":
        if isinstance(tool_result, dict) and tool_result.get("content"):
            return (
                f'\n<generating_mermaid_diagram id="{tool_call_public_id}"{duration_attr}>\n'
                f"{title}\n"
                "</generating_mermaid_diagram>\n"
            )
        error_msg = (
            tool_result.get("error")
            if isinstance(tool_result, dict)
            else "Mermaid generation failed."
        )
        return (
            f'\n<generating_mermaid_diagram_error id="{tool_call_public_id}"{duration_attr}>\n'
            f"{error_msg}\n"
            "</generating_mermaid_diagram_error>\n"
        )

    if isinstance(tool_result, dict) and tool_result.get("artifact_id"):
        return (
            f'\n<visualising id="{tool_call_public_id}"{duration_attr}>\n'
            f"{title}\n"
            "</visualising>\n"
        )
    error_msg = (
        tool_result.get("error") if isinstance(tool_result, dict) else "Visual generation failed."
    )
    return (
        f'\n<visualising_error id="{tool_call_public_id}"{duration_attr}>\n'
        f"{error_msg}\n"
        "</visualising_error>\n"
    )


def _build_code_execution_title(arguments: dict[str, Any]) -> str:
    title = " ".join(str(arguments.get("title", "")).split()).strip()
    if title:
        return title[:120]

    code = str(arguments.get("code", "")).strip()
    if not code:
        return "Python snippet"

    first_line = code.splitlines()[0].strip()
    return first_line[:120] or "Python snippet"


def _render_code_artifact_tags(tool_call_public_id: str, tool_result: Any) -> str:
    if not isinstance(tool_result, dict):
        return ""

    artifacts = tool_result.get("artifacts")
    if not isinstance(artifacts, list):
        return ""

    rendered_tags = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue

        artifact_id = str(artifact.get("id") or "").strip()
        kind = str(artifact.get("kind") or "file").strip() or "file"
        name = str(artifact.get("name") or "").strip()
        relative_path = str(artifact.get("relative_path") or "").strip()
        content_type = str(artifact.get("content_type") or "application/octet-stream").strip()
        if not artifact_id:
            continue

        rendered_tags.append(
            "<sandbox_artifact "
            f'tool_call_id="{escape(tool_call_public_id, quote=True)}" '
            f'id="{escape(artifact_id, quote=True)}" '
            f'kind="{escape(kind, quote=True)}" '
            f'name="{escape(name, quote=True)}" '
            f'path="{escape(relative_path, quote=True)}" '
            f'content_type="{escape(content_type, quote=True)}"></sandbox_artifact>'
        )

    if not rendered_tags:
        return ""

    return "\n" + "\n".join(rendered_tags) + "\n"


def _render_execute_code_summary(
    tool_call_public_id: str,
    arguments: dict[str, Any],
    tool_result: Any,
    duration_ms: int | None = None,
) -> str:
    title = _build_code_execution_title(arguments)
    artifact_tags = _render_code_artifact_tags(tool_call_public_id, tool_result)
    duration_attr = _render_duration_attr(duration_ms)
    status_attr = ""

    if isinstance(tool_result, dict):
        if tool_result.get("error"):
            status_attr = ' status="error"'

        status = str(tool_result.get("status", "")).strip()
        if status in EXECUTION_ERROR_STATUSES:
            status_attr = ' status="error"'

    return (
        f'\n<executing_code id="{tool_call_public_id}"{duration_attr}{status_attr}>\n'
        f"{title}\n"
        f"{artifact_tags}"
        "</executing_code>\n"
    )


def _render_ask_user_summary(
    tool_call_public_id: str,
    arguments: dict[str, Any],
    _tool_result: Any,
    duration_ms: int | None = None,
) -> str:
    questions = arguments.get("questions")
    if isinstance(questions, list):
        normalized_questions = [
            " ".join(str(question.get("question", "")).split()).strip()
            for question in questions
            if isinstance(question, dict)
        ]
    else:
        normalized_questions = []

    if normalized_questions:
        question = normalized_questions[0][:120]
        if len(normalized_questions) > 1:
            question = f"{len(normalized_questions)} questions: {question}"
    else:
        question = " ".join(str(arguments.get("question", "")).split()).strip()[:160]

    duration_attr = _render_duration_attr(duration_ms)
    return (
        f'\n<asking_user id="{tool_call_public_id}"{duration_attr}>\n'
        f"{question}\n"
        "</asking_user>\n"
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
    "execute_code": ToolRuntimeDefinition(
        name="execute_code",
        tool_definitions=[EXECUTE_CODE_TOOL],
        handler=execute_code,
        tag_names=("executing_code",),
        summary_renderer=_render_execute_code_summary,
    ),
    "visualise": ToolRuntimeDefinition(
        name="visualise",
        tool_definitions=[VISUALISE_TOOL],
        handler=visualise,
        tag_names=(
            "visualising",
            "visualising_error",
            "generating_mermaid_diagram",
            "generating_mermaid_diagram_error",
        ),
        summary_renderer=_render_visualise_summary,
    ),
    "ask_user": ToolRuntimeDefinition(
        name="ask_user",
        tool_definitions=[ASK_USER_TOOL],
        handler=ask_user,
        tag_names=("asking_user",),
        summary_renderer=_render_ask_user_summary,
    ),
}

TOOLS_BY_ENUM: dict[ToolEnum, list[ToolDefinition]] = {
    ToolEnum.WEB_SEARCH: RUNTIME_DEFINITIONS["web_search"].tool_definitions,
    ToolEnum.LINK_EXTRACTION: RUNTIME_DEFINITIONS["fetch_page_content"].tool_definitions,
    ToolEnum.IMAGE_GENERATION: RUNTIME_DEFINITIONS["generate_image"].tool_definitions,
    ToolEnum.EXECUTE_CODE: RUNTIME_DEFINITIONS["execute_code"].tool_definitions,
    ToolEnum.VISUALISE: RUNTIME_DEFINITIONS["visualise"].tool_definitions,
    ToolEnum.ASK_USER: RUNTIME_DEFINITIONS["ask_user"].tool_definitions,
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
