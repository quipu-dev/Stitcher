from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


import yaml
import json


def test_rename_symbol_end_to_end(tmp_path):
    # 1. Setup: Use WorkspaceFactory to declaratively build the project
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/core.py"
    old_helper_suri = f"py://{py_rel_path}#OldHelper"
    old_func_suri = f"py://{py_rel_path}#old_func"
    new_helper_suri = f"py://{py_rel_path}#NewHelper"

    project_root = (
        factory.with_pyproject(".")
        .with_source(
            "mypkg/core.py",
            """
        class OldHelper:
            pass

        def old_func():
            pass
        """,
        )
        .with_source(
            "mypkg/app.py",
            """
        from .core import OldHelper, old_func

        h = OldHelper()
        old_func()
        """,
        )
        .with_source("mypkg/__init__.py", "")
        .with_docs(
            "mypkg/core.stitcher.yaml",
            # Keys are Fragments
            {
                "OldHelper": "This is the old helper.",
                "old_func": "This is an old function.",
            },
        )
        .with_raw_file(
            ".stitcher/signatures/mypkg/core.json",
            # Keys are SURIs
            json.dumps(
                {
                    old_helper_suri: {"baseline_code_structure_hash": "hash1"},
                    old_func_suri: {"baseline_code_structure_hash": "hash2"},
                }
            ),
        )
        .build()
    )

    core_path = project_root / "mypkg/core.py"
    app_path = project_root / "mypkg/app.py"
    doc_path = project_root / "mypkg/core.stitcher.yaml"
    sig_path = project_root / ".stitcher/signatures/mypkg/core.json"

    # 2. Analysis Phase
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    # 3. Planning Phase
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        old_fqn="mypkg.core.OldHelper", new_fqn="mypkg.core.NewHelper"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    # 4. Execution Phase
    tm = TransactionManager(project_root)
    for op in file_ops:
        # In a real app, we might add ops one by one. Here we add all.
        # This assumes analyze() returns WriteFileOp with correct content.
        if isinstance(op, WriteFileOp):
            tm.add_write(op.path, op.content)

    tm.commit()

    # 5. Verification Phase
    # Check the file where the definition was
    modified_core_code = core_path.read_text(encoding="utf-8")
    assert "class NewHelper:" in modified_core_code
    assert "class OldHelper:" not in modified_core_code

    # Check the file where it was used
    modified_app_code = app_path.read_text(encoding="utf-8")
    assert "from .core import NewHelper, old_func" in modified_app_code
    assert "h = NewHelper()" in modified_app_code

    # Check sidecar files
    modified_doc_data = yaml.safe_load(doc_path.read_text("utf-8"))
    assert "NewHelper" in modified_doc_data
    assert "OldHelper" not in modified_doc_data
    assert modified_doc_data["NewHelper"] == "This is the old helper."

    modified_sig_data = json.loads(sig_path.read_text("utf-8"))
    assert new_helper_suri in modified_sig_data
    assert old_helper_suri not in modified_sig_data
    assert modified_sig_data[new_helper_suri]["baseline_code_structure_hash"] == "hash1"
