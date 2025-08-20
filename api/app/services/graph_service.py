from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from dataclasses import dataclass
from typing import Literal
from neo4j import AsyncDriver
from pydantic import BaseModel

from database.neo4j.crud import (
    get_all_ancestor_nodes,
    get_parent_node_of_type,
    get_children_node_of_type,
    get_execution_plan,
)
from database.pg.settings_ops.settings_crud  import get_settings
from database.pg.graph_ops.graph_config_crud import (
    get_canvas_config,
    GraphConfigUpdate,
)
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from models.usersDTO import SettingsDTO
from models.message import (
    Message,
    NodeTypeEnum,
    MessageContentTypeEnum,
    MessageRoleEnum,
)
from models.graphDTO import NodeSearchRequest, NodeSearchDirection
from services.node import system_message_builder, node_to_message, CleanTextOption
from services.crypto import decrypt_api_key
from const.prompts import ROUTING_PROMPT, MERMAID_DIAGRAM_PROMPT


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
    the path from the earliest ancestor down to the specified node. Consecutive prompt nodes are
    merged into a single user message.

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
        if not message:
            continue

        if (
            messages
            and messages[-1].role == MessageRoleEnum.user
            and message.role == MessageRoleEnum.user
        ):
            last_message = messages[-1]

            new_text_content = next(
                (c for c in message.content if c.type == MessageContentTypeEnum.text),
                None,
            )
            last_text_content = next(
                (
                    c
                    for c in last_message.content
                    if c.type == MessageContentTypeEnum.text
                ),
                None,
            )

            if new_text_content and new_text_content.text:
                if last_text_content:
                    existing_text = last_text_content.text or ""
                    new_text = new_text_content.text or ""
                    separator = "\n\n" if existing_text and new_text else ""
                    last_text_content.text = f"{existing_text}{separator}{new_text}"
                else:
                    last_message.content.insert(0, new_text_content)

            other_content = [
                c for c in message.content if c.type != MessageContentTypeEnum.text
            ]
            last_message.content.extend(other_content)

            last_message.node_id = message.node_id
            last_message.type = message.type
        else:
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
        node_type=NodeTypeEnum.PROMPT,
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


async def construct_routing_prompt(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    user_id: str,
) -> tuple[list[Message], BaseModel]:
    """
    Constructs a routing prompt for a specific node in a graph.

    This function retrieves the parent prompt node, gathers the current node's data, and constructs a routing prompt by appending the current node's data. It then creates a list of `Message` objects, including a system message with the constructed prompt and a user message with the parent prompt content.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL database access.
        neo4j_driver (AsyncDriver): The asynchronous Neo4j driver for graph database access.
        graph_id (str): The identifier of the graph.
        node_id (str): The identifier of the current node.
        system_prompt (str): The system prompt to prepend to the routing prompt.

    Returns:
        list[Message]: A list of `Message` objects representing the constructed prompt and the parent prompt.

    Raises:
        ValueError: If the parent prompt node cannot be found.
    """
    parent_prompt_id = await get_parent_node_of_type(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        node_type=NodeTypeEnum.PROMPT,
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

    user_settings = await get_settings(pg_engine=pg_engine, user_id=user_id)
    user_config = SettingsDTO.model_validate_json(user_settings.settings_data)

    node = nodes[0]
    routes = {
        route.id: route.description
        for route in next(
            (
                routeGroup
                for routeGroup in user_config.blockRouting.routeGroups
                if routeGroup.id == node.data.get("routeGroupId", "")
            )
        ).routes
    }
    routing_prompt = ROUTING_PROMPT.format(
        user_query=parent_prompt_node[0].data.get("prompt", ""),
        routes=routes,
    )

    class Schema(BaseModel):
        route: Literal[tuple(routes.keys())]

    messages = [system_message_builder(routing_prompt)]

    return messages, Schema


class ExecutionPlanNode(BaseModel):
    node_id: str
    node_type: str
    depends_on: list[str] = []


class ExecutionPlanResponse(BaseModel):
    steps: list[ExecutionPlanNode]
    direction: str


async def get_execution_plan_by_node(
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    direction: str,
) -> ExecutionPlanResponse:
    """
    Retrieves the execution plan for a specific node or set of nodes in a graph.

    An execution plan is a list of nodes to be processed, where each node
    includes a list of its direct dependencies that are also part of the plan.
    This allows a frontend or execution engine to process nodes in the correct
    order, respecting parallel branches.

    Args:
        neo4j_driver (AsyncDriver): The asynchronous Neo4j driver for graph database access.
        graph_id (str): The identifier of the graph.
        node_id (str): The identifier of the node(s) to start from. For the 'multiple'
                       direction, this should be a comma-separated string of node IDs.
        direction (str): The direction of the execution plan ('upstream', 'downstream', 'all', 'multiple').

    Returns:
        ExecutionPlanResponse: An object containing the list of execution steps and the direction.
    """

    node_ids_to_process: str | list[str] = node_id
    if direction == "multiple":
        node_ids_to_process = [nid.strip() for nid in node_id.split(",") if nid.strip()]

    plan_data = await get_execution_plan(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_ids_to_process,
        direction=direction,
    )

    steps = [ExecutionPlanNode(**node_data) for node_data in plan_data]

    return ExecutionPlanResponse(steps=steps, direction=direction)


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

    open_router_api_key = decrypt_api_key(
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

    graphConfig = GraphConfigUpdate(**effective_config_data)

    if user_config.models.generateMermaid:
        graphConfig.custom_instructions = (
            graphConfig.custom_instructions + "\n\n" + MERMAID_DIAGRAM_PROMPT
        )

    return graphConfig, open_router_api_key


def search_graph_nodes(
    neo4j_driver: AsyncDriver, graph_id: str, search_request: NodeSearchRequest
) -> list[str]:
    """
    Searches for nodes in a graph based on the provided search request.

    Args:
        neo4j_driver (Neo4jAsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph to search.
        search_request (NodeSearchRequest): The search request containing the query parameters.

    Returns:
        list[Node]: A list of matching Node objects.
    """

    if search_request.direction == NodeSearchDirection.upstream:
        node_id = [
            get_parent_node_of_type(
                neo4j_driver=neo4j_driver,
                graph_id=graph_id,
                node_id=search_request.source_node_id,
                node_type=search_request.node_type,
            )
        ]
    elif search_request.direction == NodeSearchDirection.downstream:
        node_id = get_children_node_of_type(
            neo4j_driver=neo4j_driver,
            graph_id=graph_id,
            node_id=search_request.source_node_id,
            node_type=search_request.node_type,
        )
    else:
        raise ValueError("Invalid direction specified in search request.")

    return node_id
