import asyncio
import logging
import os
from asyncio import Semaphore

import sentry_sdk
from const.prompts import ROUTING_PROMPT
from database.neo4j.crud import (
    get_ancestor_by_types,
    get_children_node_of_type,
    get_connected_prompt_nodes,
    get_execution_plan,
    get_parent_node_of_type,
)
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate, get_canvas_config
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from models.graphDTO import NodeSearchDirection, NodeSearchRequest
from models.message import (
    Message,
    MessageContent,
    MessageContentTypeEnum,
    MessageRoleEnum,
    NodeTypeEnum,
)
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
from services.settings import concat_system_prompts, get_user_settings
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


async def construct_message_history(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    user_id: str,
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
    with sentry_sdk.start_span(
        op="chat.history.build", description="Build message history"
    ) as span:
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
        span.set_data("generator_ancestors_count", len(generator_ancestors))

        # Initialize messages with system prompt
        system_message = system_message_builder(system_prompt)
        messages = [system_message] if system_message else []

        semaphore = Semaphore(int(os.getenv("DATABASE_POOL_SIZE", "10")) // 2)

        async def process_generator_node(generator_node):
            async with semaphore:
                return await construct_message_from_generator_node(
                    pg_engine=pg_engine,
                    neo4j_driver=neo4j_driver,
                    graph_id=graph_id,
                    user_id=user_id,
                    generator_node_id=generator_node.id,
                    add_file_content=add_file_content,
                    clean_text=clean_text,
                    add_assistant_message=(add_current_node and generator_node.id == node_id)
                    or generator_node.id != node_id,
                    github_auto_pull=github_auto_pull,
                )

        with sentry_sdk.start_span(
            op="chat.history.process_ancestors", description="Process generator ancestors"
        ):
            # Process generator nodes in parallel while maintaining order
            tasks = [
                process_generator_node(generator_node) for generator_node in generator_ancestors
            ]
            results = await asyncio.gather(*tasks)

            for new_messages in results:
                if new_messages and len(new_messages):
                    messages.extend(new_messages)

        span.set_data("final_message_count", len(messages))

        return messages


async def construct_message_from_generator_node(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    user_id: str,
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
    with sentry_sdk.start_span(
        op="chat.history.node", description="Construct message from one generator node"
    ) as span:
        span.set_data("generator_node_id", generator_node_id)
        connected_nodes_records = await get_connected_prompt_nodes(
            neo4j_driver=neo4j_driver,
            graph_id=graph_id,
            generator_node_id=generator_node_id,
        )
        if not connected_nodes_records:
            return None

        span.set_data("connected_prompt_nodes_count", len(connected_nodes_records))

        nodes_data = await get_nodes_by_ids(
            pg_engine=pg_engine,
            graph_id=graph_id,
            node_ids=[node.id for node in connected_nodes_records] + [generator_node_id],
        )

        with sentry_sdk.start_span(op="chat.context.extract", description="Extract all context"):
            # Step 1 : Concat all nodes of type PROMPT ordered by distance field
            with sentry_sdk.start_span(
                op="chat.context.prompt", description="Extract prompt context"
            ):
                base_prompt = extract_context_prompt(connected_nodes_records, nodes_data)

            # Step 2 : Add GITHUB content from the GITHUB nodes
            with sentry_sdk.start_span(
                op="chat.context.github", description="Extract GitHub context"
            ):
                github_prompt = await extract_context_github(
                    connected_nodes_records, nodes_data, github_auto_pull
                )

            # Step 3 : Add files content from the FILE_PROMPT nodes
            with sentry_sdk.start_span(
                op="chat.context.attachments", description="Extract file attachments"
            ):
                attachment_contents = await extract_context_attachment(
                    user_id, connected_nodes_records, nodes_data, pg_engine, add_file_content
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
    user_id: str,
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
        user_id=user_id,
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

    user_settings = await get_user_settings(pg_engine, user_id)

    node = nodes[0]
    if not isinstance(node.data, dict):
        raise ValueError("node.data is not a dict")
    routes = {
        route.id: route.description
        for route in next(
            (
                routeGroup
                for routeGroup in user_settings.blockRouting.routeGroups
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


async def get_effective_graph_config(
    pg_engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
) -> tuple[GraphConfigUpdate, str, str]:
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

    with sentry_sdk.start_span(op="config.build", description="Build effective graph config"):
        user_settings = await get_user_settings(pg_engine, user_id)
        open_router_api_key = decrypt_api_key(
            db_payload=(
                user_settings.account.openRouterApiKey
                if user_settings.account.openRouterApiKey
                else ""
            ),
        )
        if not open_router_api_key:
            raise ValueError("Invalid OpenRouter API key.")

        canvas_config = await get_canvas_config(
            pg_engine=pg_engine,
            graph_id=graph_id,
        )

        system_prompt = concat_system_prompts(
            user_settings.models.systemPrompt, canvas_config.custom_instructions
        )

        canvas_config.exclude_reasoning = user_settings.models.excludeReasoning
        canvas_config.include_thinking_in_context = user_settings.general.includeThinkingInContext
        canvas_config.block_github_auto_pull = user_settings.blockGithub.autoPull

        return canvas_config, system_prompt, open_router_api_key


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
