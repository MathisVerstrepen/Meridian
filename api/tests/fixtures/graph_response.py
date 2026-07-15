import datetime
import uuid

from database.pg.graph_ops.graph_crud import CompleteGraph
from database.pg.models import Edge, Graph, Node

GRAPH_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
FOLDER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
WORKSPACE_ID = uuid.UUID("87654321-4321-8765-4321-876543218765")


def deterministic_reply(size: int, seed: int = 0) -> str:
    prefix = "The graph response preserves Unicode café 🚀 and code exactly.\n"
    remaining_bytes = size - len(prefix.encode("utf-8"))
    if remaining_bytes < 0:
        raise ValueError("reply size is too small for the deterministic prefix")

    parts = [prefix]
    counter = seed * 10_007
    while remaining_bytes:
        checksum = (counter * 2_654_435_761) & 0xFFFFFFFF
        line = (
            f"Segment {counter:09d}: analyze request_{counter % 997:03d}; "
            f"value=0x{checksum:08x}; result={(checksum ^ seed) % 100_003:05d}.\n"
        )
        chunk = line[:remaining_bytes]
        parts.append(chunk)
        remaining_bytes -= len(chunk)
        counter += 1
    return "".join(parts)


def build_graph_fixture(
    *, node_count: int, edge_count: int, reply_count: int, reply_size: int
) -> CompleteGraph:
    graph = Graph(
        id=GRAPH_ID,
        user_id=USER_ID,
        folder_id=FOLDER_ID,
        workspace_id=WORKSPACE_ID,
        name="Deterministic graph",
        description=None,
        temporary=False,
        pinned=False,
        created_at=datetime.datetime(2026, 7, 15, 12, 30, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 7, 15, 12, 45, tzinfo=datetime.timezone.utc),
        custom_instructions=[],
        max_tokens=None,
        temperature=0.25,
        top_p=None,
        top_k=40,
        frequency_penalty=None,
        presence_penalty=0.0,
        repetition_penalty=None,
        reasoning_effort="high",
    )
    graph.node_count = node_count

    nodes = []
    for index in range(node_count):
        data: dict[str, object] = {
            "title": f"Node {index}",
            "nested": {
                "null": None,
                "false": False,
                "zero": 0,
                "empty_string": "",
                "empty_object": {},
                "empty_array": [],
            },
        }
        if index < reply_count:
            data["reply"] = deterministic_reply(reply_size, seed=index)
        nodes.append(
            Node(
                id=f"node-{index}",
                graph_id=GRAPH_ID,
                type="chat" if index % 3 else "prompt",
                position_x=float(index * 17),
                position_y=float(index * -9),
                width="320px" if index % 11 == 0 else "100px",
                height="180px" if index % 13 == 0 else "100px",
                parent_node_id=f"node-{index - 1}" if index and index % 7 == 0 else None,
                data=data,
            )
        )

    edges = []
    for index in range(edge_count):
        source_index = index % node_count
        target_index = (source_index + 1) % node_count
        edges.append(
            Edge(
                id=f"edge-{index}",
                graph_id=GRAPH_ID,
                source_node_id=f"node-{source_index}",
                target_node_id=f"node-{target_index}",
                source_handle_id=f"source-{index}" if index % 5 == 0 else None,
                target_handle_id=f"target-{index}" if index % 7 == 0 else None,
                type="smoothstep" if index % 4 == 0 else None,
                label=f"Edge {index}" if index % 9 == 0 else None,
                animated=index % 6 == 0,
                style={"strokeWidth": 0, "visible": False} if index % 8 == 0 else None,
                data={"empty": "", "items": []} if index % 10 == 0 else None,
                markerEnd={"type": "arrowclosed"},
            )
        )

    return CompleteGraph(graph=graph, nodes=nodes, edges=edges)


def build_small_graph_fixture() -> CompleteGraph:
    return build_graph_fixture(node_count=30, edge_count=38, reply_count=4, reply_size=4096)


def build_large_graph_fixture() -> CompleteGraph:
    return build_graph_fixture(node_count=500, edge_count=650, reply_count=220, reply_size=20_000)
