import asyncio
import copy
import json
import sys
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from const.settings import DEFAULT_SETTINGS
from models.node_preset_dto import (
    DEFAULT_PRESET_ACCENT_COLOR,
    MAX_NODE_PRESETS_UTF8_BYTES,
    MINIMUM_NODE_DIMENSIONS,
    NodePresetSettingsDTO,
)
from models.usersDTO import SettingsDTO
from services import settings as settings_service


def _id(number: int) -> str:
    return str(uuid.UUID(int=number))


def _data(node_type: str) -> dict:
    return {
        "prompt": {"prompt": "Hello", "templateId": None, "templateVariables": {"name": "Ada"}},
        "filePrompt": {
            "files": [
                {
                    "id": _id(100),
                    "name": "notes.txt",
                    "path": "uploads/notes.txt",
                    "type": "file",
                    "size": 42,
                    "content_type": "text/plain",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                    "cached": True,
                }
            ]
        },
        "textToText": {
            "model": "provider/model",
            "selectedTools": ["web_search", "ask_user"],
            "autoSelectTools": False,
            "imageModel": "provider/image",
            "videoModel": "provider/video",
            "visualiseModes": {
                "enableMermaid": True,
                "enableSvg": False,
                "enableHtml": True,
            },
        },
        "parallelization": {
            "models": [{"model": "provider/one"}, {"model": "provider/two"}],
            "aggregator": {"prompt": "Combine", "model": "provider/aggregate"},
            "defaultModel": "provider/default",
        },
        "routing": {
            "routeGroupId": "route-group",
            "selectedTools": ["execute_code"],
            "autoSelectTools": True,
            "visualiseModes": {"enableSvg": True},
        },
        "github": {
            "repo": {
                "provider": "github",
                "encoded_provider": "github",
                "full_name": "owner/repository",
                "description": None,
                "clone_url_ssh": "git@github.com:owner/repository.git",
                "clone_url_https": "https://github.com/owner/repository.git",
                "default_branch": "main",
                "stargazers_count": 12,
            },
            "files": [{"name": "README.md", "type": "file", "path": "README.md"}],
            "selectedIssues": [
                {
                    "id": 1,
                    "number": 2,
                    "title": "Issue",
                    "body": None,
                    "state": "open",
                    "html_url": "https://github.com/owner/repository/issues/2",
                    "is_pull_request": False,
                    "user_login": "octocat",
                    "user_avatar": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                }
            ],
            "branch": "feature/presets",
        },
        "contextMerger": {"mode": "last_n", "last_n": 5, "include_user_messages": True},
        "group": {"title": "Research", "comment": "Gather context", "colorIndex": 3},
    }[node_type]


def _node(number: int, node_type: str, *, parent_id: str | None = None) -> dict:
    minimum_width, minimum_height = MINIMUM_NODE_DIMENSIONS[node_type]
    node = {
        "id": _id(number),
        "type": node_type,
        "position": {"x": float(number * 10), "y": float(number * -5)},
        "width": minimum_width,
        "height": minimum_height,
        "data": copy.deepcopy(_data(node_type)),
    }
    if parent_id is not None:
        node["parentId"] = parent_id
    return node


def _preset(*, name: str = "Starter", preset_id: int = 1) -> dict:
    group = _node(10, "group")
    nodes = [
        group,
        _node(11, "prompt", parent_id=group["id"]),
        _node(12, "filePrompt"),
        _node(13, "textToText"),
        _node(14, "parallelization"),
        _node(15, "routing"),
        _node(16, "github"),
        _node(17, "contextMerger"),
    ]
    edges = [
        {"id": _id(201), "source": _id(11), "target": _id(13), "category": "prompt"},
        {"id": _id(202), "source": _id(13), "target": _id(17), "category": "context"},
        {"id": _id(203), "source": _id(14), "target": _id(17), "category": "context"},
        {"id": _id(204), "source": _id(12), "target": _id(13), "category": "attachment"},
        {"id": _id(205), "source": _id(16), "target": _id(15), "category": "attachment"},
    ]
    return {
        "id": _id(preset_id),
        "name": name,
        "accentColor": DEFAULT_PRESET_ACCENT_COLOR,
        "nodes": nodes,
        "edges": edges,
    }


def _collection(preset: dict | None = None) -> dict:
    return {"schemaVersion": 1, "presets": [_preset() if preset is None else preset]}


def _assert_invalid(payload: dict, message: str | None = None) -> None:
    with pytest.raises(ValidationError) as exc_info:
        NodePresetSettingsDTO.model_validate(payload)
    if message:
        assert message in str(exc_info.value)


def test_canonical_default_and_legacy_settings_hydration():
    assert DEFAULT_SETTINGS.nodePresets.model_dump(mode="json") == {
        "schemaVersion": 1,
        "presets": [],
    }

    legacy = DEFAULT_SETTINGS.model_dump(mode="json")
    legacy.pop("nodePresets")
    hydrated = SettingsDTO.model_validate(legacy)

    assert hydrated.nodePresets.model_dump(mode="json") == {"schemaVersion": 1, "presets": []}


def test_get_user_settings_hydrates_stored_legacy_payload(monkeypatch):
    legacy = DEFAULT_SETTINGS.model_dump(mode="json")
    legacy.pop("nodePresets")

    async def fake_get_settings(pg_engine, user_id):
        assert pg_engine is engine
        assert user_id == "legacy-user"
        return legacy

    engine = object()
    monkeypatch.setattr(settings_service, "get_settings", fake_get_settings)

    result = asyncio.run(settings_service.get_user_settings(engine, "legacy-user"))

    assert result.nodePresets.schemaVersion == 1
    assert result.nodePresets.presets == []


def test_valid_version_one_round_trip_covers_every_supported_node_data_shape():
    validated = NodePresetSettingsDTO.model_validate(_collection())
    dumped = validated.model_dump(mode="json")

    assert dumped == _collection()
    assert {node.type for node in validated.presets[0].nodes} == {
        "prompt",
        "filePrompt",
        "textToText",
        "parallelization",
        "routing",
        "github",
        "contextMerger",
        "group",
    }
    assert NodePresetSettingsDTO.model_validate(dumped).model_dump(mode="json") == dumped


def test_legacy_preset_accent_hydrates_default_and_uppercase_is_normalized():
    legacy = _preset()
    legacy.pop("accentColor")

    hydrated = NodePresetSettingsDTO.model_validate(_collection(legacy)).model_dump(mode="json")
    assert hydrated["presets"][0]["accentColor"] == DEFAULT_PRESET_ACCENT_COLOR

    uppercase = _preset()
    uppercase["accentColor"] = "#A1B2C3"
    normalized = NodePresetSettingsDTO.model_validate(_collection(uppercase))
    assert normalized.presets[0].accentColor == "#a1b2c3"


@pytest.mark.parametrize(
    "accent_color",
    [
        "red",
        "#fff",
        "#abcd",
        "#11223344",
        "112233",
        "rgb(17, 34, 51)",
        "var(--accent)",
        "#12\x00345",
        "#123456\n",
        "#123\t56",
        "#123\x1b56",
        "#gggggg",
        "#12345g",
        " #123456",
        "#123456 ",
        None,
        123456,
        True,
        ["#123456"],
        {"value": "#123456"},
    ],
)
def test_preset_accent_rejects_noncanonical_css_and_non_strings(accent_color):
    preset = _preset()
    preset["accentColor"] = accent_color

    _assert_invalid(_collection(preset))


@pytest.mark.parametrize("version", [0, 2, 999, "1", 1.0])
def test_unknown_or_non_integer_schema_version_is_rejected(version):
    _assert_invalid({"schemaVersion": version, "presets": []})


@pytest.mark.parametrize("payload", [{"presets": []}, {"schemaVersion": 1}])
def test_present_section_requires_complete_versioned_collection_shape(payload):
    _assert_invalid(payload)


@pytest.mark.parametrize(
    ("path", "extra_key"),
    [
        ([], "futureField"),
        (["presets", 0], "createdAt"),
        (["presets", 0, "nodes", 0], "graphId"),
        (["presets", 0, "nodes", 0, "position"], "z"),
        (["presets", 0, "nodes", 1, "data"], "reply"),
        (["presets", 0, "nodes", 1, "data", "templateVariables"], ""),
        (["presets", 0, "nodes", 2, "data"], "content"),
        (["presets", 0, "nodes", 2, "data", "files", 0], "bytes"),
        (["presets", 0, "nodes", 3, "data"], "usageData"),
        (["presets", 0, "nodes", 3, "data", "visualiseModes"], "html"),
        (["presets", 0, "nodes", 4, "data"], "activeGenerationHistoryId"),
        (["presets", 0, "nodes", 4, "data", "models", 0], "reply"),
        (["presets", 0, "nodes", 4, "data", "aggregator"], "usageData"),
        (["presets", 0, "nodes", 5, "data"], "selectedRouteId"),
        (["presets", 0, "nodes", 6, "data"], "oldId"),
        (["presets", 0, "nodes", 6, "data", "repo"], "private"),
        (["presets", 0, "nodes", 6, "data", "files", 0], "children"),
        (["presets", 0, "nodes", 6, "data", "selectedIssues", 0], "labels"),
        (["presets", 0, "nodes", 7, "data"], "branch_summaries"),
        (["presets", 0, "edges", 0], "sourceHandle"),
    ],
)
def test_extra_and_generated_runtime_fields_are_forbidden(path, extra_key):
    payload = _collection()
    target = payload
    for part in path:
        target = target[part]
    target[extra_key] = "forbidden"

    _assert_invalid(payload)


def test_empty_draft_is_valid_but_edges_without_nodes_are_not():
    draft = {"id": _id(1), "name": "Draft", "nodes": [], "edges": []}
    assert NodePresetSettingsDTO.model_validate(_collection(draft)).presets[0].nodes == []

    draft["edges"] = [{"id": _id(2), "source": _id(3), "target": _id(4), "category": "context"}]
    _assert_invalid(_collection(draft), "edge endpoints")


def test_preset_count_id_and_normalized_name_uniqueness_limits():
    payload = {"schemaVersion": 1, "presets": []}
    for number in range(1, 9):
        payload["presets"].append(
            {"id": _id(number), "name": f"Preset {number}", "nodes": [], "edges": []}
        )
    assert len(NodePresetSettingsDTO.model_validate(payload).presets) == 8

    payload["presets"].append({"id": _id(9), "name": "Preset 9", "nodes": [], "edges": []})
    _assert_invalid(payload)

    duplicate_id = {"schemaVersion": 1, "presets": [payload["presets"][0], payload["presets"][0]]}
    _assert_invalid(duplicate_id, "preset IDs must be unique")

    duplicate_name = {
        "schemaVersion": 1,
        "presets": [
            {"id": _id(1), "name": "  Café  ", "nodes": [], "edges": []},
            {"id": _id(2), "name": "CAFE\u0301", "nodes": [], "edges": []},
        ],
    }
    _assert_invalid(duplicate_name, "preset names must be unique")


@pytest.mark.parametrize("name", ["", "   ", "x" * 65, "unsafe\x00name"])
def test_preset_name_string_rules(name):
    draft = {"id": _id(1), "name": name, "nodes": [], "edges": []}
    _assert_invalid(_collection(draft))


def test_preset_name_is_trimmed_and_normal_whitespace_is_allowed():
    draft = {"id": _id(1), "name": f"  {'x' * 64}  ", "nodes": [], "edges": []}
    validated = NodePresetSettingsDTO.model_validate(_collection(draft))
    assert validated.presets[0].name == "x" * 64


@pytest.mark.parametrize("field", ["id", "node_id", "edge_id"])
def test_all_identity_fields_require_uuid_strings(field):
    payload = _collection()
    if field == "id":
        payload["presets"][0]["id"] = "not-a-uuid"
    elif field == "node_id":
        payload["presets"][0]["nodes"][0]["id"] = "not-a-uuid"
    else:
        payload["presets"][0]["edges"][0]["id"] = "not-a-uuid"
    _assert_invalid(payload, "must be a UUID string")


def test_node_and_edge_count_limits_and_duplicate_ids():
    nodes = [_node(number, "prompt") for number in range(1, 21)]
    preset = {"id": _id(100), "name": "Twenty", "nodes": nodes, "edges": []}
    assert len(NodePresetSettingsDTO.model_validate(_collection(preset)).presets[0].nodes) == 20
    preset["nodes"].append(_node(21, "prompt"))
    _assert_invalid(_collection(preset))

    duplicate_nodes = _preset()
    duplicate_nodes["nodes"].append(copy.deepcopy(duplicate_nodes["nodes"][1]))
    _assert_invalid(_collection(duplicate_nodes), "node IDs must be unique")

    prompt = _node(1, "prompt")
    target = _node(2, "textToText")
    edges = [
        {
            "id": _id(500 + number),
            "source": prompt["id"],
            "target": target["id"],
            "category": "prompt",
        }
        for number in range(40)
    ]
    # Duplicate topology fails before count, so use context edges with distinct source nodes for cap proof.
    sources = [_node(number, "contextMerger") for number in range(10, 51)]
    target = _node(60, "contextMerger")
    edges = [
        {
            "id": _id(500 + number),
            "source": source["id"],
            "target": target["id"],
            "category": "context",
        }
        for number, source in enumerate(sources)
    ]
    edge_preset = {
        "id": _id(101),
        "name": "Edges",
        "nodes": sources[:19] + [target],
        "edges": edges[:40],
    }
    # Node cap prevents constructing 40 unique sources; cycles permit 40 unique tuples among 20 nodes.
    edge_preset["edges"] = []
    edge_nodes = edge_preset["nodes"]
    for index in range(40):
        source = edge_nodes[index % 20]
        target_node = edge_nodes[(index // 20 + index + 1) % 20]
        edge_preset["edges"].append(
            {
                "id": _id(500 + index),
                "source": source["id"],
                "target": target_node["id"],
                "category": "context",
            }
        )
    assert (
        len(NodePresetSettingsDTO.model_validate(_collection(edge_preset)).presets[0].edges) == 40
    )
    edge_preset["edges"].append(
        {
            "id": _id(999),
            "source": edge_nodes[0]["id"],
            "target": edge_nodes[2]["id"],
            "category": "context",
        }
    )
    _assert_invalid(_collection(edge_preset))

    duplicate_edges = _preset()
    duplicate_edges["edges"].append(copy.deepcopy(duplicate_edges["edges"][0]))
    duplicate_edges["edges"][-1]["id"] = duplicate_edges["edges"][1]["id"]
    _assert_invalid(_collection(duplicate_edges), "edge IDs must be unique")


@pytest.mark.parametrize(
    ("node_type", "field", "invalid_value"),
    [
        ("prompt", "width", 499.99),
        ("prompt", "height", 199.99),
        ("filePrompt", "height", 274.99),
        ("github", "height", 249.99),
        ("textToText", "width", 599.99),
        ("parallelization", "width", 659.99),
        ("routing", "height", 299.99),
        ("contextMerger", "width", 284.99),
        ("group", "height", 39.99),
        ("prompt", "width", 4_000.01),
        ("prompt", "height", float("inf")),
    ],
)
def test_node_dimension_rules(node_type, field, invalid_value):
    node = _node(1, node_type)
    if node_type == "group":
        node["data"] = _data("group")
        preset = {"id": _id(50), "name": "Geometry", "nodes": [node], "edges": []}
    else:
        preset = {"id": _id(50), "name": "Geometry", "nodes": [node], "edges": []}
    node[field] = invalid_value
    _assert_invalid(_collection(preset))


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("value", [1_000_000.01, -1_000_000.01, float("inf"), float("nan")])
def test_position_must_be_finite_and_bounded(axis, value):
    preset = {"id": _id(50), "name": "Geometry", "nodes": [_node(1, "prompt")], "edges": []}
    preset["nodes"][0]["position"][axis] = value
    _assert_invalid(_collection(preset))


def test_parent_structure_rejects_dangling_nested_and_empty_groups():
    dangling = _preset()
    dangling["nodes"][1]["parentId"] = _id(999)
    _assert_invalid(_collection(dangling), "parentId must reference a group")

    nested = _preset()
    nested["nodes"][0]["parentId"] = _id(999)
    _assert_invalid(_collection(nested), "group nodes cannot have a parentId")

    empty_group = _preset()
    empty_group["nodes"][1].pop("parentId")
    _assert_invalid(_collection(empty_group), "every group must have at least one direct child")


@pytest.mark.parametrize(
    ("source_type", "target_type", "category"),
    [
        ("textToText", "routing", "prompt"),
        ("prompt", "filePrompt", "prompt"),
        ("prompt", "textToText", "context"),
        ("contextMerger", "prompt", "context"),
        ("textToText", "routing", "attachment"),
        ("filePrompt", "contextMerger", "attachment"),
    ],
)
def test_edge_category_type_allowlist(source_type, target_type, category):
    source = _node(1, source_type)
    target = _node(2, target_type)
    preset = {
        "id": _id(10),
        "name": "Invalid edge",
        "nodes": [source, target],
        "edges": [
            {"id": _id(3), "source": source["id"], "target": target["id"], "category": category}
        ],
    }
    _assert_invalid(_collection(preset), f"invalid {category} edge node types")


def test_edges_reject_self_dangling_group_duplicate_and_prompt_multiplicity():
    self_edge = {
        "id": _id(10),
        "name": "Self",
        "nodes": [_node(1, "contextMerger")],
        "edges": [{"id": _id(2), "source": _id(1), "target": _id(1), "category": "context"}],
    }
    _assert_invalid(_collection(self_edge), "cannot connect a node to itself")

    dangling = _preset()
    dangling["edges"][0]["target"] = _id(999)
    _assert_invalid(_collection(dangling), "edge endpoints")

    group_edge = _preset()
    group_edge["edges"][0]["source"] = group_edge["nodes"][0]["id"]
    _assert_invalid(_collection(group_edge), "group nodes")

    duplicate = _preset()
    duplicate_edge = copy.deepcopy(duplicate["edges"][1])
    duplicate_edge["id"] = _id(999)
    duplicate["edges"].append(duplicate_edge)
    _assert_invalid(_collection(duplicate), "duplicate source, target, and category")

    multiplicity = _preset()
    multiplicity["edges"].append(
        {"id": _id(999), "source": _id(11), "target": _id(13), "category": "prompt"}
    )
    multiplicity["edges"][-1]["source"] = _id(11)
    # Distinct tuple but same target requires another prompt source.
    second_prompt = _node(18, "prompt")
    multiplicity["nodes"].append(second_prompt)
    multiplicity["edges"][-1]["source"] = second_prompt["id"]
    _assert_invalid(_collection(multiplicity), "only one incoming prompt edge")


def test_multiple_context_and_attachment_inputs_and_cycles_are_allowed():
    source_one = _node(1, "textToText")
    source_two = _node(2, "contextMerger")
    target = _node(3, "routing")
    file_source = _node(4, "filePrompt")
    github_source = _node(5, "github")
    preset = {
        "id": _id(10),
        "name": "Multiple",
        "nodes": [source_one, source_two, target, file_source, github_source],
        "edges": [
            {"id": _id(20), "source": _id(1), "target": _id(3), "category": "context"},
            {"id": _id(21), "source": _id(2), "target": _id(3), "category": "context"},
            {"id": _id(22), "source": _id(3), "target": _id(1), "category": "context"},
            {"id": _id(23), "source": _id(4), "target": _id(3), "category": "attachment"},
            {"id": _id(24), "source": _id(5), "target": _id(3), "category": "attachment"},
        ],
    }
    assert len(NodePresetSettingsDTO.model_validate(_collection(preset)).presets[0].edges) == 5


@pytest.mark.parametrize(
    ("node_type", "mutation"),
    [
        ("prompt", lambda data: data.update(prompt="x" * 100_001)),
        ("prompt", lambda data: data.update(templateId="x" * 257)),
        (
            "prompt",
            lambda data: data.update(templateVariables={f"key-{i}": "x" for i in range(101)}),
        ),
        (
            "filePrompt",
            lambda data: data.update(files=[copy.deepcopy(data["files"][0]) for _ in range(51)]),
        ),
        ("textToText", lambda data: data.update(model="x" * 257)),
        ("textToText", lambda data: data.update(selectedTools=["web_search", "web_search"])),
        ("textToText", lambda data: data.update(selectedTools=["unknown_tool"])),
        ("parallelization", lambda data: data.update(models=[{"model": "m"} for _ in range(17)])),
        ("parallelization", lambda data: data["aggregator"].update(prompt="x" * 100_001)),
        ("routing", lambda data: data.update(routeGroupId="x" * 257)),
        (
            "github",
            lambda data: data.update(files=[{"name": "a", "type": "file", "path": "a"}] * 201),
        ),
        (
            "github",
            lambda data: data.update(
                selectedIssues=[copy.deepcopy(data["selectedIssues"][0])] * 51
            ),
        ),
        ("contextMerger", lambda data: data.update(last_n=1_001)),
        ("group", lambda data: data.update(title="x" * 129)),
        ("group", lambda data: data.update(comment="x" * 4_001)),
        ("group", lambda data: data.update(colorIndex=11)),
    ],
)
def test_node_data_count_and_string_limits(node_type, mutation):
    node = _node(1, node_type)
    mutation(node["data"])
    if node_type == "group":
        child = _node(2, "prompt", parent_id=node["id"])
        nodes = [node, child]
    else:
        nodes = [node]
    preset = {"id": _id(10), "name": "Limits", "nodes": nodes, "edges": []}
    _assert_invalid(_collection(preset))


def test_file_repository_issue_and_context_field_boundaries():
    file_node = _node(1, "filePrompt")
    file_node["data"]["files"][0]["size"] = 10**15 + 1
    preset = {"id": _id(10), "name": "File", "nodes": [file_node], "edges": []}
    _assert_invalid(_collection(preset))

    github = _node(1, "github")
    github["data"]["repo"]["clone_url_https"] = "x" * 4_097
    preset = {"id": _id(10), "name": "Repo", "nodes": [github], "edges": []}
    _assert_invalid(_collection(preset))

    github = _node(1, "github")
    github["data"]["selectedIssues"][0]["title"] = "x" * 513
    preset = {"id": _id(10), "name": "Issue", "nodes": [github], "edges": []}
    _assert_invalid(_collection(preset))

    merger = _node(1, "contextMerger")
    merger["data"]["mode"] = "unknown"
    preset = {"id": _id(10), "name": "Mode", "nodes": [merger], "edges": []}
    _assert_invalid(_collection(preset))


def test_group_title_rejects_controls_but_allows_plain_html_text():
    group = _node(1, "group")
    child = _node(2, "prompt", parent_id=group["id"])
    group["data"]["title"] = "<b>plain text</b>"
    preset = {"id": _id(10), "name": "Group", "nodes": [group, child], "edges": []}
    assert (
        NodePresetSettingsDTO.model_validate(_collection(preset)).presets[0].nodes[0].data.title
        == "<b>plain text</b>"
    )

    group["data"]["title"] = "unsafe\x00title"
    _assert_invalid(_collection(preset), "control characters")


def test_optional_fields_are_omitted_in_serialized_output():
    prompt = _node(1, "prompt")
    prompt["data"] = {"prompt": "Hello", "templateId": None, "templateVariables": {}}
    github = _node(2, "github")
    github["data"] = {"files": [], "selectedIssues": []}
    preset = {"id": _id(10), "name": "Minimal", "nodes": [prompt, github], "edges": []}

    dumped = NodePresetSettingsDTO.model_validate(_collection(preset)).model_dump(mode="json")

    assert dumped["presets"][0]["nodes"][0]["data"] == {
        "prompt": "Hello",
        "templateId": None,
        "templateVariables": {},
    }
    assert dumped["presets"][0]["nodes"][1]["data"] == {"files": [], "selectedIssues": []}
    assert "parentId" not in dumped["presets"][0]["nodes"][0]


def test_aggregate_limit_uses_compact_utf8_bytes_after_name_normalization():
    presets = []
    for preset_number in range(1, 9):
        nodes = []
        for node_number in range(1, 21):
            node = _node(preset_number * 100 + node_number, "prompt")
            node["data"] = {"prompt": "é" * 2_000, "templateVariables": {}}
            nodes.append(node)
        presets.append(
            {
                "id": _id(preset_number),
                "name": f"  Preset {preset_number}  ",
                "nodes": nodes,
                "edges": [],
            }
        )
    payload = {"schemaVersion": 1, "presets": presets}
    normalized = copy.deepcopy(payload)
    for preset in normalized["presets"]:
        preset["name"] = preset["name"].strip()
    compact_size = len(
        json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    assert compact_size > MAX_NODE_PRESETS_UTF8_BYTES

    _assert_invalid(payload, "UTF-8 bytes")


def test_settings_aggregate_round_trip_preserves_valid_node_presets():
    payload = DEFAULT_SETTINGS.model_dump(mode="json")
    payload["nodePresets"] = _collection()

    dumped = SettingsDTO.model_validate(payload).model_dump(mode="json")

    assert dumped["nodePresets"] == _collection()
