from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from neo4j import AsyncDriver

from database.neo4j.crud import get_all_ancestor_nodes
from database.pg.crud import get_nodes_by_ids

from rich import print_json


async def construct_prompt(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
) -> str:
    """
    Constructs a series of messages representing a conversation based on a node and its ancestors in a graph.

    This function retrieves all ancestor nodes of a specified node in a graph, then formats them into
    a conversation structure with alternating user and assistant messages. The conversation follows
    the path from the earliest ancestor down to the specified node.

    Parameters:
        pg_engine (SQLAlchemyAsyncEngine):
            The PostgreSQL database engine for retrieving node data.
        neo4j_driver (AsyncDriver):
            The Neo4j driver for graph traversal operations.
        graph_id (str):
            The unique identifier of the graph containing the nodes.
        node_id (str):
            The unique identifier of the node for which to construct the conversation.

    Returns:
        list[dict]: A list of message dictionaries
    """
    ancestor_node_ids = await get_all_ancestor_nodes(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
    )

    # We need to reverse the order of ancestor_node_ids because get_all_ancestor_nodes
    # returns them in the order from the target node to the root ancestor.
    ancestor_node_ids.reverse()

    parents = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=ancestor_node_ids,
    )

    messages = []
    for parent in parents:
        if parent.type == "prompt":
            messages.append(
                {
                    "role": "user",
                    "content": parent.data.get("prompt"),
                }
            )
        elif parent.type == "textToText":
            messages.append(
                {
                    "role": "assistant",
                    "content": parent.data.get("reply"),
                }
            )

    print_json(data=messages)
    return messages
