import ast
import asyncio
import base64
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.inference import InferenceCredentials


def _load_provider_image_generation_functions():
    source_path = Path(__file__).resolve().parents[1] / "app/services/provider_image_generation.py"
    module = ast.parse(source_path.read_text())
    selected_names = {
        "OPENROUTER_IMAGE_GENERATION_URL",
        "OPENROUTER_IMAGE_HEADERS",
        "ImageGenerationProviderError",
        "GeneratedImageResult",
        "_extract_error_message",
        "_normalize_openrouter_headers",
        "_openrouter_video_download_headers",
        "_build_openrouter_image_modalities",
        "_generate_image_with_openrouter",
    }
    selected_nodes = []
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in selected_names for target in node.targets
        ):
            selected_nodes.append(node)
        if (
            isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name in selected_names
        ):
            selected_nodes.append(node)

    isolated_module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace = {
        "Any": Any,
        "base64": base64,
        "dataclass": dataclass,
        "httpx": httpx,
        "InferenceCredentials": InferenceCredentials,
    }
    exec(compile(isolated_module, str(source_path), "exec"), namespace)
    return namespace


_provider_image_generation_functions = _load_provider_image_generation_functions()
_build_openrouter_image_modalities = _provider_image_generation_functions[
    "_build_openrouter_image_modalities"
]
_generate_image_with_openrouter = _provider_image_generation_functions[
    "_generate_image_with_openrouter"
]
_openrouter_video_download_headers = _provider_image_generation_functions[
    "_openrouter_video_download_headers"
]


def test_openrouter_image_modalities_match_model_outputs():
    assert _build_openrouter_image_modalities(["image"]) == ["image"]
    assert _build_openrouter_image_modalities(["text", "image"]) == ["image", "text"]
    assert _build_openrouter_image_modalities(None) == ["image"]


def test_openrouter_image_only_models_request_image_modality_only():
    class FakeResponse:
        status_code = 200

        def json(self):
            encoded = base64.b64encode(b"image-bytes").decode("utf-8")
            return {
                "choices": [
                    {
                        "message": {
                            "images": [{"image_url": {"url": f"data:image/png;base64,{encoded}"}}]
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self):
            self.payload = None

        async def post(self, url, headers, json):
            self.payload = json
            return FakeResponse()

    fake_client = FakeClient()
    result = asyncio.run(
        _generate_image_with_openrouter(
            credentials=InferenceCredentials(openrouter_api_key="test-key"),
            model="sourceful/riverflow-v2-pro",
            message_content="Create an image",
            aspect_ratio="1:1",
            resolution="1K",
            source_image_ids=[],
            output_modalities=["image"],
            http_client=fake_client,
        )
    )

    assert fake_client.payload["modalities"] == ["image"]
    assert result.image_bytes == b"image-bytes"


def test_openrouter_video_download_headers_only_for_openrouter_api_urls():
    headers = {"Authorization": "Bearer test-key"}

    assert (
        _openrouter_video_download_headers(
            "https://openrouter.ai/api/v1/videos/job-123/content?index=0",
            headers,
        )
        == headers
    )
    assert _openrouter_video_download_headers("https://cdn.example.com/video.mp4", headers) is None
