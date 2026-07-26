import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from database.pg.models import ToolCall, ToolCallStatusEnum
from models.message import Message, MessageContent, MessageContentTypeEnum, MessageRoleEnum
from services.graph_service import construct_message_from_generator_node
from services.node import CleanTextOption
from services.tools.image_inspection_provenance import (
    MAX_INSPECTION_PROVENANCE_ENTRIES,
    enrich_message_with_inspection_provenance,
)


def _tool_call(file_id: str, index: int = 0) -> ToolCall:
    return ToolCall(
        user_id=uuid.uuid4(),
        graph_id=uuid.uuid4(),
        node_id="node-1",
        tool_name="inspect_image",
        status=ToolCallStatusEnum.SUCCESS,
        arguments={"file_id": file_id},
        result={
            "success": True,
            "file_id": file_id,
            "inspection_bytes": 123,
            "private_path": f"/private/image-{index}.png",
            "content_hash": "secret-hash",
            "data_uri": "data:image/jpeg;base64,c2VjcmV0",
        },
        model_context_payload="private model context",
    )


@pytest.mark.anyio
async def test_image_inspection_provenance_is_sanitized_bounded_and_model_only():
    file_ids = [str(uuid.uuid4()) for _ in range(MAX_INSPECTION_PROVENANCE_ENTRIES + 2)]
    persisted_message = Message(
        role=MessageRoleEnum.assistant,
        content=[MessageContent(type=MessageContentTypeEnum.text, text="Visible answer")],
    )
    query = AsyncMock(
        return_value=[_tool_call(file_id, index) for index, file_id in enumerate(file_ids)]
    )
    pg_engine = object()

    with patch(
        "services.tools.image_inspection_provenance.get_successful_inspect_image_calls_for_node",
        new=query,
    ):
        enriched = await enrich_message_with_inspection_provenance(
            persisted_message,
            pg_engine=pg_engine,
            user_id="11111111-1111-1111-1111-111111111111",
            graph_id="22222222-2222-2222-2222-222222222222",
            node_id="node-1",
        )

    query.assert_awaited_once_with(
        pg_engine,
        user_id="11111111-1111-1111-1111-111111111111",
        graph_id="22222222-2222-2222-2222-222222222222",
        node_id="node-1",
        limit=MAX_INSPECTION_PROVENANCE_ENTRIES,
    )
    assert persisted_message.content[0].text == "Visible answer"
    model_text = enriched.content[0].text or ""
    assert model_text.startswith("Visible answer")
    assert model_text.count('tool_name="inspect_image"') == MAX_INSPECTION_PROVENANCE_ENTRIES
    assert 'status="success"' in model_text
    assert file_ids[0] in model_text
    assert file_ids[-1] not in model_text
    assert "supplied transiently through inspect_image" in model_text
    assert "not retained in conversation history" in model_text
    assert "Call inspect_image again" in model_text
    for private_value in (
        "/private/",
        "secret-hash",
        "data:image",
        "c2VjcmV0",
        "private model context",
        "inspection_bytes",
    ):
        assert private_value not in model_text


@pytest.mark.anyio
async def test_image_inspection_provenance_is_added_during_history_reconstruction():
    visible_message = Message(
        role=MessageRoleEnum.assistant,
        content=[MessageContent(type=MessageContentTypeEnum.text, text="Visible answer")],
    )
    enriched_message = visible_message.model_copy(deep=True)
    enriched_message.content[
        0
    ].text += "\n<internal_tool_provenance>safe</internal_tool_provenance>"
    provenance = AsyncMock(return_value=enriched_message)
    pg_engine = object()

    with (
        patch(
            "services.graph_service.get_connected_prompt_nodes",
            new=AsyncMock(return_value=[SimpleNamespace(id="prompt-1")]),
        ),
        patch(
            "services.graph_service.get_nodes_by_ids",
            new=AsyncMock(
                return_value=[
                    SimpleNamespace(id="prompt-1"),
                    SimpleNamespace(id="generator-1"),
                ]
            ),
        ),
        patch("services.graph_service.extract_context_prompt", return_value="User prompt"),
        patch("services.graph_service.extract_context_github", new=AsyncMock(return_value="")),
        patch("services.graph_service.extract_context_attachment", new=AsyncMock(return_value=[])),
        patch(
            "services.graph_service.node_to_message", new=AsyncMock(return_value=visible_message)
        ),
        patch(
            "services.graph_service.enrich_message_with_inspection_provenance",
            new=provenance,
        ),
    ):
        messages = await construct_message_from_generator_node(
            pg_engine=pg_engine,
            neo4j_driver=object(),
            graph_id="graph-1",
            user_id="user-1",
            git_http_client=object(),
            generator_node_id="generator-1",
            view="full",
            clean_text=CleanTextOption.REMOVE_TAG_AND_TEXT,
            add_assistant_message=True,
        )

    provenance.assert_awaited_once_with(
        visible_message,
        pg_engine=pg_engine,
        user_id="user-1",
        graph_id="graph-1",
        node_id="generator-1",
    )
    assert messages is not None
    assert messages[-1].content[0].text == enriched_message.content[0].text
    assert visible_message.content[0].text == "Visible answer"
