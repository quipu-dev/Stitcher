import json
from stitcher.refactor.types import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_file_across_packages_migrates_lock_entry(tmp_path):
    """
    Verifies that moving a file across packages correctly migrates its
    fingerprint entry from the source package's stitcher.lock to the
    destination's.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    py_rel_path_a = "packages/pkg-a/src/pkga/core.py"
    old_suri = f"py://{py_rel_path_a}#SharedClass"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "abc"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject("packages/pkg-a")
        .with_source("packages/pkg-a/src/pkga/__init__.py", "")
        .with_source("packages/pkg-a/src/pkga/core.py", "class SharedClass: pass")
        .with_raw_file("packages/pkg-a/stitcher.lock", lock_content)
        .with_pyproject("packages/pkg-b")
        .with_source("packages/pkg-b/src/pkgb/__init__.py", "")
        .build()
    )

    src_path = project_root / py_rel_path_a
    dest_path = project_root / "packages/pkg-b/src/pkgb/core.py"
    src_lock_path = project_root / "packages/pkg-a/stitcher.lock"
    dest_lock_path = project_root / "packages/pkg-b/stitcher.lock"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("pkga")
    graph.load("pkgb")

    sidecar_manager = SidecarManager(root_path=project_root)
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

    op = MoveFileOperation(src_path, dest_path)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    assert not src_path.exists(), "Source file should have been moved"
    assert dest_path.exists(), "Destination file should exist"

    # Assert source lock file is updated (or empty)
    src_lock_data = json.loads(src_lock_path.read_text())["fingerprints"]
    assert old_suri not in src_lock_data, "Old SURI should be removed from source lock"

    # Assert destination lock file is created and contains the migrated entry
    assert dest_lock_path.exists(), "Destination stitcher.lock should be created"
    dest_lock_data = json.loads(dest_lock_path.read_text())["fingerprints"]
    py_rel_path_b = "packages/pkg-b/src/pkgb/core.py"
    expected_new_suri = f"py://{py_rel_path_b}#SharedClass"
    assert expected_new_suri in dest_lock_data, (
        "New SURI should be present in destination lock"
    )
    assert dest_lock_data[expected_new_suri] == {
        "baseline_code_structure_hash": "abc"
    }, "Fingerprint data should be preserved"
