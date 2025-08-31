import logging
import sys

from database.pg.models import Edge, Node
from models.message import NodeTypeEnum
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")


async def _execute_neo4j_update_in_tx(tx, graph_id_prefix, nodes_data, edges_data):
    """
    Executes a Neo4j transaction to update graph data for a specific graph prefix.

    This function performs three main operations within a transaction:
    1. Deletes all existing nodes (and their relationships) that have unique_ids starting with the
    given prefix
    2. Creates new nodes based on the provided nodes_data
    3. Creates new edges between nodes based on the provided edges_data

    Args:
        tx: Neo4j transaction object to execute queries
        graph_id_prefix (str): Prefix used to identify nodes belonging to a specific graph
        nodes_data (list): List of dictionaries containing node data, each must have a 'unique_id'
            key
        edges_data (list): List of dictionaries containing edge data, each must have
            'source_unique_id' and 'target_unique_id' keys

    Note:
        - Uses MERGE operations for idempotency when creating nodes and relationships
        - Completely replaces the existing graph structure with the new one
        - Both nodes_data and edges_data can be empty (None)
    """
    # 1. Delete Old Nodes/Edges in Neo4j for this graph_id
    await tx.run(
        """
        MATCH (n:GNode)
        WHERE n.unique_id STARTS WITH $prefix
        DETACH DELETE n
        """,
        prefix=graph_id_prefix,
    )

    # 2. Create New Nodes in Neo4j
    if nodes_data:
        await tx.run(
            """
            UNWIND $nodes AS node_data
            MERGE (n:GNode {unique_id: node_data.unique_id})
            SET n.type = node_data.type
            """,
            nodes=nodes_data,
        )

    # 3. Create New Edges in Neo4j
    if edges_data:
        await tx.run(
            """
            UNWIND $edges AS edge_data
            MATCH (source:GNode {unique_id: edge_data.source_unique_id})
            MATCH (target:GNode {unique_id: edge_data.target_unique_id})
            MERGE (source)-[r:CONNECTS_TO]->(target) // Use MERGE for idempotency
            """,
            edges=edges_data,
        )


async def update_neo4j_graph(
    neo4j_driver: AsyncDriver,
    graph_id: str,
    nodes: list["Node"] | None = None,
    edges: list["Edge"] | None = None,
) -> None:
    """
    Update a graph structure in the Neo4j database.

    This function updates the Neo4j database with the provided graph data, which consists of nodes
    and edges.
    Each node and edge is prefixed with the graph_id to ensure uniqueness within the Neo4j database.

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance for database connections
        graph_id (str): The unique identifier for the graph being updated
        nodes (list[Node] | None, optional): A list of Node objects to be added/updated in the
            graph, by default None
        edges (list[Edge] | None, optional): A list of Edge objects to be added/updated in the
            graph, by default None

    Raises:
        Neo4jError: If there's an error during the Neo4j database operation
        Exception: If any other unexpected error occurs during the update process
    """
    nodes = nodes or []
    edges = edges or []

    neo4j_nodes_data = [
        {
            "unique_id": f"{graph_id}:{node.id}",
            "type": node.type,
        }
        for node in nodes
    ]
    neo4j_edges_data = [
        {
            "source_unique_id": f"{graph_id}:{edge.source_node_id}",
            "target_unique_id": f"{graph_id}:{edge.target_node_id}",
        }
        for edge in edges
    ]
    graph_id_prefix = f"{graph_id}:"

    try:
        async with neo4j_driver.session(database="neo4j") as neo_session:
            await neo_session.execute_write(
                _execute_neo4j_update_in_tx,
                graph_id_prefix,
                neo4j_nodes_data,
                neo4j_edges_data,
            )
    except Neo4jError as e:
        logger.error(f"Neo4j update failed for graph {graph_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during Neo4j update for graph {graph_id}: {e}")
        raise e


NODE_TYPE_PRIORITY = {
    "prompt": 0,
    "filePrompt": 1,
    "textToText": 2,
}
DEFAULT_TYPE_PRIORITY = sys.maxsize


class NodeRecord(BaseModel):
    id: str
    type: NodeTypeEnum
    distance: int


async def get_ancestor_by_types(
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    node_types: list[NodeTypeEnum],
) -> list[NodeRecord]:
    """
    Retrieves the starting node (if it matches the type criteria) and all its
    ancestor nodes of specific types for a given node in Neo4j.

    This function queries Neo4j to find all ancestor nodes of the specified types
    connected to the target node via an incoming CONNECTS_TO relationship path.
    It also includes the starting node in the results if its type is in the
    provided list of node types. The results are ordered by distance, starting
    with the target node itself (distance 0).

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph containing the node.
        node_id (str): The ID of the node whose ancestors to retrieve.
        node_types (list[str]): The types of the ancestor nodes to search for.

    Returns:
        list[dict] | None: A list of ancestor nodes (each represented as a dictionary)
                            if found, otherwise None.

    Raises:
        Neo4jError: If there is an error during the Neo4j database operation.
        Exception: If any other unexpected error occurs.
    """
    target_unique_id = f"{str(graph_id)}:{node_id}"
    ancestors = []

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                """
                MATCH path = (ancestor:GNode)-[:CONNECTS_TO*0..]->(target:GNode 
                    {unique_id: $target_unique_id})
                WHERE ancestor.type IN $node_types
                RETURN ancestor.unique_id AS unique_id,
                       ancestor.type AS type,
                       length(path) AS distance
                ORDER BY length(path) ASC
                """,
                target_unique_id=target_unique_id,
                node_types=node_types,
            )

            async for record in result:
                ancestors.append(
                    NodeRecord(
                        id=record["unique_id"].split(":", 1)[1],
                        type=record["type"],
                        distance=record["distance"],
                    )
                )

            return ancestors

    except Neo4jError as e:
        logger.error(f"Neo4j query failed for generator ancestors of {target_unique_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error processing generator ancestors for {target_unique_id}: {e}")
        raise


async def get_connected_prompt_nodes(
    neo4j_driver: AsyncDriver, graph_id: str, generator_node_id: str
) -> list[NodeRecord]:
    """
    Retrieves all nodes of type PROMPT, FILE_PROMPT, or GITHUB that are ancestors
    of a given generator node, without traversing through any other generator nodes.

    This function finds all incoming paths of "prompt-like" nodes that lead to the
    specified generator node. The search stops and excludes any path that contains
    another generator node (TEXT_TO_TEXT, PARALLELIZATION, ROUTING) as an
    intermediate step.

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph containing the nodes.
        generator_node_id (str): The ID of the generator node to find connections for.

    Returns:
        list[dict]: A list of unique dictionaries, each containing 'node_id', 'type',
                    and 'distance' for the connected prompt nodes, ordered by their
                    distance from the generator node.

    Raises:
        Neo4jError: If there is an error during the Neo4j database operation.
        Exception: If any other unexpected error occurs.
    """
    generator_unique_id = f"{str(graph_id)}:{generator_node_id}"
    prompt_types = [
        NodeTypeEnum.PROMPT,
        NodeTypeEnum.FILE_PROMPT,
        NodeTypeEnum.GITHUB,
    ]
    generator_types = [
        NodeTypeEnum.TEXT_TO_TEXT,
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
    ]

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                """
                MATCH path = (prompt:GNode)-[:CONNECTS_TO*]->
                    (generator:GNode {unique_id: $generator_unique_id})
                // 1. Ensure the starting node of the path is a prompt-type node
                WHERE prompt.type IN $prompt_types
                  // 2. Crucially, ensure no intermediate nodes in the path are generator types
                  AND size([n IN nodes(path)[1..-1] WHERE n.type IN $generator_types]) = 0
                // 3. Return distinct prompt nodes to avoid duplicates from multiple paths
                WITH DISTINCT prompt, length(path) as distance
                // 4. Order by distance to process nodes closest to the generator first
                ORDER BY distance
                RETURN prompt.unique_id AS unique_id,
                       prompt.type AS type,
                       distance
                """,
                generator_unique_id=generator_unique_id,
                prompt_types=prompt_types,
                generator_types=generator_types,
            )

            connected_nodes = []
            async for record in result:
                connected_nodes.append(
                    NodeRecord(
                        id=record["unique_id"].split(":", 1)[1],
                        type=record["type"],
                        distance=record["distance"],
                    )
                )

            return connected_nodes

    except Neo4jError as e:
        logger.error(f"Neo4j query failed for connected prompt nodes of {generator_unique_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error processing connected prompt nodes for {generator_unique_id}: {e}")
        raise


async def get_parent_node_of_type(
    neo4j_driver: AsyncDriver, graph_id: str, node_id: str, node_type: str | list[str]
) -> str | None:
    """
    Retrieves the parent node of a specific type for a given node in Neo4j.

    This function queries Neo4j to find the first parent node of the specified type
    connected to the target node via an incoming CONNECTS_TO relationship path.

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph containing the node.
        node_id (str): The ID of the node whose parent to retrieve.
        node_type (str | list[str]): The type(s) of the parent node to search for.

    Returns:
        str | None: The ID of the parent node (without the graph_id prefix) if found,
                    otherwise None.

    Raises:
        Neo4jError: If there is an error during the Neo4j database operation.
        Exception: If any other unexpected error occurs.
    """
    target_unique_id = f"{str(graph_id)}:{node_id}"

    # Handle both str and list[str] for node_type
    if isinstance(node_type, str):
        node_type_list = [node_type]
    else:
        node_type_list = node_type

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                """
                MATCH path = (parent:GNode)-[:CONNECTS_TO*]->
                    (target:GNode {unique_id: $target_unique_id})
                WHERE parent.type IN $node_type_list
                RETURN parent.unique_id AS unique_id
                ORDER BY length(path)
                LIMIT 1
                """,
                target_unique_id=target_unique_id,
                node_type_list=node_type_list,
            )

            record = await result.single()
            if record:
                unique_id = record.get("unique_id")
                if isinstance(unique_id, str):
                    return unique_id.split(":", 1)[1]
                return None
            else:
                return None
    except Neo4jError as e:
        logger.error(f"Neo4j query failed for parent of {target_unique_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error processing parent for {target_unique_id}: {e}")
        raise


async def get_children_node_of_type(
    neo4j_driver: AsyncDriver, graph_id: str, node_id: str, node_type: str | list[str]
) -> list[str] | None:
    """
    Retrieves the closest child node(s) of a specific type for a given node in Neo4j.

    If multiple children of the specified type are found at the same shortest
    distance, a list of their IDs is returned. Otherwise, the ID of the single
    closest child is returned.

    This function queries Neo4j to find child nodes of the specified type
    connected to the target node via an outgoing CONNECTS_TO relationship path.

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph containing the node.
        node_id (str): The ID of the node whose child to retrieve.
        node_type (str | list[str]): The type(s) of the child node to search for.

    Returns:
        str | list[str] | None: The ID of the child node, a list of child node IDs
                                if multiple are found at the same shortest distance,
                                or None if no such child is found.

    Raises:
        Neo4jError: If there is an error during the Neo4j database operation.
        Exception: If any other unexpected error occurs.
    """
    target_unique_id = f"{str(graph_id)}:{node_id}"

    # Handle both str and list[str] for node_type
    if isinstance(node_type, str):
        node_type_list = [node_type]
    else:
        node_type_list = node_type

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                """
                MATCH path = (target:GNode {unique_id: $target_unique_id})-[:CONNECTS_TO*]->
                    (child:GNode)
                WHERE child.type IN $node_type_list
                WITH child, length(path) AS len
                ORDER BY len ASC
                // Collect all potential children, ordered by distance
                WITH collect({id: child.unique_id, len: len}) AS children_data
                // Find the minimum distance
                WITH children_data, CASE WHEN size(children_data) > 0 THEN children_data[0].len 
                    ELSE null END AS min_len
                // Return all children that match the minimum distance
                RETURN [c IN children_data WHERE c.len = min_len | c.id] AS unique_ids
                """,
                target_unique_id=target_unique_id,
                node_type_list=node_type_list,
            )

            record = await result.single()
            if record:
                unique_ids = record["unique_ids"]

                if not unique_ids:
                    return None

                return [uid.split(":", 1)[1] for uid in unique_ids]
            else:
                return None

    except Neo4jError as e:
        logger.error(f"Neo4j query failed for child of {target_unique_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error processing child for {target_unique_id}: {e}")
        raise


async def get_execution_plan(
    neo4j_driver: AsyncDriver, graph_id: str, node_id: str | list[str], direction: str
) -> list[dict]:
    """
    Generates an execution plan for a subgraph starting from a specific node or set of nodes.

    An execution plan is a list of nodes to be processed, where each node
    includes a list of its direct dependencies that are also part of the plan.
    This function returns only "executable" node types and remaps dependencies
    to the nearest executable ancestor, skipping over non-executable nodes.

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph.
        node_id (str | list[str]): The ID of the node to start from, or a list of IDs for the
            'multiple' direction. Ignored if direction is 'all'.
        direction (str): 'downstream', 'upstream', 'all', or 'multiple'.

    Returns:
        list[dict]: A list of dictionaries, each representing an executable node
                    in the plan. Each dict contains 'node_id', 'node_type',
                    and 'depends_on' keys.

    Raises:
        ValueError: If the direction is invalid.
        TypeError: If node_id is not a list for the 'multiple' direction.
        Neo4jError: For database-related issues.
    """
    graph_id_prefix = f"{str(graph_id)}:"
    executable_types = [
        NodeTypeEnum.TEXT_TO_TEXT,
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
    ]

    params: dict = {"executable_types": executable_types}
    initial_query_part = ""
    log_identifier = ""

    if direction in ["downstream", "upstream"]:
        start_node_unique_id = f"{graph_id_prefix}{node_id}"
        if direction == "downstream":
            path_match_clause = """MATCH path = 
            (start:GNode {unique_id: $start_node_unique_id})-[:CONNECTS_TO*0..]->(p:GNode)"""
        else:  # upstream
            path_match_clause = """MATCH path = (p:GNode)-[:CONNECTS_TO*0..]->
                (start:GNode {unique_id: $start_node_unique_id})"""

        initial_query_part = f"""
        {path_match_clause}
        WITH nodes(path) AS path_nodes
        UNWIND path_nodes AS n
        WITH collect(DISTINCT n) AS plan_nodes
        """
        params["start_node_unique_id"] = start_node_unique_id
        log_identifier = start_node_unique_id

    elif direction == "all":
        initial_query_part = """
        MATCH (n:GNode)
        WHERE n.unique_id STARTS WITH $graph_id_prefix
        WITH collect(DISTINCT n) AS plan_nodes
        """
        params["graph_id_prefix"] = graph_id_prefix
        log_identifier = graph_id_prefix

    elif direction == "multiple":
        if not isinstance(node_id, list):
            raise TypeError("For 'multiple' direction, node_id must be a list.")

        start_node_unique_ids = [f"{graph_id_prefix}{nid}" for nid in node_id]
        path_match_clause = """MATCH path = (start:GNode)-[:CONNECTS_TO*0..]->(p:GNode)
            WHERE start.unique_id IN $start_node_unique_ids"""

        initial_query_part = f"""
        {path_match_clause}
        WITH nodes(path) AS path_nodes
        UNWIND path_nodes AS n
        WITH collect(DISTINCT n) AS plan_nodes
        """
        params["start_node_unique_ids"] = start_node_unique_ids
        log_identifier = ", ".join(start_node_unique_ids)

    else:
        raise ValueError("Direction must be 'upstream', 'downstream', 'all', or 'multiple'")

    dependency_logic_query = """
    // Filter the subgraph to get only executable nodes
    WITH [node IN plan_nodes WHERE node.type IN $executable_types] AS executable_nodes, plan_nodes

    // For each executable node, find its dependencies
    UNWIND executable_nodes AS exec_node

    // Find all potential dependency paths. `OPTIONAL MATCH` handles nodes with no dependencies.
    OPTIONAL MATCH path = (dep:GNode)-[:CONNECTS_TO*1..]->(exec_node)

    // Group all potential dependencies and their paths for each exec_node.
    // By collecting a map, we avoid the warning about aggregating NULLs.
    WITH exec_node, collect({dep: dep, path: path}) AS potential_deps, plan_nodes, executable_nodes

    // Use a list comprehension to filter the collected items and extract the dependency ID.
    WITH exec_node, [item IN potential_deps WHERE
        // The dependency must exist (this handles the root node case where `dep` is NULL)
        item.dep IS NOT NULL
        // The dependency must itself be an executable node
        AND item.dep IN executable_nodes
        // All nodes in the path from dependency to node must be within the overall plan
        AND all(n IN nodes(item.path) WHERE n IN plan_nodes)
        // The path between the dependency and the node must not contain any *other* 
        // executable nodes
        AND size([inter_node IN nodes(item.path)[1..-1] WHERE inter_node IN executable_nodes]) = 0
    | item.dep.unique_id] AS dependencies

    RETURN exec_node.unique_id AS unique_id,
           exec_node.type AS type,
           dependencies
    """

    query = f"{initial_query_part}\n{dependency_logic_query}"
    plan = []

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(query, params)
            async for record in result:
                # Strip graph_id prefix from all returned IDs
                deps = [uid.split(":", 1)[1] for uid in record["dependencies"] if uid]
                plan.append(
                    {
                        "node_id": record["unique_id"].split(":", 1)[1],
                        "node_type": record["type"],
                        "depends_on": deps,
                    }
                )
    except Neo4jError as e:
        logger.error(f"Neo4j query failed for execution plan of {log_identifier}: {e}")
        raise e

    return plan
