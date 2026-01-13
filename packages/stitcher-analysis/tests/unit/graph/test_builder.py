from unittest.mock import MagicMock
import networkx as nx

from stitcher.spec.index import FileRecord, DependencyEdge, SymbolRecord
from stitcher.analysis.graph.builder import GraphBuilder


def test_build_dependency_graph_simple():
    # 1. Arrange: Setup mock store and data
    mock_store = MagicMock()

    mock_files = [
        FileRecord(
            id=1,
            path="src/a.py",
            content_hash="a",
            last_mtime=1,
            last_size=1,
            indexing_status=1,
        ),
        FileRecord(
            id=2,
            path="src/b.py",
            content_hash="b",
            last_mtime=1,
            last_size=1,
            indexing_status=1,
        ),
    ]
    mock_store.get_all_files.return_value = mock_files

    mock_edges = [
        DependencyEdge(
            source_path="src/a.py",
            target_fqn="b_module.some_func",
            kind="import",
            lineno=1,
        ),
    ]
    mock_store.get_all_dependency_edges.return_value = mock_edges

    def mock_find_symbol(fqn):
        symbol_rec = SymbolRecord(
            id=fqn,
            name="",
            kind="",
            lineno=1,
            col_offset=0,
            end_lineno=1,
            end_col_offset=0,
        )
        if fqn.startswith("b_module"):
            return (symbol_rec, "src/b.py")
        return None

    mock_store.find_symbol_by_fqn.side_effect = mock_find_symbol

    # 2. Act: Build the graph
    builder = GraphBuilder()
    graph = builder.build_dependency_graph(mock_store)

    # 3. Assert: Verify the graph structure
    assert isinstance(graph, nx.DiGraph)
    assert set(graph.nodes) == {"src/a.py", "src/b.py"}
    assert graph.has_edge("src/a.py", "src/b.py")


def test_build_dependency_graph_resolves_init_aliases_correctly():
    """
    This is the regression test for the __init__.py barrel export issue.

    It simulates the following structure:
    - app.py:        `from my_pkg import my_func`
    - my_pkg/__init__.py: `from .logic import my_func`
    - my_pkg/logic.py:  `def my_func(): ...`

    The graph edge should be `app.py -> my_pkg/logic.py`, NOT `app.py -> my_pkg/__init__.py`.
    """
    # 1. Arrange
    mock_store = MagicMock()

    # Define the files in our simulated project
    mock_files = [
        FileRecord(
            id=1,
            path="app.py",
            content_hash="a",
            last_mtime=1,
            last_size=1,
            indexing_status=1,
        ),
        FileRecord(
            id=2,
            path="my_pkg/__init__.py",
            content_hash="b",
            last_mtime=1,
            last_size=1,
            indexing_status=1,
        ),
        FileRecord(
            id=3,
            path="my_pkg/logic.py",
            content_hash="c",
            last_mtime=1,
            last_size=1,
            indexing_status=1,
        ),
    ]
    mock_store.get_all_files.return_value = mock_files

    # Define the import relationships
    mock_edges = [
        # app.py imports the aliased symbol from the package
        DependencyEdge(
            source_path="app.py", target_fqn="my_pkg.my_func", kind="import", lineno=1
        ),
        # __init__.py creates the alias by importing from the logic module
        DependencyEdge(
            source_path="my_pkg/__init__.py",
            target_fqn="my_pkg.logic.my_func",
            kind="import",
            lineno=1,
        ),
    ]
    mock_store.get_all_dependency_edges.return_value = mock_edges

    # Define the symbols and how to find them
    # This is the REAL function definition
    func_symbol = SymbolRecord(
        id="...",
        name="my_func",
        kind="function",
        lineno=1,
        col_offset=0,
        end_lineno=1,
        end_col_offset=0,
        canonical_fqn="my_pkg.logic.my_func",
    )
    # This is the ALIAS created in __init__.py
    alias_symbol = SymbolRecord(
        id="...",
        name="my_func",
        kind="alias",
        lineno=1,
        col_offset=0,
        end_lineno=1,
        end_col_offset=0,
        canonical_fqn="my_pkg.my_func",
        alias_target_fqn="my_pkg.logic.my_func",  # Critical link
    )

    symbol_map = {
        "my_pkg.my_func": (alias_symbol, "my_pkg/__init__.py"),
        "my_pkg.logic.my_func": (func_symbol, "my_pkg/logic.py"),
    }
    mock_store.find_symbol_by_fqn.side_effect = lambda fqn: symbol_map.get(fqn)

    # 2. Act
    builder = GraphBuilder()
    graph = builder.build_dependency_graph(mock_store)

    # 3. Assert
    # The graph must connect app.py to the *real* source file, not the __init__
    assert graph.has_edge("app.py", "my_pkg/logic.py"), (
        "Graph should link consumer to the canonical source of the symbol."
    )

    # The incorrect edge must NOT exist
    assert not graph.has_edge("app.py", "my_pkg/__init__.py"), (
        "Graph should NOT link consumer to the __init__.py alias."
    )

    # The internal dependency from __init__ to logic should still exist
    assert graph.has_edge("my_pkg/__init__.py", "my_pkg/logic.py"), (
        "The internal dependency from __init__ to its implementation module should be preserved."
    )
