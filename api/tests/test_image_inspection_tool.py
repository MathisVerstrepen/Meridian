import io
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from fastapi import FastAPI
from models.inference import Architecture, InferenceCredentials, ModelInfo, Pricing, ResponseModel
from models.message import NodeTypeEnum, ToolEnum
from PIL import Image
from services.inference import get_available_models_for_user, model_supports_image_inspection
from services.inference_requests import build_inference_request
from services.tools.image_inspection import MAX_INSPECTION_EDGE, inspect_image
from services.tools.registry import get_openrouter_tools


def _image_bytes(size: tuple[int, int] = (2400, 1200)) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 128)).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_image_inspection_owner_query_and_bounded_transient_result(tmp_path, monkeypatch):
    user_id = str(uuid.uuid4())
    file_id = uuid.uuid4()
    storage_root = tmp_path / "data" / "user_files" / user_id
    storage_root.mkdir(parents=True)
    image_path = storage_root / "generated.png"
    image_path.write_bytes(_image_bytes())
    record = SimpleNamespace(
        type="file",
        storage_provider="local",
        file_path="generated.png",
        content_type="image/png",
        size=image_path.stat().st_size,
    )
    observed = {}

    async def fake_get_file_by_id(engine, requested_id, *, user_id):
        observed.update(engine=engine, requested_id=requested_id, user_id=user_id)
        return record

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "services.tools.image_inspection.get_file_by_id",
        fake_get_file_by_id,
    )
    req = SimpleNamespace(
        image_inspection_enabled=True,
        pg_engine="engine",
        user_id=user_id,
    )

    result = await inspect_image({"file_id": str(file_id)}, req)

    assert result.persisted_result["success"] is True
    assert result.persisted_result["inspection_width"] <= MAX_INSPECTION_EDGE
    assert result.persisted_result["inspection_height"] <= MAX_INSPECTION_EDGE
    assert "data_uri" not in str(result.persisted_result)
    assert result.transient_images[0].data_uri.startswith("data:image/jpeg;base64,")
    assert observed == {"engine": "engine", "requested_id": file_id, "user_id": user_id}


@pytest.mark.anyio
async def test_image_inspection_rejects_disabled_malformed_and_escaped_paths(tmp_path, monkeypatch):
    req = SimpleNamespace(image_inspection_enabled=False, pg_engine="engine", user_id="user")
    disabled = await inspect_image({"file_id": str(uuid.uuid4())}, req)
    assert disabled.persisted_result["error"]

    req.image_inspection_enabled = True
    malformed = await inspect_image({"file_id": "../../secret"}, req)
    assert malformed.persisted_result == {"error": "A valid file UUID is required."}

    async def fake_get_file_by_id(*args, **kwargs):
        return SimpleNamespace(
            type="file",
            storage_provider="local",
            file_path="../foreign.png",
            content_type="image/png",
            size=10,
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "services.tools.image_inspection.get_file_by_id",
        fake_get_file_by_id,
    )
    escaped = await inspect_image({"file_id": str(uuid.uuid4())}, req)
    assert escaped.persisted_result["error"] == "Image is unavailable."
    assert "foreign" not in str(escaped.persisted_result)


def test_image_inspection_schema_is_internal_and_capability_gated():
    ordinary = get_openrouter_tools([ToolEnum.IMAGE_GENERATION])
    internal = get_openrouter_tools([ToolEnum.IMAGE_GENERATION], include_image_inspection=True)
    assert "inspect_image" not in [tool["function"]["name"] for tool in ordinary]
    assert "inspect_image" in [tool["function"]["name"] for tool in internal]
    assert "inspect_image" not in [item.value for item in ToolEnum]

    model = {
        "id": "gemini_cli:vision-model",
        "architecture": {"input_modalities": ["text", "image"]},
        "supportsMeridianTools": True,
        "supportedMeridianToolNames": [ToolEnum.IMAGE_GENERATION.value],
    }
    assert model_supports_image_inspection(model["id"], [model])
    assert not model_supports_image_inspection("gemini_cli:missing", [model])
    assert not model_supports_image_inspection(
        "github-copilot/vision-model", [{**model, "id": "github-copilot/vision-model"}]
    )


@pytest.mark.anyio
async def test_image_inspection_raw_openrouter_catalog_is_normalized_for_chat_payload():
    model_id = "google/gemini-3.6-flash"
    raw_model = ModelInfo(
        id=model_id,
        name="Gemini 3.6 Flash",
        architecture=Architecture(
            input_modalities=["text", "image"],
            output_modalities=["text"],
            modality="text+image->text",
            tokenizer="Gemini",
        ),
        pricing=Pricing(prompt="0", completion="0"),
        toolsSupport=True,
    )
    assert raw_model.supportsMeridianTools is False
    assert raw_model.supportedMeridianToolNames == []

    app = FastAPI()
    app.state.pg_engine = object()
    app.state.available_models = ResponseModel(data=[raw_model])
    with patch(
        "services.inference.get_user_inference_credentials",
        new=AsyncMock(return_value=InferenceCredentials()),
    ):
        available_models = (await get_available_models_for_user(app, "user-1")).data

    normalized_model = available_models[0]
    assert normalized_model.supportsMeridianTools is True
    assert ToolEnum.IMAGE_GENERATION.value in normalized_model.supportedMeridianToolNames

    request = build_inference_request(
        credentials=InferenceCredentials(openrouter_api_key="test-key"),
        model=model_id,
        messages=[{"role": "user", "content": "Create and inspect an image."}],
        config=GraphConfigUpdate(),
        user_id="user-1",
        pg_engine=app.state.pg_engine,
        node_type=NodeTypeEnum.TEXT_TO_TEXT,
        http_client=object(),
        selected_tools=[ToolEnum.IMAGE_GENERATION],
        available_models=available_models,
    )

    tool_names = [tool["function"]["name"] for tool in request.get_payload()["tools"]]
    assert "inspect_image" in tool_names
