import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from models.chatDTO import EffortEnum
from models.message import Message, NodeTypeEnum, ToolEnum
from models.usersDTO import ModelsSettings
from pydantic import BaseModel
from services.reasoning_effort import (
    ALL_REASONING_EFFORTS_MASK,
    get_model_reasoning_efforts,
    reasoning_efforts_mask_from_catalog,
    resolve_reasoning_effort,
)


def _load_openrouter_req_chat_class():
    source_path = Path(__file__).resolve().parents[1] / "app/services/openrouter.py"
    module = ast.parse(source_path.read_text())
    selected_nodes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name in {"OpenRouterReq", "OpenRouterReqChat"}
    ]
    namespace = {
        "Any": Any,
        "Optional": Optional,
        "httpx": httpx,
        "BaseModel": BaseModel,
        "GraphConfigUpdate": GraphConfigUpdate,
        "Message": Message,
        "NodeTypeEnum": NodeTypeEnum,
        "ToolEnum": ToolEnum,
        "SandboxInputFileReference": object,
        "SQLAlchemyAsyncEngine": object,
        "OPENROUTER_CHAT_URL": "https://openrouter.test/chat",
        "build_openrouter_response_format": lambda schema: {},
        "get_openrouter_tools": lambda tools, *, include_image_inspection=False: [],
        "resolve_reasoning_effort": resolve_reasoning_effort,
    }
    isolated_module = ast.Module(body=selected_nodes, type_ignores=[])
    exec(compile(isolated_module, str(source_path), "exec"), namespace)
    return namespace["OpenRouterReqChat"]


OpenRouterReqChat = _load_openrouter_req_chat_class()


def _load_function(source_file: str, function_name: str, namespace: dict):
    source_path = Path(__file__).resolve().parents[1] / f"app/services/{source_file}"
    module = ast.parse(source_path.read_text())
    function_node = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    isolated_module = ast.Module(body=[function_node], type_ignores=[])
    exec(compile(isolated_module, str(source_path), "exec"), namespace)
    return namespace[function_name]


_resolve_visualise_reasoning_efforts = _load_function(
    "tools/visualise.py",
    "_resolve_visualise_reasoning_efforts",
    {},
)
_build_context_merger_summarizer_config = _load_function(
    "context_merger_service.py",
    "_build_context_merger_summarizer_config",
    {"GraphConfigUpdate": GraphConfigUpdate},
)


@pytest.mark.parametrize(
    ("reasoning", "expected"),
    [
        ({"supported_efforts": ["max", "high", "none"]}, 69),
        ({"supported_efforts": []}, 0),
        ({"supported_efforts": None}, ALL_REASONING_EFFORTS_MASK),
        ({}, 0),
        ({"supported_efforts": ["future"]}, -1),
        ({"supported_efforts": "high"}, -1),
        ("malformed", -1),
        (None, 0),
    ],
)
def test_catalog_reasoning_effort_masks(reasoning, expected):
    assert reasoning_efforts_mask_from_catalog(reasoning, "supported_efforts") == expected


@pytest.mark.parametrize(
    ("configured", "mask", "prefer_higher", "expected"),
    [
        (EffortEnum.HIGH, 4, True, EffortEnum.HIGH),
        (EffortEnum.MAX, 4 | 8 | 16, True, EffortEnum.HIGH),
        (EffortEnum.MEDIUM, 4 | 16, True, EffortEnum.HIGH),
        (EffortEnum.MEDIUM, 4 | 16, False, EffortEnum.LOW),
        (EffortEnum.NONE, 32, True, EffortEnum.MINIMAL),
        (EffortEnum.MAX, -1, True, EffortEnum.MAX),
        (EffortEnum.MAX, 128, True, EffortEnum.MAX),
        (EffortEnum.MAX, 0, True, None),
    ],
)
def test_reasoning_effort_resolver(configured, mask, prefer_higher, expected):
    assert resolve_reasoning_effort(configured, mask, prefer_higher=prefer_higher) == expected


def test_exact_model_reasoning_effort_lookup_preserves_unknown():
    models = [
        {"id": "known", "reasoningEfforts": 4},
        {"id": "invalid", "reasoningEfforts": 128},
    ]

    assert get_model_reasoning_efforts("known", models) == 4
    assert get_model_reasoning_efforts("invalid", models) == -1
    assert get_model_reasoning_efforts("missing", models) == -1


def test_visualise_does_not_reuse_parent_mask_for_a_different_child_model():
    parent_request = SimpleNamespace(model="openai/parent", reasoning_efforts=4)

    assert _resolve_visualise_reasoning_efforts(parent_request, "google/visualise") == -1
    assert _resolve_visualise_reasoning_efforts(parent_request, "openai/parent") == 4


def test_context_merger_summarizer_only_inherits_reasoning_config():
    graph_config = GraphConfigUpdate(
        reasoning_effort=EffortEnum.MAX,
        prefer_higher_reasoning_effort=False,
        exclude_reasoning=True,
        max_tokens=1234,
        temperature=0.2,
        top_p=0.3,
        frequency_penalty=0.4,
    )

    summarizer_config = _build_context_merger_summarizer_config(graph_config)

    assert summarizer_config.reasoning_effort == EffortEnum.MAX
    assert summarizer_config.prefer_higher_reasoning_effort is False
    assert summarizer_config.exclude_reasoning is True
    assert summarizer_config.max_tokens is None
    assert summarizer_config.temperature == 0.7
    assert summarizer_config.top_p == 1.0
    assert summarizer_config.frequency_penalty == 0.0


def test_effort_enum_and_settings_default_support_all_labels():
    assert [effort.value for effort in EffortEnum] == [
        "max",
        "xhigh",
        "high",
        "medium",
        "low",
        "minimal",
        "none",
    ]
    settings = ModelsSettings(defaultModel="openai/test", excludeReasoning=False)

    assert settings.preferHigherReasoningEffort is True
    assert GraphConfigUpdate().prefer_higher_reasoning_effort is True


def _payload(mask: int, *, is_title_generation: bool = False, prefer_higher: bool = True):
    config = GraphConfigUpdate(
        reasoning_effort=EffortEnum.MEDIUM,
        exclude_reasoning=True,
        prefer_higher_reasoning_effort=prefer_higher,
    )
    request = OpenRouterReqChat(
        api_key="test-key",
        model="openai/test",
        messages=[],
        config=config,
        user_id="user-id",
        pg_engine=None,
        http_client=object(),
        is_title_generation=is_title_generation,
        reasoning_efforts=mask,
    )
    return request.get_payload()


def test_openrouter_payload_resolves_effort_and_preserves_reasoning_flags():
    payload = _payload(4 | 16)

    assert payload["reasoning"] == {"exclude": True, "enabled": True, "effort": EffortEnum.HIGH}


def test_openrouter_payload_omits_only_effort_for_explicit_zero_capability():
    payload = _payload(0, is_title_generation=True)

    assert payload["reasoning"] == {"exclude": True, "enabled": False}


def test_openrouter_payload_preserves_unknown_capability_effort():
    payload = _payload(-1)

    assert payload["reasoning"]["effort"] == EffortEnum.MEDIUM
