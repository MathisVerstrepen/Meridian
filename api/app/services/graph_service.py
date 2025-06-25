from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from dataclasses import dataclass
from neo4j import AsyncDriver

from database.neo4j.crud import get_all_ancestor_nodes, get_parent_node_of_type
from database.pg.crud import (
    get_nodes_by_ids,
    get_canvas_config,
    get_settings,
    GraphConfigUpdate,
)
from models.usersDTO import SettingsDTO
from models.message import (
    Message,
    MessageTypeEnum,
)
from services.node import system_message_builder, node_to_message, CleanTextOption
from services.crypto import retrieve_and_decrypt_api_key


async def construct_message_history(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    system_prompt: str,
    add_current_node: bool = False,
    add_file_content: bool = True,
    clean_text: CleanTextOption = CleanTextOption.REMOVE_NOTHING,
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
        add_file_content (bool):
            If True, file content associated with the messages will be included.
            If False, the file id will be included instead of the file content.
            This is useful for the frontend to speed up the fetching of messages
            Defaults to True.
        clean_text (bool):
            If True, the thinking text will be cleaned before being added to the message.

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

    system_message = system_message_builder(system_prompt)
    messages = [system_message] if system_message else []

    for idx, parent in enumerate(parents):
        message = await node_to_message(
            node=parent,
            previousNode=parents[idx - 1] if idx != 0 else None,
            add_file_content=add_file_content,
            clean_text=clean_text,
            pg_engine=pg_engine,
        )
        if message:
            messages.append(message)

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
        node_type=MessageTypeEnum.PROMPT,
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

    messages = [system_message_builder(f"{system_prompt}\n{aggregator_prompt}")]

    message = await node_to_message(
        node=parent_prompt_node[0],
        previousNode=None,
        pg_engine=pg_engine,
    )
    messages.append(message)

    return messages


@dataclass
class FieldMapping:
    """Maps a field from canvas/user settings to the final graph config."""

    target: str
    canvas_source: str
    user_source_path: str


mappings = [
    FieldMapping(
        "custom_instructions", "custom_instructions", "models.globalSystemPrompt"
    ),
    FieldMapping("max_tokens", "max_tokens", "models.maxTokens"),
    FieldMapping("temperature", "temperature", "models.temperature"),
    FieldMapping("top_p", "top_p", "models.topP"),
    FieldMapping("top_k", "top_k", "models.topK"),
    FieldMapping("frequency_penalty", "frequency_penalty", "models.frequencyPenalty"),
    FieldMapping("presence_penalty", "presence_penalty", "models.presencePenalty"),
    FieldMapping(
        "repetition_penalty", "repetition_penalty", "models.repetitionPenalty"
    ),
    FieldMapping("reasoning_effort", "reasoning_effort", "models.reasoningEffort"),
    FieldMapping("exclude_reasoning", "exclude_reasoning", "models.excludeReasoning"),
    FieldMapping(
        "include_thinking_in_context",
        "includeThinkingInContext",
        "general.includeThinkingInContext",
    ),
]


def get_nested_attr(obj, attr_path):
    attrs = attr_path.split(".")
    for attr in attrs:
        obj = getattr(obj, attr, None)
        if obj is None:
            return None
    return obj


async def get_effective_graph_config(
    pg_engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
) -> tuple[GraphConfigUpdate, str]:
    """
    Retrieves the effective configuration for a specific graph, combining user and canvas settings.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy engine for PostgreSQL.
        graph_id (str): The ID of the graph.
        user_id (str): The ID of the user.

    Returns:
        tuple[GraphConfigUpdate, str]: A tuple containing the effective graph configuration and the OpenRouter API key.
    """

    user_settings = await get_settings(pg_engine=pg_engine, user_id=user_id)
    user_config = SettingsDTO.model_validate_json(user_settings.settings_data)

    open_router_api_key = retrieve_and_decrypt_api_key(
        db_payload=user_config.account.openRouterApiKey,
    )

    canvas_config = await get_canvas_config(
        pg_engine=pg_engine,
        graph_id=graph_id,
    )

    effective_config_data = {
        m.target: (
            canvas_value
            if (canvas_value := getattr(canvas_config, m.canvas_source, None))
            is not None
            else get_nested_attr(user_config, m.user_source_path)
        )
        for m in mappings
    }

    return GraphConfigUpdate(**effective_config_data), open_router_api_key
