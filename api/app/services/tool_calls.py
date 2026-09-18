import re
from uuid import UUID

from services.tools import get_tool_runtime_by_tag_name

TOOL_TAG_PATTERN = re.compile(
    r"<(?P<tag>[a-z_]+)\s+id=\"(?P<id>[^\"]+)\"(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</(?P=tag)>"
)


def extract_tool_call_ids(text: str) -> list[str]:
    return list(extract_tool_call_references(text))


def extract_tool_call_references(text: str) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    for match in TOOL_TAG_PATTERN.finditer(text):
        runtime = get_tool_runtime_by_tag_name(match.group("tag"))
        if runtime is None or runtime.name == "inspect_image":
            continue
        try:
            public_id = str(UUID(match.group("id")))
        except ValueError:
            continue
        references.setdefault(public_id, set()).add(runtime.name)
    return references
