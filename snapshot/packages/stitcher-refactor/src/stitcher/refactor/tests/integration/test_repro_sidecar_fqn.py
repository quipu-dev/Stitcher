import yaml
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_repro_sidecar_keys_should_remain_short_names_after_directory_move(tmp_path):
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/section/__init__.py", "")
        .with_source("mypkg/section/core.py", "class MyClass:\n    pass")
        .with_docs(
            "mypkg/section/core.stitcher.yaml",
            {"MyClass": "Class doc"},
        )
        .build()
    )

    src_dir = project_root / "mypkg/section"
    dest_dir = project_root / "mypkg/moved_section"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    # Load top level to ensure graph coverage
    graph.load("mypkg")

    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
        uri_generator=PythonURIGenerator(),
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveDirectoryOperation(src_dir, dest_dir)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    # The file should now be at mypkg/moved_section/core.stitcher.yaml
    new_yaml_path = dest_dir / "core.stitcher.yaml"
    assert new_yaml_path.exists(), "Sidecar file was not moved correctly!"

    data = yaml.safe_load(new_yaml_path.read_text())

    print(f"\n[DEBUG] Keys in new sidecar: {list(data.keys())}")

    # Assert Short Name retention
    # This assertion is expected to FAIL if the bug is present.
    # It will likely contain "mypkg.moved_section.core.MyClass" instead.
    assert "MyClass" in data, (
        f"Short name 'MyClass' missing. Found keys: {list(data.keys())}"
    )
