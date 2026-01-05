from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_semantic_graph_get_module_nested_lookup(tmp_path):
    """
    Verifies that get_module can navigate the module tree to find submodules.
    """
    # 1. ARRANGE: Create a nested package structure
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/utils/__init__.py", "")
        .with_source("mypkg/utils/math.py", "def add(a, b): return a + b")
        .build()
    )

    # 2. ACT
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("mypkg")

    # 3. ASSERT
    # Test successful lookup of a nested module
    nested_module = graph.get_module("mypkg.utils.math")
    assert nested_module is not None
    assert nested_module.path == "mypkg.utils.math"
    assert "add" in nested_module.members

    # Test successful lookup of an intermediate package
    intermediate_pkg = graph.get_module("mypkg.utils")
    assert intermediate_pkg is not None
    assert intermediate_pkg.path == "mypkg.utils"

    # Test lookup of the top-level package
    top_level_pkg = graph.get_module("mypkg")
    assert top_level_pkg is not None
    assert top_level_pkg.path == "mypkg"

    # Test unsuccessful lookup
    non_existent_module = graph.get_module("mypkg.utils.nonexistent")
    assert non_existent_module is None

    non_existent_top_level = graph.get_module("nonexistent")
    assert non_existent_top_level is None