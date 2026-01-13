from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint

import json


def test_rename_symbol_end_to_end(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/core.py"
    old_helper_suri = f"py://{py_rel_path}#OldHelper"
    old_func_suri = f"py://{py_rel_path}#old_func"
    new_helper_suri = f"py://{py_rel_path}#NewHelper"

    lock_manager = LockFileManager()
    fingerprints = {
        old_helper_suri: Fingerprint.from_dict(
            {"baseline_code_structure_hash": "hash1"}
        ),
        old_func_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "hash2"}),
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source(
            "mypkg/core.py",
            "class OldHelper: pass\ndef old_func(): pass",
        )
        .with_source(
            "mypkg/app.py",
            "from .core import OldHelper, old_func\nh = OldHelper()\nold_func()",
        )
        .with_source("mypkg/__init__.py", "")
        .with_docs("mypkg/core.stitcher.yaml", {"OldHelper": "doc", "old_func": "doc"})
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )

    core_path = project_root / "mypkg/core.py"
    app_path = project_root / "mypkg/app.py"
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
        uri_generator=PythonURIGenerator(),
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for op in file_ops:
        if isinstance(op, WriteFileOp):
            tm.add_write(op.path, op.content)
    tm.commit()

    assert "class NewHelper:" in core_path.read_text(encoding="utf-8")
    assert "from .core import NewHelper, old_func" in app_path.read_text(
        encoding="utf-8"
    )

    modified_lock_data = json.loads(lock_path.read_text("utf-8"))["fingerprints"]
    assert new_helper_suri in modified_lock_data
    assert old_helper_suri not in modified_lock_data
    assert (
        modified_lock_data[new_helper_suri]["baseline_code_structure_hash"] == "hash1"
    )
    assert old_func_suri in modified_lock_data  # Ensure other keys are untouched
