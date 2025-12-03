import asyncio
import logging
import os
import uuid
from asyncio import Semaphore
from typing import Literal

import sentry_sdk
from const.prompts import ROUTING_PROMPT
from database.neo4j.crud import (
    NodeRecord,
    get_ancestor_by_types,
    get_children_node_of_type,
    get_connected_prompt_nodes,
    get_execution_plan,
    get_parent_node_of_type,
)
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate, get_canvas_config
from database.pg.graph_ops.graph_crud import CompleteGraph
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
from services.context_merger_service import ContextMergerService
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

DEFAULT_LAST_N = 1


async def construct_message_history(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    user_id: str,
    node_id: str,
    system_prompt: str,
    add_current_node: bool = False,
    view: Literal["reduce", "full"] = "full",
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
            NodeTypeEnum.CONTEXT_MERGER,
        ]

        generator_ancestors = await get_ancestor_by_types(
            neo4j_driver=neo4j_driver,
            graph_id=graph_id,
            node_id=node_id,
            node_types=generator_types,
        )

        merger_node: "NodeRecord" | None = None
        merger_node_index = -1
        for i, ancestor in enumerate(generator_ancestors):
            if ancestor.type == NodeTypeEnum.CONTEXT_MERGER:
                merger_node = ancestor
                merger_node_index = i
                break

        semaphore = Semaphore(int(os.getenv("DATABASE_POOL_SIZE", "10")) // 2)

        async def process_generator_node(generator_node: NodeRecord) -> list[Message] | None:
            async with semaphore:
                if generator_node.type == NodeTypeEnum.CONTEXT_MERGER:
                    return None

                return await construct_message_from_generator_node(
                    pg_engine=pg_engine,
                    neo4j_driver=neo4j_driver,
                    graph_id=graph_id,
                    user_id=user_id,
                    generator_node_id=generator_node.id,
                    view=view,
                    clean_text=clean_text,
                    add_assistant_message=(add_current_node and generator_node.id == node_id)
                    or generator_node.id != node_id,
                    github_auto_pull=github_auto_pull,
                )

        messages: list[Message] = []
        if merger_node:
            merger_service = ContextMergerService(pg_engine, neo4j_driver, graph_id, user_id)
            messages = await merger_service.construct_merged_history(
                merger_node.id, system_prompt, github_auto_pull
            )

            # Process any nodes that come after the merger.
            nodes_after_merger = generator_ancestors[:merger_node_index]
            nodes_after_merger.reverse()

            if nodes_after_merger:
                tasks = [process_generator_node(node) for node in nodes_after_merger]
                results = await asyncio.gather(*tasks)
                for new_messages in results:
                    if new_messages:
                        messages.extend(new_messages)
        else:
            # Standard flow: no merger node found in history.
            if system_msg := system_message_builder(system_prompt):
                messages.append(system_msg)

            nodes_to_process = generator_ancestors
            nodes_to_process.reverse()

            if nodes_to_process:
                tasks = [process_generator_node(node) for node in nodes_to_process]
                results = await asyncio.gather(*tasks)
                for new_messages in results:
                    if new_messages:
                        messages.extend(new_messages)

        span.set_data("final_message_count", len(messages))
        return messages


async def construct_message_from_generator_node(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    user_id: str,
    generator_node_id: str,
    view: Literal["reduce", "full"],
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
                base_prompt = extract_context_prompt(
                    connected_nodes_records, nodes_data, view == "reduce"
                )

            # Step 2 : Add GITHUB content from the GITHUB nodes
            with sentry_sdk.start_span(
                op="chat.context.github", description="Extract GitHub context"
            ):
                github_prompt = await extract_context_github(
                    connected_nodes_records, nodes_data, github_auto_pull, view == "full"
                )

            # Step 3 : Add files content from the FILE_PROMPT nodes
            with sentry_sdk.start_span(
                op="chat.context.attachments", description="Extract file attachments"
            ):
                attachment_contents = await extract_context_attachment(
                    user_id, connected_nodes_records, nodes_data, pg_engine, view == "full"
                )

        user_message = Message(
            role=MessageRoleEnum.user,
            content=[
                MessageContent(
                    type=MessageContentTypeEnum.text, text=f"{github_prompt}\n{base_prompt}"
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
        view="full",
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
        open_router_api_key = await decrypt_api_key(
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
        canvas_config.pdf_engine = user_settings.blockAttachment.pdf_engine
        canvas_config.default_selected_tools = user_settings.tools.defaultSelectedTools
        canvas_config.tools_web_search_num_results = user_settings.toolsWebSearch.numResults
        canvas_config.tools_web_search_ignored_sites = user_settings.toolsWebSearch.ignoredSites
        canvas_config.tools_web_search_preferred_sites = user_settings.toolsWebSearch.preferredSites
        canvas_config.tools_web_search_custom_api_key = user_settings.toolsWebSearch.customApiKey
        canvas_config.tools_web_search_force_custom_api_key = (
            user_settings.toolsWebSearch.forceCustomApiKey
        )
        canvas_config.tools_link_extraction_max_length = user_settings.toolsLinkExtraction.maxLength
        canvas_config.block_context_merger_summarizer_model = (
            user_settings.blockContextMerger.summarizer_model
        )

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


def migrate_graph_ids(backup_data: CompleteGraph, user_id: str) -> CompleteGraph:
    """
    Migrates all IDs (Graph, Nodes, Edges) in a CompleteGraph object to new UUIDs.
    This is used when importing a graph to ensure it's treated as a new entity.

    Args:
        backup_data (CompleteGraph): The graph data to migrate.
        user_id (str): The ID of the user importing the graph.

    Returns:
        CompleteGraph: The graph data with migrated IDs.
    """
    # 1. Generate new Graph ID and reset metadata
    new_graph_id = uuid.uuid4()
    backup_data.graph.id = new_graph_id
    backup_data.graph.user_id = uuid.UUID(user_id)
    backup_data.graph.folder_id = None  # Reset folder so it appears in root
    backup_data.graph.created_at = None  # Let DB set defaults
    backup_data.graph.updated_at = None
    backup_data.graph.pinned = False

    # 2. Create ID Mapping for Nodes
    node_id_map = {}  # old_id -> new_id

    for node in backup_data.nodes:
        old_id = node.id
        new_id = str(uuid.uuid4())
        node_id_map[old_id] = new_id

        node.id = new_id
        node.graph_id = new_graph_id

    # 3. Update Node Parent References
    for node in backup_data.nodes:
        if node.parent_node_id and node.parent_node_id in node_id_map:
            node.parent_node_id = node_id_map[node.parent_node_id]

    # 4. Migrate Edges
    for edge in backup_data.edges:
        edge.id = str(uuid.uuid4())
        edge.graph_id = new_graph_id

        # Update Source Node ID
        if edge.source_node_id in node_id_map:
            old_source_id = edge.source_node_id
            new_source_id = node_id_map[old_source_id]
            edge.source_node_id = new_source_id

            # Update Source Handle ID if it contains the old node ID
            if edge.source_handle_id and old_source_id in edge.source_handle_id:
                edge.source_handle_id = edge.source_handle_id.replace(old_source_id, new_source_id)

        # Update Target Node ID
        if edge.target_node_id in node_id_map:
            old_target_id = edge.target_node_id
            new_target_id = node_id_map[old_target_id]
            edge.target_node_id = new_target_id

            # Update Target Handle ID if it contains the old node ID
            if edge.target_handle_id and old_target_id in edge.target_handle_id:
                edge.target_handle_id = edge.target_handle_id.replace(old_target_id, new_target_id)

    return backup_data
