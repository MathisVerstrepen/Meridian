from database.pg.graph_ops.graph_crud import CompleteGraph
from schemas.graph_response import (
    GraphEditorEdgeV1,
    GraphEditorGraphV1,
    GraphEditorNodeV1,
    GraphEditorResponseV1,
)


def encode_graph_editor_response(complete_graph: CompleteGraph) -> GraphEditorResponseV1:
    """Convert an internal complete graph into the version-1 editor wire shape."""

    graph = complete_graph.graph
    if graph.id is None or graph.node_count is None:
        raise ValueError("Persisted graph response requires id and node_count")
    graph_response = GraphEditorGraphV1(
        id=graph.id,
        name=graph.name,
        node_count=graph.node_count,
        folder_id=graph.folder_id,
        workspace_id=graph.workspace_id,
        description=graph.description,
        temporary=graph.temporary,
        pinned=graph.pinned,
        created_at=graph.created_at,
        updated_at=graph.updated_at,
        custom_instructions=graph.custom_instructions or [],
        max_tokens=graph.max_tokens,
        temperature=graph.temperature,
        top_p=graph.top_p,
        top_k=graph.top_k,
        frequency_penalty=graph.frequency_penalty,
        presence_penalty=graph.presence_penalty,
        repetition_penalty=graph.repetition_penalty,
        reasoning_effort=graph.reasoning_effort,
    )
    nodes = [
        GraphEditorNodeV1.model_construct(
            id=node.id,
            type=node.type,
            position_x=node.position_x,
            position_y=node.position_y,
            width=node.width,
            height=node.height,
            parent_node_id=node.parent_node_id,
            data=node.data,
        )
        for node in complete_graph.nodes
    ]
    edges = [
        GraphEditorEdgeV1.model_construct(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            source_handle_id=edge.source_handle_id,
            target_handle_id=edge.target_handle_id,
            type=edge.type,
            label=edge.label,
            animated=edge.animated,
            style=edge.style,
            data=edge.data,
        )
        for edge in complete_graph.edges
    ]
    return GraphEditorResponseV1(version=1, graph=graph_response, nodes=nodes, edges=edges)
