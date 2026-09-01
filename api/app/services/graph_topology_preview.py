import heapq
import math
import re
from dataclasses import dataclass
from typing import Iterable

from database.pg.models import Edge, Node
from schemas.topology_preview import (
    TOPOLOGY_PREVIEW_HEIGHT,
    TOPOLOGY_PREVIEW_MAX_EDGES,
    TOPOLOGY_PREVIEW_MAX_NODES,
    TOPOLOGY_PREVIEW_WIDTH,
    TopologyPreviewEdgeV1,
    TopologyPreviewNodeV1,
    TopologyPreviewV1,
)

_MAX_ANCESTORS = 32
_MAX_SOURCE_COORDINATE = 1_000_000.0
_MIN_SOURCE_NODE_DIMENSION = 24.0
_MAX_SOURCE_NODE_DIMENSION = 480.0
_DEFAULT_SOURCE_NODE_DIMENSION = 100.0
_MIN_WORLD_WIDTH = 600.0
_MIN_WORLD_HEIGHT = 360.0
_VIEWPORT_PADDING = 40.0
_PIXEL_DIMENSION_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)px")


@dataclass
class _SelectedNode:
    node: Node
    node_id: str
    x: float
    y: float
    width: float
    height: float
    parent_id: str | None
    visited_ids: set[str]


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric_value = float(value)
    return numeric_value if math.isfinite(numeric_value) else None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _source_coordinate(value: object) -> float | None:
    numeric_value = _finite_number(value)
    if numeric_value is None:
        return None
    return _clamp(numeric_value, -_MAX_SOURCE_COORDINATE, _MAX_SOURCE_COORDINATE)


def _source_dimension(value: object) -> float:
    numeric_value = _finite_number(value)
    if (
        numeric_value is None
        and isinstance(value, str)
        and _PIXEL_DIMENSION_PATTERN.fullmatch(value)
    ):
        numeric_value = _finite_number(float(value[:-2]))
    if numeric_value is None:
        numeric_value = _DEFAULT_SOURCE_NODE_DIMENSION
    return _clamp(
        numeric_value,
        _MIN_SOURCE_NODE_DIMENSION,
        _MAX_SOURCE_NODE_DIMENSION,
    )


def _eligible_nodes(nodes: Iterable[Node]) -> Iterable[Node]:
    for node in nodes:
        if (
            _finite_number(node.position_x) is not None
            and _finite_number(node.position_y) is not None
        ):
            yield node


def _select_nodes(nodes: list[Node]) -> list[_SelectedNode]:
    selected = heapq.nsmallest(
        TOPOLOGY_PREVIEW_MAX_NODES,
        _eligible_nodes(nodes),
        key=lambda node: str(node.id),
    )
    return [
        _SelectedNode(
            node=node,
            node_id=str(node.id),
            x=_source_coordinate(node.position_x) or 0.0,
            y=_source_coordinate(node.position_y) or 0.0,
            width=_source_dimension(node.width),
            height=_source_dimension(node.height),
            parent_id=str(node.parent_node_id) if node.parent_node_id is not None else None,
            visited_ids={str(node.id)},
        )
        for node in selected
    ]


def _resolve_absolute_positions(selected_nodes: list[_SelectedNode], nodes: list[Node]) -> None:
    for _ in range(_MAX_ANCESTORS):
        requested_parent_ids = {
            state.parent_id
            for state in selected_nodes
            if state.parent_id is not None and state.parent_id not in state.visited_ids
        }
        if not requested_parent_ids:
            return

        resolved_parents: dict[str, Node] = {}
        for node in nodes:
            node_id = str(node.id)
            if node_id in requested_parent_ids and node_id not in resolved_parents:
                resolved_parents[node_id] = node
                if len(resolved_parents) == len(requested_parent_ids):
                    break

        for state in selected_nodes:
            parent_id = state.parent_id
            if parent_id is None:
                continue
            if parent_id in state.visited_ids:
                state.parent_id = None
                continue

            parent = resolved_parents.get(parent_id)
            if parent is None:
                state.parent_id = None
                continue

            parent_x = _source_coordinate(parent.position_x)
            parent_y = _source_coordinate(parent.position_y)
            if parent_x is None or parent_y is None:
                state.parent_id = None
                continue

            state.x = _clamp(
                state.x + parent_x,
                -_MAX_SOURCE_COORDINATE,
                _MAX_SOURCE_COORDINATE,
            )
            state.y = _clamp(
                state.y + parent_y,
                -_MAX_SOURCE_COORDINATE,
                _MAX_SOURCE_COORDINATE,
            )
            state.visited_ids.add(parent_id)
            state.parent_id = (
                str(parent.parent_node_id) if parent.parent_node_id is not None else None
            )


def _fit_nodes(selected_nodes: list[_SelectedNode]) -> list[TopologyPreviewNodeV1]:
    min_x = min(state.x for state in selected_nodes)
    min_y = min(state.y for state in selected_nodes)
    max_x = max(state.x + state.width for state in selected_nodes)
    max_y = max(state.y + state.height for state in selected_nodes)

    world_width = max(max_x - min_x, _MIN_WORLD_WIDTH)
    world_height = max(max_y - min_y, _MIN_WORLD_HEIGHT)
    world_center_x = (min_x + max_x) / 2
    world_center_y = (min_y + max_y) / 2
    world_min_x = world_center_x - world_width / 2
    world_min_y = world_center_y - world_height / 2

    scale = min(
        (TOPOLOGY_PREVIEW_WIDTH - 2 * _VIEWPORT_PADDING) / world_width,
        (TOPOLOGY_PREVIEW_HEIGHT - 2 * _VIEWPORT_PADDING) / world_height,
    )
    offset_x = (TOPOLOGY_PREVIEW_WIDTH - world_width * scale) / 2
    offset_y = (TOPOLOGY_PREVIEW_HEIGHT - world_height * scale) / 2

    fitted_nodes = []
    for state in selected_nodes:
        x = max(
            0,
            min(
                TOPOLOGY_PREVIEW_WIDTH - 1,
                round(offset_x + (state.x - world_min_x) * scale),
            ),
        )
        y = max(
            0,
            min(
                TOPOLOGY_PREVIEW_HEIGHT - 1,
                round(offset_y + (state.y - world_min_y) * scale),
            ),
        )
        width = max(1, min(TOPOLOGY_PREVIEW_WIDTH - x, round(state.width * scale)))
        height = max(1, min(TOPOLOGY_PREVIEW_HEIGHT - y, round(state.height * scale)))
        fitted_nodes.append(TopologyPreviewNodeV1(x=x, y=y, width=width, height=height))
    return fitted_nodes


def _eligible_edges(edges: Iterable[Edge], selected_node_ids: set[str]) -> Iterable[Edge]:
    for edge in edges:
        source_id = str(edge.source_node_id)
        target_id = str(edge.target_node_id)
        if (
            source_id != target_id
            and source_id in selected_node_ids
            and target_id in selected_node_ids
        ):
            yield edge


def _build_edges(
    edges: list[Edge],
    selected_nodes: list[_SelectedNode],
    fitted_nodes: list[TopologyPreviewNodeV1],
) -> list[TopologyPreviewEdgeV1]:
    fitted_by_id = {
        state.node_id: fitted_node
        for state, fitted_node in zip(selected_nodes, fitted_nodes, strict=True)
    }
    selected_edges = heapq.nsmallest(
        TOPOLOGY_PREVIEW_MAX_EDGES,
        _eligible_edges(edges, set(fitted_by_id)),
        key=lambda edge: (
            str(edge.source_node_id),
            str(edge.target_node_id),
            str(edge.id),
        ),
    )

    preview_edges = []
    for edge in selected_edges:
        source = fitted_by_id[str(edge.source_node_id)]
        target = fitted_by_id[str(edge.target_node_id)]
        preview_edges.append(
            TopologyPreviewEdgeV1(
                x1=round(source.x + source.width / 2),
                y1=round(source.y + source.height / 2),
                x2=round(target.x + target.width / 2),
                y2=round(target.y + target.height / 2),
            )
        )
    return preview_edges


def build_topology_preview(nodes: list[Node], edges: list[Edge]) -> TopologyPreviewV1:
    selected_nodes = _select_nodes(nodes)
    if not selected_nodes:
        return TopologyPreviewV1()

    _resolve_absolute_positions(selected_nodes, nodes)
    fitted_nodes = _fit_nodes(selected_nodes)
    preview_edges = _build_edges(edges, selected_nodes, fitted_nodes)
    return TopologyPreviewV1(nodes=fitted_nodes, edges=preview_edges)
