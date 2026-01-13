import networkx as nx

from needle.pointer import L
from stitcher.analysis.rules.architecture import CircularDependencyRule


def test_circular_dependency_rule_with_cycle():
    # 1. Arrange
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("a.py", "b.py"),
        ("b.py", "c.py"),
        ("c.py", "a.py"),
    ])
    rule = CircularDependencyRule()

    # 2. Act
    violations = rule.check(graph)

    # 3. Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.kind == L.check.architecture.circular_dependency
    assert violation.fqn in {"a.py", "b.py", "c.py"}  # Start node is arbitrary
    assert "cycle" in violation.context
    assert "a.py ->" in violation.context["cycle"]
    assert "b.py ->" in violation.context["cycle"]
    assert "c.py ->" in violation.context["cycle"]


def test_circular_dependency_rule_without_cycle():
    # 1. Arrange
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("a.py", "b.py"),
        ("b.py", "c.py"),
    ])
    rule = CircularDependencyRule()

    # 2. Act
    violations = rule.check(graph)

    # 3. Assert
    assert len(violations) == 0