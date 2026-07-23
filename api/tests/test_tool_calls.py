import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.models import ToolCall, ToolCallStatusEnum  # noqa: E402
from services.tool_calls import expand_tool_context_in_text  # noqa: E402
from services.tools import get_tool_runtime_by_tag_name  # noqa: E402


def _tool_call(seed: int, tool_name: str) -> ToolCall:
    return ToolCall(
        id=uuid.UUID(int=seed),
        user_id=uuid.UUID(int=100 + seed),
        graph_id=uuid.UUID(int=200 + seed),
        node_id=f"node-{seed}",
        tool_name=tool_name,
        status=ToolCallStatusEnum.SUCCESS,
        arguments={"seed": seed},
        result={"value": seed},
        model_context_payload=f"context-{seed}",
    )


def _render_context(tag_name: str, tool_call: ToolCall) -> str:
    runtime = get_tool_runtime_by_tag_name(tag_name)
    assert runtime is not None
    return runtime.render_context(tool_call)


def test_expand_tool_context_expands_each_tool_call_id_once() -> None:
    search_call = _tool_call(1, "web_search")
    image_call = _tool_call(2, "generate_image")
    first_search_tag = '<search_query id="search-id" duration_ms="12">first</search_query>'
    first_image_tag = '<generating_image id="image-id">first</generating_image>'
    repeated_search_tag = '<search_query id="search-id">second</search_query>'
    repeated_image_tag = (
        '<generating_image_error id="image-id" reason="failed">second</generating_image_error>'
    )
    text = (
        f"before|{first_search_tag}|{first_image_tag}|"
        f"{repeated_search_tag}|{repeated_image_tag}|after"
    )

    result = expand_tool_context_in_text(
        text,
        {"search-id": search_call, "image-id": image_call},
    )

    assert result == (
        f"before|{first_search_tag}{_render_context('search_query', search_call)}|"
        f"{first_image_tag}{_render_context('generating_image', image_call)}|"
        f"{repeated_search_tag}|{repeated_image_tag}|after"
    )


def test_expand_tool_context_preserves_missing_and_unsupported_tags() -> None:
    tool_call = _tool_call(3, "web_search")
    missing_tag = '<search_query id="missing-id">first</search_query>'
    repeated_missing_tag = '<search_query id="missing-id">second</search_query>'
    unsupported_tag = '<unknown_tool id="shared-id">unsupported</unknown_tool>'
    supported_tag = '<search_query id="shared-id">supported</search_query>'
    text = f"{missing_tag}|{repeated_missing_tag}|{unsupported_tag}|{supported_tag}"

    result = expand_tool_context_in_text(text, {"shared-id": tool_call})

    assert result == (
        f"{missing_tag}|{repeated_missing_tag}|{unsupported_tag}|"
        f"{supported_tag}{_render_context('search_query', tool_call)}"
    )


def test_expand_tool_context_resets_seen_ids_per_invocation() -> None:
    tool_call = _tool_call(4, "web_search")
    tag = '<search_query id="search-id">query</search_query>'
    text = f"{tag}|{tag}"
    expected = f"{tag}{_render_context('search_query', tool_call)}|{tag}"

    first_result = expand_tool_context_in_text(text, {"search-id": tool_call})
    second_result = expand_tool_context_in_text(text, {"search-id": tool_call})

    assert first_result == expected
    assert second_result == expected
