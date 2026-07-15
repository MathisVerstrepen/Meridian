import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
sys.path.append(str(APP_ROOT))
sys.path.append(str(FIXTURE_ROOT))

from graph_response import GRAPH_ID, USER_ID, build_graph_fixture, build_small_graph_fixture
from services.graph_response import encode_graph_editor_response


async def _stub_auth() -> str:
    return str(USER_ID)


auth_stub = ModuleType("services.auth")
auth_stub.get_current_user_id = _stub_auth  # type: ignore[attr-defined]
original_auth = sys.modules.get("services.auth")
try:
    sys.modules["services.auth"] = auth_stub
    from routers import graph as graph_router
finally:
    if original_auth is None:
        sys.modules.pop("services.auth", None)
    else:
        sys.modules["services.auth"] = original_auth

get_current_user_id = graph_router.get_current_user_id


def _wire_json() -> tuple[object, dict[str, object]]:
    complete_graph = build_small_graph_fixture()
    encoded = encode_graph_editor_response(complete_graph)
    wire = encoded.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    return complete_graph, wire


def _test_app() -> FastAPI:
    app = FastAPI()
    app.state.pg_engine = object()
    app.state.neo4j_driver = object()
    app.include_router(graph_router.router)
    app.dependency_overrides[get_current_user_id] = _stub_auth
    return app


def test_encoder_serializes_only_version_1_editor_fields_and_omits_defaults() -> None:
    complete_graph, wire = _wire_json()
    assert isinstance(wire, dict)
    graph = wire["graph"]
    nodes = wire["nodes"]
    edges = wire["edges"]
    assert isinstance(graph, dict)
    assert isinstance(nodes, list)
    assert isinstance(edges, list)

    assert wire["version"] == 1
    assert set(graph) == {
        "id",
        "name",
        "node_count",
        "folder_id",
        "workspace_id",
        "created_at",
        "updated_at",
        "temperature",
        "top_k",
        "presence_penalty",
        "reasoning_effort",
    }
    assert graph["created_at"] == "2026-07-15T12:30:00Z"
    assert graph["updated_at"] == "2026-07-15T12:45:00Z"
    assert "user_id" not in graph
    assert "graph_id" not in nodes[0]
    assert "graph_id" not in edges[0]
    assert "markerEnd" not in edges[0]
    assert "width" not in nodes[1]
    assert "height" not in nodes[1]
    assert "animated" not in edges[1]

    nested = nodes[0]["data"]["nested"]
    assert nested == {
        "null": None,
        "false": False,
        "zero": 0,
        "empty_string": "",
        "empty_object": {},
        "empty_array": [],
    }
    assert edges[0]["style"] == {"strokeWidth": 0, "visible": False}
    assert edges[0]["data"] == {"empty": "", "items": []}

    before = complete_graph.model_dump(mode="json")
    encoded = encode_graph_editor_response(complete_graph)
    assert complete_graph.model_dump(mode="json") == before
    assert encoded.nodes[0].data is complete_graph.nodes[0].data
    assert encoded.edges[0].style is complete_graph.edges[0].style
    assert encoded.edges[0].data is complete_graph.edges[0].data


def test_encoder_preserves_every_populated_editor_field() -> None:
    complete_graph = build_small_graph_fixture()
    graph = complete_graph.graph
    graph.description = "Description"
    graph.temporary = True
    graph.pinned = True
    graph.custom_instructions = ["Instruction"]
    graph.max_tokens = 4096
    graph.top_p = 0.9
    graph.frequency_penalty = -0.25
    graph.repetition_penalty = 1.1
    wire = encode_graph_editor_response(complete_graph).model_dump(
        mode="json", exclude_none=True, exclude_defaults=True
    )

    assert wire["graph"] == {
        "id": str(GRAPH_ID),
        "name": "Deterministic graph",
        "node_count": 30,
        "folder_id": "12345678-1234-5678-1234-567812345678",
        "workspace_id": "87654321-4321-8765-4321-876543218765",
        "description": "Description",
        "temporary": True,
        "pinned": True,
        "created_at": "2026-07-15T12:30:00Z",
        "updated_at": "2026-07-15T12:45:00Z",
        "custom_instructions": ["Instruction"],
        "max_tokens": 4096,
        "temperature": 0.25,
        "top_p": 0.9,
        "top_k": 40,
        "frequency_penalty": -0.25,
        "presence_penalty": 0.0,
        "repetition_penalty": 1.1,
        "reasoning_effort": "high",
    }
    assert wire["nodes"][7]["parent_node_id"] == "node-6"
    assert wire["nodes"][0]["width"] == "320px"
    assert wire["nodes"][0]["height"] == "180px"
    assert wire["edges"][0] == {
        "id": "edge-0",
        "source_node_id": "node-0",
        "target_node_id": "node-1",
        "source_handle_id": "source-0",
        "target_handle_id": "target-0",
        "type": "smoothstep",
        "label": "Edge 0",
        "animated": True,
        "style": {"strokeWidth": 0, "visible": False},
        "data": {"empty": "", "items": []},
    }


def test_encoder_omits_nullable_timestamps_without_inventing_values() -> None:
    complete_graph = build_small_graph_fixture()
    complete_graph.graph.created_at = None
    complete_graph.graph.updated_at = None
    complete_graph.graph.custom_instructions = None  # type: ignore[assignment]

    wire = encode_graph_editor_response(complete_graph).model_dump(
        mode="json", exclude_none=True, exclude_defaults=True
    )

    assert "created_at" not in wire["graph"]
    assert "updated_at" not in wire["graph"]
    assert "custom_instructions" not in wire["graph"]


def test_multi_megabyte_reply_is_unchanged_after_json_decoding() -> None:
    complete_graph = build_graph_fixture(
        node_count=1, edge_count=1, reply_count=1, reply_size=2_100_000
    )
    original_reply = complete_graph.nodes[0].data["reply"]  # type: ignore[index]
    wire = encode_graph_editor_response(complete_graph).model_dump(
        mode="json", exclude_none=True, exclude_defaults=True
    )

    decoded = json.loads(json.dumps(wire, ensure_ascii=False, separators=(",", ":")))

    assert decoded["nodes"][0]["data"]["reply"] == original_reply
    assert len(decoded["nodes"][0]["data"]["reply"].encode("utf-8")) == 2_100_000


def test_main_get_forwards_owner_lookup_and_uses_compact_response() -> None:
    complete_graph = build_small_graph_fixture()
    app = _test_app()
    lookup = AsyncMock(return_value=complete_graph)

    with patch.object(graph_router, "get_graph_by_id", new=lookup):
        response = TestClient(app).get(f"/graph/{GRAPH_ID}")

    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert "user_id" not in response.json()["graph"]
    assert response.json()["nodes"][0]["data"]["nested"]["false"] is False
    lookup.assert_awaited_once_with(app.state.pg_engine, str(GRAPH_ID), str(USER_ID))


def test_main_get_preserves_dependency_and_not_found_statuses() -> None:
    async def reject_auth() -> str:
        raise HTTPException(status_code=401, detail="Not authenticated")

    app = _test_app()
    app.dependency_overrides[get_current_user_id] = reject_auth
    lookup = AsyncMock()
    with patch.object(graph_router, "get_graph_by_id", new=lookup):
        response = TestClient(app).get(f"/graph/{GRAPH_ID}")
    assert response.status_code == 401
    lookup.assert_not_awaited()

    app.dependency_overrides[get_current_user_id] = _stub_auth
    with patch.object(
        graph_router,
        "get_graph_by_id",
        new=AsyncMock(side_effect=HTTPException(status_code=404, detail="Graph not found")),
    ):
        response = TestClient(app).get(f"/graph/{GRAPH_ID}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Graph not found"}


def test_backup_get_retains_full_unversioned_shape() -> None:
    complete_graph = build_small_graph_fixture()
    app = _test_app()

    with patch.object(graph_router, "get_graph_by_id", new=AsyncMock(return_value=complete_graph)):
        response = TestClient(app).get(f"/graph/{GRAPH_ID}/backup")

    body = response.json()
    assert response.status_code == 200
    assert "version" not in body
    assert body["graph"]["user_id"] == str(USER_ID)
    assert body["nodes"][0]["graph_id"] == str(GRAPH_ID)
    assert body["edges"][0]["graph_id"] == str(GRAPH_ID)
    assert body["edges"][0]["markerEnd"] == {"type": "arrowclosed"}


def test_update_still_accepts_full_graph_ids_and_marker_end() -> None:
    complete_graph = build_small_graph_fixture()
    payload = complete_graph.model_dump(mode="json")
    app = _test_app()
    settings = SimpleNamespace(generationHistory=SimpleNamespace(max_saved_entries=10))
    updated_graph = complete_graph.graph

    with (
        patch.object(graph_router, "validate_premium_nodes", new=AsyncMock()) as validate,
        patch.object(graph_router, "get_user_settings", new=AsyncMock(return_value=settings)),
        patch.object(
            graph_router,
            "update_graph_with_nodes_and_edges",
            new=AsyncMock(return_value=updated_graph),
        ) as update,
    ):
        response = TestClient(app).post(f"/graph/{GRAPH_ID}/update", json=payload)

    assert response.status_code == 200
    received = update.await_args.args
    assert str(received[5][0].graph_id) == str(GRAPH_ID)
    assert str(received[6][0].graph_id) == str(GRAPH_ID)
    assert received[6][0].markerEnd == {"type": "arrowclosed"}
    validate.assert_awaited_once()
