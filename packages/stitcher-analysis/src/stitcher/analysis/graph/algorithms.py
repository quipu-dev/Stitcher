from typing import List
import networkx as nx


def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    return [list(cycle) for cycle in nx.simple_cycles(graph)]


def has_path(graph: nx.DiGraph, source: str, target: str) -> bool:
    return nx.has_path(graph, source, target)
