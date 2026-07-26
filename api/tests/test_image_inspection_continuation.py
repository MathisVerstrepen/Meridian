import json
from types import SimpleNamespace

import pytest
from services.openrouter import _process_tool_calls_and_continue
from services.providers.anthropic_protocol import build_anthropic_messages
from services.tools.runtime_results import ToolExecutionEnvelope, TransientImageContent


@pytest.mark.anyio
async def test_image_inspection_continuation_orders_results_before_transient_images(monkeypatch):
    persisted_calls = []

    async def fake_create_tool_call(*args, **kwargs):
        persisted_calls.append(kwargs)
        return SimpleNamespace(id=f"audit-{len(persisted_calls)}")

    async def inspect_handler(arguments, req):
        file_id = arguments["file_id"]
        return ToolExecutionEnvelope(
            {"success": True, "file_id": file_id, "inspection_bytes": 3},
            (TransientImageContent(file_id, "data:image/jpeg;base64,YWJj"),),
        )

    async def ordinary_handler(arguments, req):
        return {"success": True, "value": arguments["value"]}

    monkeypatch.setitem(
        __import__("services.openrouter", fromlist=["TOOL_HANDLERS_BY_NAME"]).__dict__[
            "TOOL_HANDLERS_BY_NAME"
        ],
        "inspect_image",
        inspect_handler,
    )
    monkeypatch.setitem(
        __import__("services.openrouter", fromlist=["TOOL_HANDLERS_BY_NAME"]).__dict__[
            "TOOL_HANDLERS_BY_NAME"
        ],
        "ordinary_test_tool",
        ordinary_handler,
    )
    monkeypatch.setattr("services.openrouter.create_tool_call", fake_create_tool_call)
    calls = [
        {
            "index": 0,
            "id": "inspect-1",
            "type": "function",
            "function": {"name": "inspect_image", "arguments": json.dumps({"file_id": "id-1"})},
        },
        {
            "index": 1,
            "id": "other-1",
            "type": "function",
            "function": {"name": "ordinary_test_tool", "arguments": '{"value":1}'},
        },
    ]
    req = SimpleNamespace(
        graph_id="graph",
        node_id="node",
        user_id="user",
        pg_engine=None,
        model_id="model",
        messages=[],
    )

    result = await _process_tool_calls_and_continue(calls, [], req, None)

    assert [message["role"] for message in result.messages] == [
        "assistant",
        "tool",
        "tool",
        "user",
    ]
    assert "data:image" not in result.messages[1]["content"]
    assert result.feedback_strings == [""]
    assert result.messages[-1]["content"][1]["image_url"]["url"].startswith("data:image/")
    assert len(persisted_calls) == 2
    assert all("data:image" not in json.dumps(call) for call in persisted_calls)
    assert persisted_calls[0]["result"] == {
        "success": True,
        "file_id": "id-1",
        "inspection_bytes": 3,
    }


@pytest.mark.anyio
async def test_image_inspection_continuation_caps_successes_per_round(monkeypatch):
    executed = []

    async def inspect_handler(arguments, req):
        file_id = arguments["file_id"]
        executed.append(file_id)
        return ToolExecutionEnvelope(
            {"success": True, "file_id": file_id},
            (TransientImageContent(file_id, "data:image/jpeg;base64,YWJj"),),
        )

    monkeypatch.setitem(
        __import__("services.openrouter", fromlist=["TOOL_HANDLERS_BY_NAME"]).__dict__[
            "TOOL_HANDLERS_BY_NAME"
        ],
        "inspect_image",
        inspect_handler,
    )
    calls = [
        {
            "index": index,
            "id": f"inspect-{index}",
            "type": "function",
            "function": {
                "name": "inspect_image",
                "arguments": json.dumps({"file_id": f"id-{index}"}),
            },
        }
        for index in range(3)
    ]
    req = SimpleNamespace(
        graph_id=None,
        node_id=None,
        user_id="user",
        pg_engine=None,
        model_id="model",
        messages=[],
    )

    result = await _process_tool_calls_and_continue(calls, [], req, None)

    assert executed == ["id-0", "id-1"]
    assert "limit reached" in result.messages[3]["content"]
    image_parts = [
        part for part in result.messages[-1]["content"] if part.get("type") == "image_url"
    ]
    assert len(image_parts) == 2


def test_image_inspection_anthropic_conversion_combines_tool_result_and_image():
    messages = [
        {"role": "tool", "tool_call_id": "call-1", "content": '{"success":true}'},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Inspection image:"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,YWJj"},
                },
            ],
        },
    ]
    _, converted = build_anthropic_messages(messages)
    blocks = converted[0]["content"]
    assert [block["type"] for block in blocks] == ["tool_result", "text", "image"]
    assert blocks[-1]["source"] == {
        "type": "base64",
        "media_type": "image/jpeg",
        "data": "YWJj",
    }
