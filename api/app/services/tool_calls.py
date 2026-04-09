import re

from database.pg.models import ToolCall
from services.tools import get_tool_runtime_by_tag_name

TOOL_TAG_PATTERN = re.compile(
    r"<(?P<tag>[a-z_]+)\s+id=\"(?P<id>[^\"]+)\"(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</(?P=tag)>"
)


def extract_tool_call_ids(text: str) -> list[str]:
    ids: list[str] = []
    seen_ids: set[str] = set()

    for match in TOOL_TAG_PATTERN.finditer(text):
        tag_name = match.group("tag")
        if not get_tool_runtime_by_tag_name(tag_name):
            continue

        tool_call_id = match.group("id")
        if tool_call_id not in seen_ids:
            ids.append(tool_call_id)
            seen_ids.add(tool_call_id)

    return ids


def expand_tool_context_in_text(text: str, tool_calls_by_id: dict[str, ToolCall]) -> str:
    def replace(match: re.Match[str]) -> str:
        tag_name = match.group("tag")
        runtime = get_tool_runtime_by_tag_name(tag_name)
        if not runtime:
            return match.group(0)

        tool_call_id = match.group("id")
        tool_call = tool_calls_by_id.get(tool_call_id)
        if not tool_call:
            return match.group(0)

        return f"{match.group(0)}{runtime.render_context(tool_call)}"

    return TOOL_TAG_PATTERN.sub(replace, text)
