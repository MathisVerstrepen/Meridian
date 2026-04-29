import ast
import asyncio
import json
import sys
from pathlib import Path

import httpx


sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.inference import Architecture, ModelInfo, Pricing, ResponseModel


def _load_openrouter_req_class():
    source_path = Path(__file__).resolve().parents[1] / "app/services/openrouter.py"
    module = ast.parse(source_path.read_text())
    class_node = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "OpenRouterReq"
    )
    isolated_module = ast.Module(body=[class_node], type_ignores=[])
    namespace = {}
    exec(compile(isolated_module, str(source_path), "exec"), namespace)
    return namespace["OpenRouterReq"]


OpenRouterReq = _load_openrouter_req_class()


def _load_openrouter_model_mapping_functions():
    source_path = Path(__file__).resolve().parents[1] / "app/services/openrouter.py"
    module = ast.parse(source_path.read_text())
    selected_names = {
        "BRAND_ICON_ALIASES",
        "BRAND_ICONS",
        "OPENROUTER_FRONTEND_MODELS_URL",
        "OPENROUTER_MODELS_URL",
        "_fetch_openrouter_models",
        "_get_openrouter_brand_icon",
        "_normalize_openrouter_pricing",
        "_build_openrouter_modality",
        "_map_frontend_openrouter_model",
        "_map_frontend_openrouter_models",
        "_map_v1_openrouter_models",
        "list_available_models",
    }
    selected_nodes = []
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in selected_names for target in node.targets
        ):
            selected_nodes.append(node)
        if (
            isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name in selected_names
        ):
            selected_nodes.append(node)

    isolated_module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace = {
        "Any": object,
        "Architecture": Architecture,
        "OpenRouterReq": OpenRouterReq,
        "ModelInfo": ModelInfo,
        "Pricing": Pricing,
        "ResponseModel": ResponseModel,
        "httpx": httpx,
        "json": json,
        "logger": type(
            "Logger",
            (),
            {
                "info": lambda *args, **kwargs: None,
                "warning": lambda *args, **kwargs: None,
                "error": lambda *args, **kwargs: None,
            },
        )(),
    }
    exec(compile(isolated_module, str(source_path), "exec"), namespace)
    return namespace


_openrouter_mapping_functions = _load_openrouter_model_mapping_functions()
_map_frontend_openrouter_models = _openrouter_mapping_functions["_map_frontend_openrouter_models"]
_map_v1_openrouter_models = _openrouter_mapping_functions["_map_v1_openrouter_models"]
list_available_models = _openrouter_mapping_functions["list_available_models"]


def test_openrouter_request_headers_are_isolated_per_instance():
    first_request = OpenRouterReq(api_key="first-key")
    second_request = OpenRouterReq(api_key="second-key")

    first_request.headers["HTTP-Referer"] = "https://first.example"

    assert first_request.headers["Authorization"] == "Bearer first-key"
    assert second_request.headers["Authorization"] == "Bearer second-key"
    assert second_request.headers["HTTP-Referer"] == "https://meridian.diikstra.fr/"
    assert first_request.headers is not second_request.headers


def test_frontend_openrouter_models_are_mapped_to_response_model():
    models = _map_frontend_openrouter_models(
        {
            "data": [
                {
                    "slug": "bytedance-seed/seedream-4.5",
                    "name": "ByteDance Seed: Seedream 4.5",
                    "created_at": "2026-04-24T17:31:33.253+00:00",
                    "context_length": 1050000,
                    "input_modalities": ["file", "image", "text"],
                    "output_modalities": ["text"],
                    "instruct_type": None,
                    "endpoint": {
                        "context_length": 1050000,
                        "supported_parameters": ["tools", "response_format"],
                        "pricing": {
                            "prompt": "0.000005",
                            "completion": "0.00003",
                            "image_output": "0.15",
                            "web_search": "0.01",
                        },
                    },
                }
            ]
        }
    )

    model = models.data[0]
    assert model.id == "bytedance-seed/seedream-4.5"
    assert model.name == "ByteDance Seed: Seedream 4.5"
    assert model.created == "2026-04-24T17:31:33.253+00:00"
    assert model.context_length == 1050000
    assert model.icon == "bytedance"
    assert model.architecture.input_modalities == ["file", "image", "text"]
    assert model.architecture.modality == "file+image+text->text"
    assert model.pricing.prompt == "0.000005"
    assert model.pricing.completion == "0.00003"
    assert model.pricing.image == "0.15"
    assert model.pricing.web_search == "0.01"
    assert model.toolsSupport is True


def test_frontend_openrouter_model_mapper_skips_unavailable_models():
    models = _map_frontend_openrouter_models(
        {
            "data": [
                {"slug": "openai/hidden", "name": "Hidden", "hidden": True},
                {
                    "slug": "openai/disabled",
                    "name": "Disabled",
                    "endpoint": {"is_disabled": True},
                },
                {
                    "slug": "google/available",
                    "name": "Available",
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                    "endpoint": {"pricing": {"prompt": "1", "completion": "2"}},
                },
            ]
        }
    )

    assert [model.id for model in models.data] == ["google/available"]


def test_v1_openrouter_model_mapper_preserves_existing_enrichment():
    models = _map_v1_openrouter_models(
        {
            "data": [
                {
                    "id": "google/gemini-2.5-flash",
                    "name": "Google: Gemini 2.5 Flash",
                    "architecture": {
                        "input_modalities": ["text"],
                        "modality": "text->text",
                        "output_modalities": ["text"],
                        "tokenizer": "Gemini",
                    },
                    "pricing": {"prompt": "0.1", "completion": "0.2"},
                    "supported_parameters": ["tools"],
                }
            ]
        }
    )

    model = models.data[0]
    assert model.icon == "google"
    assert model.toolsSupport is True


def test_list_available_models_falls_back_to_v1_when_frontend_fetch_fails():
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self):
            self.urls = []

        async def get(self, url, headers):
            self.urls.append(url)
            if url.endswith("/api/frontend/models"):
                return FakeResponse(429, {})
            return FakeResponse(
                200,
                {
                    "data": [
                        {
                            "id": "google/gemini-2.5-flash",
                            "name": "Google: Gemini 2.5 Flash",
                            "architecture": {
                                "input_modalities": ["text"],
                                "modality": "text->text",
                                "output_modalities": ["text"],
                                "tokenizer": "Gemini",
                            },
                            "pricing": {"prompt": "0.1", "completion": "0.2"},
                            "supported_parameters": ["tools"],
                        }
                    ]
                },
            )

    fake_client = FakeClient()
    models = asyncio.run(
        list_available_models(OpenRouterReq(api_key="test-key", http_client=fake_client))
    )

    assert fake_client.urls == [
        "https://openrouter.ai/api/frontend/models",
        "https://openrouter.ai/api/v1/models",
    ]
    assert models.data[0].id == "google/gemini-2.5-flash"
    assert models.data[0].toolsSupport is True
