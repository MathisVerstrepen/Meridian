import logging
from dataclasses import dataclass

from const.prompts import MERMAID_DIAGRAM_PROMPT, ROUTING_PROMPT
from database.neo4j.crud import (
    get_ancestor_by_types,
    get_children_node_of_type,
    get_connected_prompt_nodes,
    get_execution_plan,
    get_parent_node_of_type,
)
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate, get_canvas_config
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from database.pg.settings_ops.settings_crud import get_settings
from models.graphDTO import NodeSearchDirection, NodeSearchRequest
from models.message import (
    Message,
    MessageContent,
    MessageContentTypeEnum,
    MessageRoleEnum,
    NodeTypeEnum,
)
from models.usersDTO import SettingsDTO
from neo4j import AsyncDriver
from pydantic import BaseModel, field_validator
from services.crypto import decrypt_api_key
from services.node import (
    CleanTextOption,
    extract_context_attachment,
    extract_context_github,
    extract_context_prompt,
    node_to_message,
    system_message_builder,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


async def construct_message_history(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    system_prompt: str,
    add_current_node: bool = False,
    add_file_content: bool = True,
    clean_text: CleanTextOption = CleanTextOption.REMOVE_NOTHING,
    github_auto_pull: bool = False,
) -> list[Message]:
    """
    Constructs a series of messages representing a conversation based on a node and its ancestors
    in a graph.

    This function retrieves generator ancestor nodes (TEXT_TO_TEXT, PARALLELIZATION, ROUTING)
    of a specified node in a graph, then for each generator node fetches its connected prompt nodes
    (PROMPT, FILE_PROMPT, GITHUB) to construct the conversation messages.

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
    generator_types = [
        NodeTypeEnum.TEXT_TO_TEXT,
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
    ]

    # Extract the generator types ancestors to construct the route
    generator_ancestors = await get_ancestor_by_types(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        node_types=generator_types,
    )
    generator_ancestors.reverse()

    # Initialize messages with system prompt
    system_message = system_message_builder(system_prompt)
    messages = [system_message] if system_message else []

    # For each generator node, fetch connected prompt nodes and construct messages
    for generator_node in generator_ancestors:
        new_messages = await construct_message_from_generator_node(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            graph_id=graph_id,
            generator_node_id=generator_node.id,
            add_file_content=add_file_content,
            clean_text=clean_text,
            add_assistant_message=(add_current_node and generator_node.id == node_id)
            or generator_node.id != node_id,
            github_auto_pull=github_auto_pull,
        )

        if new_messages and len(new_messages):
            messages.extend(new_messages)

    return messages


async def construct_message_from_generator_node(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    generator_node_id: str,
    add_file_content: bool,
    clean_text: CleanTextOption,
    add_assistant_message: bool,
    github_auto_pull: bool = False,
) -> list[Message] | None:
    """
    Constructs a message from a generator node by fetching its connected prompt nodes and
    formatting the content.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL
            database access.
        neo4j_driver (AsyncDriver): The asynchronous Neo4j driver for graph database access.
        graph_id (str): The identifier of the graph.
        generator_node_id (str): The identifier of the generator node.
        add_file_content (bool): Whether to include file content in the message.
        clean_text (CleanTextOption): Whether to clean the text content.

    Returns:
        Message | None: The constructed message or None if no valid message could be created.
    """
    connected_nodes_records = await get_connected_prompt_nodes(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        generator_node_id=generator_node_id,
    )
    if not connected_nodes_records:
        return None

    nodes_data = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=[node.id for node in connected_nodes_records] + [generator_node_id],
    )

    # Step 1 : Concat all nodes of type PROMPT ordered by distance field
    base_prompt = extract_context_prompt(connected_nodes_records, nodes_data)

    # Step 2 : Add GITHUB content from the GITHUB nodes
    github_prompt = await extract_context_github(
        connected_nodes_records, nodes_data, github_auto_pull
    )

    # Step 3 : Add files content from the FILE_PROMPT nodes
    attachment_contents = await extract_context_attachment(
        connected_nodes_records, nodes_data, pg_engine, add_file_content
    )

    user_message = Message(
        role=MessageRoleEnum.user,
        content=[
            MessageContent(
                type=MessageContentTypeEnum.text, text=f"{base_prompt}\n{github_prompt}"
            ),
            *attachment_contents,
        ],
    )

    messages = [user_message]
    if add_assistant_message:
        message = await node_to_message(
            node=next((n for n in nodes_data if n.id == generator_node_id)),
            clean_text=clean_text,
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
    github_auto_pull: bool,
) -> list[Message]:
    """
    Assembles a list of messages for an aggregator prompt by collecting model replies and
    formatting them for parallelization.

    This function retrieves the parent prompt node, gathers the current node's data, and constructs
    an aggregator prompt by appending each model's reply. It then creates a list of `Message`
    objects, including a system message with the constructed prompt and a user message with
    the parent prompt content.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL
            database access.
        neo4j_driver (AsyncDriver): The asynchronous Neo4j driver for graph database access.
        graph_id (str): The identifier of the graph.
        node_id (str): The identifier of the current node.
        system_prompt (str): The system prompt to prepend to the aggregator prompt.

    Returns:
        list[Message]: A list of `Message` objects representing the constructed prompt and
            the parent prompt.

    Raises:
        ValueError: If the parent prompt node cannot be found.
    """
    nodes = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=[node_id],
    )

    node = nodes[0]
    if not isinstance(node.data, dict):
        raise ValueError("node.data is not a dict")
    models = node.data.get("models", [])

    aggregator_prompt = node.data.get("aggregator", {}).get("prompt", "")
    for idx, model in enumerate(models):
        reply = model.get("reply")

        aggregator_prompt += f"""\n
            === Answer {idx + 1} ===
            {reply}
            \n
        """

    system_message = system_message_builder(f"{system_prompt}\n{aggregator_prompt}")
    constructed_messages = await construct_message_from_generator_node(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        generator_node_id=node_id,
        add_file_content=True,
        clean_text=CleanTextOption.REMOVE_TAG_AND_TEXT,
        add_assistant_message=False,
        github_auto_pull=github_auto_pull,
    )

    messages: list[Message] = []
    if system_message:
        messages.append(system_message)
    if constructed_messages and len(constructed_messages):
        messages.extend(constructed_messages)

    return messages


async def construct_routing_prompt(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    user_id: str,
) -> tuple[list[Message], type[BaseModel]]:
    """
    Constructs a routing prompt for a specific node in a graph.

    This function retrieves the parent prompt node, gathers the current node's data, and constructs
    a routing prompt by appending the current node's data. It then creates a list of `Message`
    objects, including a system message with the constructed prompt and a user message with the
    parent prompt content.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The asynchronous SQLAlchemy engine for PostgreSQL
            database access.
        neo4j_driver (AsyncDriver): The asynchronous Neo4j driver for graph database access.
        graph_id (str): The identifier of the graph.
        node_id (str): The identifier of the current node.
        system_prompt (str): The system prompt to prepend to the routing prompt.

    Returns:
        list[Message]: A list of `Message` objects representing the constructed prompt and the
            parent prompt.

    Raises:
        ValueError: If the parent prompt node cannot be found.
    """
    parent_prompt_id = await get_parent_node_of_type(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        node_type=NodeTypeEnum.PROMPT,
    )
    if not parent_prompt_id:
        raise ValueError(f"Parent prompt node not found for node ID {node_id}")

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
    user_config = SettingsDTO.model_validate(user_settings)

    node = nodes[0]
    if not isinstance(node.data, dict):
        raise ValueError("node.data is not a dict")
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

    if not isinstance(parent_prompt_node[0].data, dict):
        raise ValueError("parent_prompt_node[0].data is not a dict")
    routing_prompt = ROUTING_PROMPT.format(
        user_query=parent_prompt_node[0].data.get("prompt", ""),
        routes=routes,
    )

    class Schema(BaseModel):
        route: str

        @field_validator("route")
        def validate_route(cls, v):
            if v not in routes:
                raise ValueError(f"Invalid route: {v}. Must be one of {list(routes.keys())}")
            return v

    messages = []
    if system_message := system_message_builder(f"{routing_prompt}"):
        messages.append(system_message)

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
        direction (str): The direction of the execution plan
            ('upstream', 'downstream', 'all', 'multiple').

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
    FieldMapping("custom_instructions", "custom_instructions", "models.globalSystemPrompt"),
    FieldMapping("max_tokens", "max_tokens", "models.maxTokens"),
    FieldMapping("temperature", "temperature", "models.temperature"),
    FieldMapping("top_p", "top_p", "models.topP"),
    FieldMapping("top_k", "top_k", "models.topK"),
    FieldMapping("frequency_penalty", "frequency_penalty", "models.frequencyPenalty"),
    FieldMapping("presence_penalty", "presence_penalty", "models.presencePenalty"),
    FieldMapping("repetition_penalty", "repetition_penalty", "models.repetitionPenalty"),
    FieldMapping("reasoning_effort", "reasoning_effort", "models.reasoningEffort"),
    FieldMapping("exclude_reasoning", "exclude_reasoning", "models.excludeReasoning"),
    FieldMapping(
        "include_thinking_in_context",
        "includeThinkingInContext",
        "general.includeThinkingInContext",
    ),
    FieldMapping("block_github_auto_pull", "blockGithub.autoPull", "blockGithub.autoPull"),
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
        tuple[GraphConfigUpdate, str]: A tuple containing the effective graph configuration and
            the OpenRouter API key.
    """

    user_settings = await get_settings(pg_engine=pg_engine, user_id=user_id)
    user_config = SettingsDTO.model_validate(user_settings)
    open_router_api_key = decrypt_api_key(
        db_payload=(
            user_config.account.openRouterApiKey if user_config.account.openRouterApiKey else ""
        ),
    )
    if not open_router_api_key:
        raise ValueError("Invalid OpenRouter API key.")

    canvas_config = await get_canvas_config(
        pg_engine=pg_engine,
        graph_id=graph_id,
    )

    effective_config_data = {
        m.target: (
            canvas_value
            if (canvas_value := getattr(canvas_config, m.canvas_source, None)) is not None
            else get_nested_attr(user_config, m.user_source_path)
        )
        for m in mappings
    }

    graphConfig = GraphConfigUpdate(**effective_config_data)

    if user_config.models.generateMermaid:
        graphConfig.custom_instructions = (
            graphConfig.custom_instructions or "" + "\n\n" + MERMAID_DIAGRAM_PROMPT
        )

    return graphConfig, open_router_api_key


async def search_graph_nodes(
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

    node_id = []
    if search_request.direction == NodeSearchDirection.upstream:
        parent_node = await get_parent_node_of_type(
            neo4j_driver=neo4j_driver,
            graph_id=graph_id,
            node_id=search_request.source_node_id,
            node_type=[node.value for node in search_request.node_type],
        )
        if parent_node:
            node_id.append(parent_node)

    elif search_request.direction == NodeSearchDirection.downstream:
        children_nodes = await get_children_node_of_type(
            neo4j_driver=neo4j_driver,
            graph_id=graph_id,
            node_id=search_request.source_node_id,
            node_type=[node.value for node in search_request.node_type],
        )
        if children_nodes:
            node_id.extend(children_nodes)
    else:
        raise ValueError("Invalid direction specified in search request.")

    return node_id
