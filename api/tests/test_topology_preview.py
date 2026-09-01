import copy
import math
import sys
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

from database.pg.models import Edge, Node
from schemas.topology_preview import TopologyPreviewEdgeV1, TopologyPreviewNodeV1, TopologyPreviewV1
from services.graph_topology_preview import build_topology_preview

GRAPH_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


def _node(
    node_id: str,
    x: float = 0,
    y: float = 0,
    *,
    width: str = "100px",
    height: str = "100px",
    parent_id: str | None = None,
    data: object = None,
) -> Node:
    return Node(
        id=node_id,
        graph_id=GRAPH_ID,
        type="secret-node-type",
        position_x=x,
        position_y=y,
        width=width,
        height=height,
        parent_node_id=parent_id,
        data=data,
    )


def _edge(edge_id: str, source: str, target: str) -> Edge:
    return Edge(
        id=edge_id,
        graph_id=GRAPH_ID,
        source_node_id=source,
        target_node_id=target,
        label="secret-edge-label",
        data={"prompt": "must not leak"},
        style={"stroke": "private"},
    )


def _descriptor() -> dict[str, object]:
    return {
        "version": 1,
        "width": 1000,
        "height": 600,
        "nodes": [{"x": 0, "y": 0, "width": 1, "height": 1}],
        "edges": [{"x1": 0, "y1": 0, "x2": 1000, "y2": 600}],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(version=2),
        lambda value: value.update(width=999),
        lambda value: value.update(height=599),
        lambda value: value.update(extra="forbidden"),
        lambda value: value["nodes"][0].update(id="forbidden"),
        lambda value: value["edges"][0].update(label="forbidden"),
        lambda value: value.update(nodes=[value["nodes"][0]] * 65),
        lambda value: value.update(edges=[value["edges"][0]] * 129),
        lambda value: value["nodes"][0].update(x=-1),
        lambda value: value["nodes"][0].update(y=601),
        lambda value: value["nodes"][0].update(width=0),
        lambda value: value["nodes"][0].update(height=-1),
        lambda value: value["nodes"][0].update(x=999, width=2),
        lambda value: value["nodes"][0].update(y=599, height=2),
        lambda value: value["edges"][0].update(x1=-1),
        lambda value: value["edges"][0].update(y2=601),
        lambda value: value["nodes"][0].update(x="0"),
        lambda value: value["nodes"][0].update(width=1.5),
        lambda value: value["edges"][0].update(x1=True),
    ],
)
def test_v1_schema_rejects_invalid_or_extended_descriptors(mutation: object) -> None:
    value = copy.deepcopy(_descriptor())
    mutation(value)  # type: ignore[operator]

    with pytest.raises(ValidationError):
        TopologyPreviewV1.model_validate(value)


def test_v1_schema_accepts_only_exact_geometry_keys() -> None:
    descriptor = TopologyPreviewV1.model_validate(_descriptor()).model_dump(mode="json")

    assert set(descriptor) == {"version", "width", "height", "nodes", "edges"}
    assert set(descriptor["nodes"][0]) == {"x", "y", "width", "height"}
    assert set(descriptor["edges"][0]) == {"x1", "y1", "x2", "y2"}


def test_empty_and_single_node_previews_are_valid_and_centered() -> None:
    assert build_topology_preview([], []).model_dump(mode="json") == {
        "version": 1,
        "width": 1000,
        "height": 600,
        "nodes": [],
        "edges": [],
    }

    preview = build_topology_preview([_node("node", 123, -456)], [])

    assert preview.nodes == [TopologyPreviewNodeV1(x=428, y=228, width=144, height=144)]
    assert preview.edges == []


def test_generator_is_deterministic_and_excludes_content_and_invalid_edges() -> None:
    nodes = [
        _node("b", 600, 360, data={"name": "private", "reply": "secret"}),
        _node("a", 0, 0, data={"prompt": "secret"}),
        _node("invalid", math.nan, 0),
    ]
    edges = [
        _edge("valid", "a", "b"),
        _edge("dangling", "a", "missing"),
        _edge("self", "a", "a"),
    ]

    first = build_topology_preview(nodes, edges).model_dump(mode="json")
    second = build_topology_preview(list(reversed(nodes)), list(reversed(edges))).model_dump(
        mode="json"
    )

    assert first == second
    assert len(first["nodes"]) == 2
    assert len(first["edges"]) == 1
    serialized = repr(first)
    for forbidden in ("private", "secret", "prompt", "reply", "label", "secret-node-type"):
        assert forbidden not in serialized


def test_dimensions_use_exact_px_values_fallbacks_and_clamps() -> None:
    low = _node("a-low", 0, 0, width="-20px", height="0px")
    fallback = _node("b-fallback", 0, 200, width=" 40px", height="calc(100px)")
    numeric = _node("c-numeric", 0, 400)
    numeric.width = 120  # type: ignore[assignment]
    numeric.height = 80  # type: ignore[assignment]
    high = _node("d-high", 0, 600, width="999px", height="999px")

    preview = build_topology_preview([low, fallback, numeric, high], [])

    assert preview.nodes[0].width < preview.nodes[1].width < preview.nodes[2].width
    assert preview.nodes[0].height < preview.nodes[2].height < preview.nodes[1].height
    assert preview.nodes[3].width > preview.nodes[2].width
    assert preview.nodes[3].height > preview.nodes[1].height


def test_uniform_fit_preserves_square_geometry_and_viewport_containment() -> None:
    preview = build_topology_preview(
        [_node("a", -1_000_000_000, -1_000_000_000), _node("b", 1_000_000_000, 1_000_000_000)],
        [_edge("edge", "a", "b")],
    )

    assert all(node.width == node.height for node in preview.nodes)
    assert all(node.x + node.width <= 1000 for node in preview.nodes)
    assert all(node.y + node.height <= 600 for node in preview.nodes)
    assert preview.edges == [
        TopologyPreviewEdgeV1(
            x1=240,
            y1=40,
            x2=760,
            y2=560,
        )
    ]


def _selected_fixture(child: Node, ancestors: list[Node]) -> list[Node]:
    selected_fillers = [_node(f"b-{index:03d}", index * 10, index * 3) for index in range(63)]
    return [child, *selected_fillers, *ancestors]


def _child_geometry(child: Node, ancestors: list[Node]) -> TopologyPreviewNodeV1:
    return build_topology_preview(_selected_fixture(child, ancestors), []).nodes[0]


def test_missing_ancestor_stops_before_add_and_retains_previous_offsets() -> None:
    parent = _node("z-parent", 30, 20, parent_id="missing")
    actual = _child_geometry(_node("a-child", 10, 5, parent_id=parent.id), [parent])
    expected = _child_geometry(_node("a-child", 40, 25), [parent])

    assert actual == expected


def test_repeated_ancestor_stops_before_add_and_retains_previous_offsets() -> None:
    parent = _node("z-parent", 30, 20, parent_id="a-child")
    actual = _child_geometry(_node("a-child", 10, 5, parent_id=parent.id), [parent])
    expected = _child_geometry(_node("a-child", 40, 25), [parent])

    assert actual == expected


def test_non_finite_ancestor_stops_before_add_and_retains_previous_offsets() -> None:
    parent = _node("z-parent", 30, 20, parent_id="z-invalid")
    invalid = _node("z-invalid", math.inf, 100)
    actual = _child_geometry(
        _node("a-child", 10, 5, parent_id=parent.id),
        [parent, invalid],
    )
    expected = _child_geometry(_node("a-child", 40, 25), [parent, invalid])

    assert actual == expected


def test_ancestry_depth_is_capped_at_32_accepted_offsets() -> None:
    ancestors = [
        _node(
            f"z-{index:02d}",
            1,
            2,
            parent_id=f"z-{index + 1:02d}" if index < 32 else None,
        )
        for index in range(33)
    ]
    actual = _child_geometry(_node("a-child", 0, 0, parent_id="z-00"), ancestors)
    expected = _child_geometry(_node("a-child", 32, 64), ancestors)

    assert actual == expected


def test_large_input_caps_output_and_is_order_independent() -> None:
    nodes = [_node(f"node-{index:05d}", index * 17, index * -9) for index in range(5_000)]
    edges = [
        _edge(
            f"edge-{index:05d}",
            f"node-{index % 64:05d}",
            f"node-{(index + 1) % 64:05d}",
        )
        for index in range(10_000)
    ]

    first = build_topology_preview(nodes, edges).model_dump(mode="json")
    second = build_topology_preview(list(reversed(nodes)), list(reversed(edges))).model_dump(
        mode="json"
    )

    assert first == second
    assert len(first["nodes"]) == 64
    assert len(first["edges"]) == 128
