import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.tool_calls import extract_tool_call_ids, extract_tool_call_references


def test_references_require_known_tag_and_public_uuid_and_deduplicate():
    public_id = str(uuid.UUID(int=1))
    text = (
        f'<search_query id="{public_id}">first</search_query>'
        f'<search_query id="{public_id}">second</search_query>'
        f'<generating_image_error id="{public_id}">error</generating_image_error>'
        '<search_query id="provider-id">not public</search_query>'
        f'<unknown_tool id="{uuid.UUID(int=2)}">unknown</unknown_tool>'
        f'<inspect_image id="{uuid.UUID(int=3)}">hidden</inspect_image>'
    )
    assert extract_tool_call_ids(text) == [public_id]
    assert extract_tool_call_references(text) == {public_id: {"web_search", "generate_image"}}


def test_context_attributes_and_json_are_not_references():
    public_id = str(uuid.UUID(int=1))
    assert (
        extract_tool_call_ids(
            f'<tool_call_context id="{public_id}" tool_name="web_search">'
            f'{{"id":"{public_id}"}}</tool_call_context>'
        )
        == []
    )
