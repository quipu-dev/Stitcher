from typing import List
import networkx as nx


def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    """
    Finds all simple cycles in a directed graph.

    A simple cycle is a path where the start and end nodes are the same,
    and no other nodes are repeated. Self-loops are not considered simple cycles.

    Args:
        graph: The directed graph to check.

    Returns:
        A list of cycles, where each cycle is represented as a list of
        node identifiers (file paths).
    """
    return [list(cycle) for cycle in nx.simple_cycles(graph)]


def has_path(graph: nx.DiGraph, source: str, target: str) -> bool:
    """
    Checks if a path exists between two nodes in the graph.

    Args:
        graph: The directed graph to check.
        source: The starting node.
        target: The ending node.

    Returns:
        True if a path exists, False otherwise.
    """
    return nx.has_path(graph, source, target)
