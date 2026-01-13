import networkx as nx

from stitcher.analysis.graph.algorithms import (
    detect_circular_dependencies,
    has_path,
)


def test_detect_circular_dependencies():
    # 1. Arrange: Create a graph with a known cycle
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
            ("c.py", "a.py"),  # Cycle: a -> b -> c -> a
            ("d.py", "a.py"),  # Not part of cycle
        ]
    )

    # 2. Act
    cycles = detect_circular_dependencies(graph)

    # 3. Assert
    assert len(cycles) == 1
    # networkx can start the cycle from any node, so we sort to have a stable check
    assert sorted(cycles[0]) == ["a.py", "b.py", "c.py"]


def test_detect_circular_dependencies_no_cycles():
    # 1. Arrange: Create a Directed Acyclic Graph (DAG)
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
            ("a.py", "c.py"),
        ]
    )

    # 2. Act
    cycles = detect_circular_dependencies(graph)

    # 3. Assert
    assert len(cycles) == 0


def test_has_path():
    # 1. Arrange
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
            ("d.py", "e.py"),
        ]
    )

    # 2. Act & 3. Assert
    assert has_path(graph, "a.py", "c.py") is True
    assert has_path(graph, "a.py", "e.py") is False
    assert has_path(graph, "a.py", "a.py") is True  # A path to self always exists
