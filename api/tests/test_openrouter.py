import ast
from pathlib import Path


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


def test_openrouter_request_headers_are_isolated_per_instance():
    first_request = OpenRouterReq(api_key="first-key")
    second_request = OpenRouterReq(api_key="second-key")

    first_request.headers["HTTP-Referer"] = "https://first.example"

    assert first_request.headers["Authorization"] == "Bearer first-key"
    assert second_request.headers["Authorization"] == "Bearer second-key"
    assert second_request.headers["HTTP-Referer"] == "https://meridian.diikstra.fr/"
    assert first_request.headers is not second_request.headers
