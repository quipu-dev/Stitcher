from unittest.mock import MagicMock
import networkx as nx

from needle.pointer import L
from stitcher.analysis.schema import Violation
from stitcher.analysis.engines.architecture import ArchitectureEngine


def test_architecture_engine_analyze_flow():
    # 1. Arrange
    mock_store = MagicMock()
    mock_builder = MagicMock()
    mock_rule = MagicMock()

    # Configure mocks
    mock_graph = nx.DiGraph()
    mock_builder.build_dependency_graph.return_value = mock_graph

    mock_violation = Violation(kind=L.check.architecture.circular_dependency, fqn="a.py")
    mock_rule.check.return_value = [mock_violation]

    # 2. Act
    engine = ArchitectureEngine(builder=mock_builder, rules=[mock_rule])
    results = engine.analyze(mock_store)

    # 3. Assert
    # Assert that the engine returns the violations from the rule
    assert results == [mock_violation]

    # Assert that the engine correctly orchestrated its dependencies
    mock_builder.build_dependency_graph.assert_called_once_with(mock_store)
    mock_rule.check.assert_called_once_with(mock_graph)