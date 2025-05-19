from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from neo4j import AsyncDriver
from pydantic import BaseModel
from enum import Enum
from typing import Any

from database.neo4j.crud import get_all_ancestor_nodes, get_parent_node_of_type
from database.pg.crud import get_nodes_by_ids

from rich import print as pprint


# TODO: Move models to a separate file
class MessageRoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Message(BaseModel):
    role: MessageRoleEnum
    content: str
    model: str | None = None
    node_id: str | None = None
    data: Any = None


async def construct_message_history(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    system_prompt: str,
    add_current_node: bool = False,
) -> list[Message]:
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
        add_current_node (bool):
            If True, the current node's message will be included in the conversation.
            Defaults to False.

    Returns:
        list[Message]:
            A list of Message objects representing the conversation history.
            Each message contains a role (user or assistant) and the corresponding content.
    """
    ancestor_node_ids = await get_all_ancestor_nodes(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
    )

    # We need to reverse the order of ancestor_node_ids because get_all_ancestor_nodes
    # returns them in the order from the target node to the root ancestor.
    ancestor_node_ids.reverse()
    if add_current_node:
        ancestor_node_ids.append(node_id)

    parents = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=ancestor_node_ids,
    )

    messages = (
        [Message(role=MessageRoleEnum.system, content=system_prompt)]
        if system_prompt
        else []
    )
    for parent in parents:
        if parent.type == "prompt":
            messages.append(
                Message(
                    role=MessageRoleEnum.user,
                    content=parent.data.get("prompt"),
                    node_id=parent.id,
                )
            )
        elif parent.type == "textToText":
            messages.append(
                Message(
                    role=MessageRoleEnum.assistant,
                    content=parent.data.get("reply"),
                    model=parent.data.get("model"),
                    node_id=parent.id,
                )
            )
        elif parent.type == "parallelization":
            messages.append(
                Message(
                    role=MessageRoleEnum.assistant,
                    content=parent.data.get("aggregator").get("reply"),
                    model=parent.data.get("aggregator").get("model"),
                    node_id=parent.id,
                    data=parent.data.get("models"),
                )
            )

    pprint(messages)
    return messages


async def construct_parallelization_aggregator_prompt(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    system_prompt: str,
) -> list[Message]:
    """
    Assembles a list of messages for an aggregator prompt by collecting model replies and formatting them for parallelization.

    This function retrieves the parent prompt node, gathers the current node's data, and constructs an aggregator prompt by appending each model's reply. It then creates a list of `Message` objects, including a system message with the constructed prompt and a user message with the parent prompt content.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL database access.
        neo4j_driver (AsyncDriver): The asynchronous Neo4j driver for graph database access.
        graph_id (str): The identifier of the graph.
        node_id (str): The identifier of the current node.
        system_prompt (str): The system prompt to prepend to the aggregator prompt.

    Returns:
        list[Message]: A list of `Message` objects representing the constructed prompt and the parent prompt.

    Raises:
        ValueError: If the parent prompt node cannot be found.
    """
    parent_prompt_id = await get_parent_node_of_type(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        node_type="prompt",
    )

    parent_prompt_node = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=[parent_prompt_id],
    )

    if not parent_prompt_node:
        raise ValueError(f"Parent prompt node with ID {parent_prompt_id} not found.")

    nodes = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=[node_id],
    )

    node = nodes[0]
    models = node.data.get("models")

    aggregator_prompt = node.data.get("aggregator").get("prompt")
    for idx, model in enumerate(models):
        reply = model.get("reply")

        aggregator_prompt += f"""\n
            === Answer {idx + 1} ===
            {reply}
            \n
        """

    messages = [
        Message(
            role=MessageRoleEnum.system,
            content=f"{system_prompt}\n{aggregator_prompt}",
        )
    ]

    messages.append(
        Message(
            role=MessageRoleEnum.user,
            content=parent_prompt_node[0].data.get("prompt"),
            node_id=node.id,
        )
    )

    pprint(messages)
    return messages
