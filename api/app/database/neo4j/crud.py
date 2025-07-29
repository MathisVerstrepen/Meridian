from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from database.pg.models import Node, Edge
import logging
import sys

logger = logging.getLogger("uvicorn.error")


async def _execute_neo4j_update_in_tx(tx, graph_id_prefix, nodes_data, edges_data):
    """
    Executes a Neo4j transaction to update graph data for a specific graph prefix.

    This function performs three main operations within a transaction:
    1. Deletes all existing nodes (and their relationships) that have unique_ids starting with the given prefix
    2. Creates new nodes based on the provided nodes_data
    3. Creates new edges between nodes based on the provided edges_data

    Args:
        tx: Neo4j transaction object to execute queries
        graph_id_prefix (str): Prefix used to identify nodes belonging to a specific graph
        nodes_data (list): List of dictionaries containing node data, each must have a 'unique_id' key
        edges_data (list): List of dictionaries containing edge data, each must have 'source_unique_id'
                          and 'target_unique_id' keys

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

    This function updates the Neo4j database with the provided graph data, which consists of nodes and edges.
    Each node and edge is prefixed with the graph_id to ensure uniqueness within the Neo4j database.

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance for database connections
        graph_id (str): The unique identifier for the graph being updated
        nodes (list[Node] | None, optional): A list of Node objects to be added/updated in the graph, by default None
        edges (list[Edge] | None, optional): A list of Edge objects to be added/updated in the graph, by default None

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


async def get_all_ancestor_nodes(
    neo4j_driver: AsyncDriver, graph_id: str, node_id: str
) -> list[str]:
    """
    Retrieves all ancestor nodes of a given node, sorted by distance and type.

    This function queries Neo4j for all nodes connected to the target node via
    incoming CONNECTS_TO relationships. The ancestors are returned in a stable order:
    1. By distance (number of hops) from the target node (ascending).
    2. By node type priority ('prompt' before 'textToText', others last).

    Args:
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (str): The ID of the graph containing the node.
        node_id (str): The ID of the node whose ancestors to retrieve.

    Returns:
        list[str]: A sorted list of ancestor node IDs (without the graph_id prefix).

    Raises:
        Neo4jError: If there is an error during the Neo4j database operation.
        Exception: If any other unexpected error occurs.
    """
    target_unique_id = f"{str(graph_id)}:{node_id}"
    ancestor_data: list[tuple[str, str, int]] = []

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                """
                MATCH path = (ancestor:GNode)-[:CONNECTS_TO*]->(target:GNode {unique_id: $target_unique_id})
                RETURN ancestor.unique_id AS unique_id,
                       ancestor.type AS type,
                       length(path) AS distance
                """,
                target_unique_id=target_unique_id,
            )

            async for record in result:
                ancestor_data.append(
                    (record["unique_id"], record["type"], record["distance"])
                )
    except Neo4jError as e:
        logger.error(f"Neo4j query failed for ancestors of {target_unique_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error processing ancestors for {target_unique_id}: {e}")
        raise

    ancestor_data.sort(
        key=lambda item: (
            item[2],
            NODE_TYPE_PRIORITY.get(item[1], DEFAULT_TYPE_PRIORITY),
        )
    )

    sorted_ancestor_node_ids = [uid.split(":", 1)[1] for uid, _, _ in ancestor_data]

    return sorted_ancestor_node_ids


async def get_parent_node_of_type(
    neo4j_driver: AsyncDriver, graph_id: str, node_id: str, node_type: str | list[str]
) -> str | None:
    """
    Retrieves the parent node of a specific type for a given node in Neo4j.

    This function queries Neo4j to find the first parent node of the specified type
    connected to the target node via an incoming CONNECTS_TO relationship.

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
                MATCH path = (parent:GNode)-[:CONNECTS_TO]->(target:GNode {unique_id: $target_unique_id})
                WHERE parent.type IN $node_type_list
                RETURN parent.unique_id AS unique_id
                LIMIT 1
                """,
                target_unique_id=target_unique_id,
                node_type_list=node_type_list,
            )

            record = await result.single()
            if record:
                return record["unique_id"].split(":", 1)[1]
            else:
                return None
    except Neo4jError as e:
        logger.error(f"Neo4j query failed for parent of {target_unique_id}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Error processing parent for {target_unique_id}: {e}")
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
        node_id (str | list[str]): The ID of the node to start from, or a list of IDs for the 'multiple' direction. Ignored if direction is 'all'.
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
    executable_types = ["textToText", "parallelization", "routing"]

    params = {"executable_types": executable_types}
    initial_query_part = ""
    log_identifier = ""

    if direction in ["downstream", "upstream"]:
        start_node_unique_id = f"{graph_id_prefix}{node_id}"
        if direction == "downstream":
            path_match_clause = "MATCH path = (start:GNode {unique_id: $start_node_unique_id})-[:CONNECTS_TO*0..]->(p:GNode)"
        else:  # upstream
            path_match_clause = "MATCH path = (p:GNode)-[:CONNECTS_TO*0..]->(start:GNode {unique_id: $start_node_unique_id})"

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
        path_match_clause = "MATCH path = (start:GNode)-[:CONNECTS_TO*0..]->(p:GNode) WHERE start.unique_id IN $start_node_unique_ids"

        initial_query_part = f"""
        {path_match_clause}
        WITH nodes(path) AS path_nodes
        UNWIND path_nodes AS n
        WITH collect(DISTINCT n) AS plan_nodes
        """
        params["start_node_unique_ids"] = start_node_unique_ids
        log_identifier = ", ".join(start_node_unique_ids)

    else:
        raise ValueError(
            "Direction must be 'upstream', 'downstream', 'all', or 'multiple'"
        )

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
        // The path between the dependency and the node must not contain any *other* executable nodes
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
            result = await session.run(query, **params)
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
