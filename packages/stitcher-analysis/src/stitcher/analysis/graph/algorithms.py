import networkx as nx
from .algo.cycles import detect_circular_dependencies


def has_path(graph: nx.DiGraph, source: str, target: str) -> bool:
    return nx.has_path(graph, source, target)


# Re-export for compatibility
__all__ = ["detect_circular_dependencies", "has_path"]
