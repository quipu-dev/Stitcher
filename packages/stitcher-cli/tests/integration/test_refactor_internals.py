from pathlib import Path

from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.workspace import load_config_from_path
from stitcher.workspace import Workspace
from stitcher.refactor.engine import SemanticGraph


def test_graph_can_find_symbol_after_workspace_refactor(tmp_path: Path):
    """
    Diagnostic test to verify that the refactored Workspace correctly
    configures the SemanticGraph to find symbols and their usages.
    """
    # 1. Arrange: Create a project with the same structure as the failing e2e test
    factory = WorkspaceFactory(tmp_path)
    (
        factory.with_project_name("mypkg")
        .with_config({"scan_paths": ["src"]})
        .with_source("src/mypkg/__init__.py", "")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old\n\nvar = Old()")
    ).build()

    # 2. Act: Manually instantiate the core components, bypassing the CLI runner
    configs, _ = load_config_from_path(tmp_path)
    assert configs, "Config should be loaded"
    config = configs[0]

    # Create and populate index
    index_store = create_populated_index(tmp_path)

    workspace = Workspace(root_path=tmp_path, config=config)
    graph = SemanticGraph(workspace, index_store)

    # The key action performed by RefactorRunner
    pkg_names = list(workspace.import_to_source_dirs.keys())
    assert "mypkg" in pkg_names, "Workspace should discover 'mypkg'"

    for pkg_name in pkg_names:
        graph.load(pkg_name)

    # 3. Assert: Check the internal state of the SemanticGraph's usage discovery
    # Assert that the definition of the class itself is found and registered as a "usage"
    usages_of_definition = [
        u for u in graph.find_usages("mypkg.core.Old") if u.file_path.name == "core.py"
    ]
    assert len(usages_of_definition) > 0, (
        "Graph should find the definition of mypkg.core.Old"
    )

    # Assert that the usage in another file is found
    usages_in_app = [
        u for u in graph.find_usages("mypkg.core.Old") if u.file_path.name == "app.py"
    ]
    assert len(usages_in_app) > 0, (
        "Graph should find the usage of mypkg.core.Old in app.py"
    )
