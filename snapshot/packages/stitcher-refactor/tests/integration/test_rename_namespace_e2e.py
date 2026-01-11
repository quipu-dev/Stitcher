from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.operations.rename_namespace import RenameNamespaceOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_namespace_operation_triggers_known_bug(tmp_path):
    """
    This test is designed to fail by triggering the AttributeError in
    RenameNamespaceOperation, which incorrectly calls a non-existent
    `graph.registry` attribute.
    """
    # 1. ARRANGE: Create a project with a nested namespace
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/old_ns/__init__.py", "")
        .with_source("mypkg/old_ns/module.py", "class MyClass: pass")
        .with_source(
            "app.py", "from mypkg.old_ns.module import MyClass\n\nc = MyClass()"
        )
        .build()
    )

    # 2. SETUP CONTEXT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("app")

    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    # 3. ACT & ASSERT (This call is expected to raise AttributeError)
    op = RenameNamespaceOperation(
        old_prefix="mypkg.old_ns", new_prefix="mypkg.new_ns"
    )

    try:
        # This line contains the buggy call `ctx.graph.registry.get_usages`
        # and is expected to raise an AttributeError.
        op.analyze(ctx)
    except AttributeError as e:
        # This is the expected failure. We can assert the error message
        # to be more specific about the bug we've caught.
        assert "'SemanticGraph' object has no attribute 'registry'" in str(e)
        # We return here to make the test pass *only* if the expected bug is triggered.
        # This way, when the bug is fixed, the test will fail, prompting us to
        # update it with proper assertions.
        return

    # If the AttributeError was NOT raised, the bug has been fixed or masked.
    # Fail the test to indicate that this test case needs to be updated.
    assert False, (
        "Expected AttributeError was not raised. The bug might be fixed. "
        "Update this test to verify the correct behavior."
    )
