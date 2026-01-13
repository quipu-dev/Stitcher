import json
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_rename_symbol_updates_suri_in_lockfile(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    rel_py_path = "src/mypkg/core.py"
    old_suri = f"py://{rel_py_path}#MyClass"
    new_suri = f"py://{rel_py_path}#YourClass"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict(
            {"baseline_code_structure_hash": "original_hash"}
        )
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("src/mypkg/__init__.py", "")
        .with_source(rel_py_path, "class MyClass: pass")
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )
    lock_path = project_root / "stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    sidecar_manager = SidecarManager(root_path=project_root)

    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.MyClass", "mypkg.core.YourClass")
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    updated_data = json.loads(lock_path.read_text(encoding="utf-8"))["fingerprints"]
    assert old_suri not in updated_data
    assert new_suri in updated_data
    assert updated_data[new_suri]["baseline_code_structure_hash"] == "original_hash"


def test_rename_nested_method_updates_suri_fragment(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    rel_py_path = "src/mypkg/logic.py"
    old_suri = f"py://{rel_py_path}#MyClass.old_method"
    new_suri = f"py://{rel_py_path}#MyClass.new_method"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "123"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source(rel_py_path, "class MyClass:\n    def old_method(self): pass")
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )
    lock_path = project_root / "stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "mypkg.logic.MyClass.old_method", "mypkg.logic.MyClass.new_method"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    updated_data = json.loads(lock_path.read_text())["fingerprints"]
    assert old_suri not in updated_data
    assert new_suri in updated_data
    assert updated_data[new_suri]["baseline_code_structure_hash"] == "123"
