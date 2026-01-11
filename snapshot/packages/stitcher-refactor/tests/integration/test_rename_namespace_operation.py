from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_populated_index

from stitcher.refactor.engine import (
    RefactorContext,
    SemanticGraph,
)
from stitcher.refactor.operations.rename_namespace import RenameNamespaceOperation
from stitcher.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager


def test_rename_namespace_operation_fails_as_expected(workspace_factory: WorkspaceFactory):
    """
    This test is designed to FAIL.
    It specifically targets the `analyze` method of `RenameNamespaceOperation`
    to confirm it hits the `AttributeError` due to the incorrect use of `ctx.graph.registry`.
    """
    # 1. Setup a workspace
    ws = (
        workspace_factory.with_project_name("my-project")
        .with_config({"scan_paths": ["src"]})
        .with_source(
            "src/my_pkg/utils/helpers.py",
            """
            def helper_func():
                return 1
            """,
        )
        .with_source(
            "src/my_pkg/main.py",
            """
            from my_pkg.utils.helpers import helper_func
            
            def main():
                return helper_func()
            """,
        )
        .with_raw_file("src/my_pkg/__init__.py", "")
        .with_raw_file("src/my_pkg/utils/__init__.py", "")
    )
    root_path = ws.build()

    # 2. Setup Refactor Context
    workspace = Workspace(root_path)
    index_store = create_populated_index(root_path)
    graph = SemanticGraph(workspace, index_store)
    graph.load_from_workspace()
    sidecar_manager = SidecarManager(root_path)
    ctx = RefactorContext(workspace, graph, sidecar_manager, index_store)

    # 3. Define the operation
    op = RenameNamespaceOperation(old_prefix="my_pkg.utils", new_prefix="my_pkg.tools")

    # 4. Execute the faulty method
    # This call is expected to raise an AttributeError.
    op.analyze(ctx)
