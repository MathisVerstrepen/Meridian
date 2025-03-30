from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from database.pg.models import Node, Edge


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
            MERGE (n:GNode {unique_id: node_data.unique_id}) // Use MERGE for idempotency
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

    neo4j_nodes_data = [{"unique_id": f"{graph_id}:{node.id}"} for node in nodes]
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
        print(f"Neo4j update failed for graph {graph_id}: {e}")
        raise e
    except Exception as e:
        print(f"Unexpected error during Neo4j update for graph {graph_id}: {e}")
        raise e


async def get_all_ancestor_nodes(
    neo4j_driver: AsyncDriver, graph_id: str, node_id: str
) -> list[str]:
    """
    Retrieves all ancestor nodes of a given node in a graph.
    This function queries the Neo4j database to find all nodes that have a path
    to the target node through CONNECTS_TO relationships. It returns a list of
    node IDs for all ancestors.

    Parameters:
        neo4j_driver (AsyncDriver): The Neo4j driver instance to use for the query.
        graph_id (str): The ID of the graph containing the node.
        node_id (str): The ID of the node whose ancestors to retrieve.

    Returns:
        list[str]: A list of node IDs for all ancestor nodes. Only the node portion
                   of the unique_id is returned (without the graph_id prefix).

    Raises:
        Exception: If there is an error while querying the Neo4j database.
    """
    target_unique_id = f"{str(graph_id)}:{node_id}"
    ancestor_ids_tuples: list[tuple[str, str]] = []

    try:
        async with neo4j_driver.session(database="neo4j") as session:
            result = await session.run(
                """
                MATCH (ancestor:GNode)-[:CONNECTS_TO*]->(target:GNode {unique_id: $target_unique_id})
                RETURN DISTINCT ancestor.unique_id AS unique_id
                """,
                target_unique_id=target_unique_id,
            )

            ancestor_ids_tuples = [record["unique_id"] async for record in result]
    except Exception as e:
        print(f"Error querying Neo4j: {e}")
        raise

    ancestor_node_ids = []
    for uid in ancestor_ids_tuples:
        try:
            node_id = uid.split(":")[1]
            ancestor_node_ids.append(node_id)
        except IndexError as e:
            print(f"Warning: Invalid unique_id format: {uid} - {e}")

    return ancestor_node_ids
