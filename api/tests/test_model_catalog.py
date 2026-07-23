import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelDiscoveryWarning,
    ModelInfo,
    Pricing,
    ResponseModel,
)
from models.message import ToolEnum
from services.model_catalog import (
    CAPABILITY_IMAGE_OUTPUT,
    CAPABILITY_MERIDIAN_TOOLS,
    CAPABILITY_NATIVE_TOOLS,
    CAPABILITY_STRUCTURED_OUTPUTS,
    CAPABILITY_SUBSCRIPTION,
    CAPABILITY_TEXT_OUTPUT,
    CAPABILITY_VIDEO_OUTPUT,
    MERIDIAN_TOOL_BITS,
    encode_model_catalog,
)


async def _stub_dependency(*args: object, **kwargs: object) -> object:
    return None


class _StubOpenRouterReq:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


stub_modules = {
    "services.auth": ModuleType("services.auth"),
    "services.inference": ModuleType("services.inference"),
    "services.openrouter": ModuleType("services.openrouter"),
}
stub_modules["services.auth"].get_current_user_id = _stub_dependency  # type: ignore[attr-defined]
stub_modules["services.inference"].get_available_models_for_user = (  # type: ignore[attr-defined]
    _stub_dependency
)
stub_modules["services.openrouter"].OpenRouterReq = _StubOpenRouterReq  # type: ignore[attr-defined]
stub_modules["services.openrouter"].list_available_models = _stub_dependency  # type: ignore[attr-defined]
original_modules = {name: sys.modules.get(name) for name in stub_modules}
try:
    sys.modules.update(stub_modules)
    from routers import models as models_router
finally:
    for module_name, original_module in original_modules.items():
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module

get_current_user_id = models_router.get_current_user_id


def _model(**overrides: object) -> ModelInfo:
    values: dict[str, object] = {
        "architecture": Architecture(
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="test",
        ),
        "id": "openrouter/test-model",
        "name": "Test Model",
        "pricing": Pricing(prompt="1.25", completion="2.5"),
        "supportsStructuredOutputs": False,
        "reasoningEfforts": 0,
    }
    values.update(overrides)
    return ModelInfo(**values)


def test_version_1_bit_assignments_are_frozen() -> None:
    assert CAPABILITY_TEXT_OUTPUT == 1
    assert CAPABILITY_IMAGE_OUTPUT == 2
    assert CAPABILITY_VIDEO_OUTPUT == 4
    assert CAPABILITY_STRUCTURED_OUTPUTS == 8
    assert CAPABILITY_NATIVE_TOOLS == 16
    assert CAPABILITY_MERIDIAN_TOOLS == 32
    assert CAPABILITY_SUBSCRIPTION == 64
    assert MERIDIAN_TOOL_BITS == {
        ToolEnum.WEB_SEARCH.value: 1,
        ToolEnum.LINK_EXTRACTION.value: 2,
        ToolEnum.IMAGE_GENERATION.value: 4,
        ToolEnum.EXECUTE_CODE.value: 8,
        ToolEnum.VISUALISE.value: 16,
        ToolEnum.ASK_USER.value: 32,
    }


@pytest.mark.parametrize(
    ("modalities", "expected"),
    [
        (["text"], 1),
        (["image"], 2),
        (["video"], 4),
        (["text", "image"], 3),
        (["text", "video"], 5),
        (["image", "video"], 6),
        (["text", "image", "video"], 7),
    ],
)
def test_output_capabilities_are_encoded_independently(
    modalities: list[str], expected: int
) -> None:
    model = _model(
        architecture=Architecture(
            input_modalities=["text"],
            modality="test",
            output_modalities=modalities,
            tokenizer="test",
        )
    )

    encoded = encode_model_catalog(ResponseModel(data=[model]))

    assert encoded.data[0].capabilities == expected


def test_encoder_combines_capabilities_and_known_meridian_tools() -> None:
    model = _model(
        billingType=BillingTypeEnum.SUBSCRIPTION,
        supportsStructuredOutputs=True,
        toolsSupport=True,
        supportsMeridianTools=True,
        supportedMeridianToolNames=[tool.value for tool in ToolEnum] + ["future_tool"],
        architecture=Architecture(
            input_modalities=["text"],
            modality="test",
            output_modalities=["text", "image", "video"],
            tokenizer="test",
        ),
    )

    encoded = encode_model_catalog(ResponseModel(data=[model]))

    assert encoded.data[0].capabilities == 127
    assert encoded.data[0].supportedTools == 63


def test_meridian_support_is_independent_of_known_tool_bits() -> None:
    model = _model(
        supportsMeridianTools=True,
        supportedMeridianToolNames=["future_tool"],
    )

    encoded = encode_model_catalog(ResponseModel(data=[model]))

    assert encoded.data[0].capabilities == CAPABILITY_TEXT_OUTPUT | CAPABILITY_MERIDIAN_TOOLS
    assert encoded.data[0].supportedTools == 0


def test_encoder_omits_none_and_declared_defaults_without_mutating_input() -> None:
    response = ResponseModel(
        data=[
            _model(
                icon=None,
                provider=InferenceProviderEnum.OPENROUTER,
                created=None,
                context_length=None,
                pricing=Pricing(prompt="1.25", completion="2.5", image=None),
                supportedMeridianToolNames=[],
                reasoningEfforts=0,
            )
        ]
    )
    before = response.model_dump(mode="json")

    wire = encode_model_catalog(response).model_dump(
        mode="json", exclude_none=True, exclude_defaults=True
    )

    assert response.model_dump(mode="json") == before
    assert wire == {
        "version": 1,
        "data": [
            {
                "id": "openrouter/test-model",
                "name": "Test Model",
                "pricing": {"prompt": "1.25", "completion": "2.5"},
                "capabilities": 1,
            }
        ],
    }


def test_encoder_preserves_warning_fields_and_reasoning_semantics() -> None:
    warning = ModelDiscoveryWarning(
        provider=InferenceProviderEnum.GITHUB_COPILOT,
        title="Discovery warning",
        message="Models may be incomplete.",
        actionLabel="Reconnect",
        actionUrl="/settings?tab=Providers",
    )
    response = ResponseModel(data=[_model(reasoningEfforts=-1)], warnings=[warning])

    encoded = encode_model_catalog(response)

    assert encoded.data[0].reasoningEfforts == -1
    assert encoded.warnings == [warning]


@pytest.mark.parametrize("reasoning_efforts", [-1, 0, 42])
def test_encoder_preserves_reasoning_mask_values(reasoning_efforts: int) -> None:
    encoded = encode_model_catalog(ResponseModel(data=[_model(reasoningEfforts=reasoning_efforts)]))

    assert encoded.data[0].reasoningEfforts == reasoning_efforts


def test_models_endpoint_serializes_only_the_compact_contract() -> None:
    internal_response = ResponseModel(
        data=[
            _model(
                icon=None,
                context_length=None,
                reasoningEfforts=-1,
                supportsMeridianTools=True,
                supportedMeridianToolNames=[ToolEnum.WEB_SEARCH.value],
            )
        ]
    )
    app = FastAPI()
    app.state.available_models = []
    app.include_router(models_router.router)
    app.dependency_overrides[get_current_user_id] = lambda: "test-user"

    with patch.object(
        models_router,
        "get_available_models_for_user",
        new=AsyncMock(return_value=internal_response),
    ):
        response = TestClient(app).get("/models")

    assert response.status_code == 200
    assert response.json() == {
        "version": 1,
        "data": [
            {
                "id": "openrouter/test-model",
                "name": "Test Model",
                "pricing": {"prompt": "1.25", "completion": "2.5"},
                "capabilities": 33,
                "supportedTools": 1,
                "reasoningEfforts": -1,
            }
        ],
    }
