from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.test_utils import WorkspaceFactory


import yaml
import json


def test_rename_symbol_end_to_end(tmp_path):
    # 1. Setup: Use WorkspaceFactory to declaratively build the project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_source(
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
            {
                "mypkg.core.OldHelper": "This is the old helper.",
                "mypkg.core.old_func": "This is an old function.",
            },
        )
        .with_raw_file(
            ".stitcher/signatures/mypkg/core.json",
            json.dumps(
                {
                    "mypkg.core.OldHelper": {"baseline_code_structure_hash": "hash1"},
                    "mypkg.core.old_func": {"baseline_code_structure_hash": "hash2"},
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
    graph = SemanticGraph(root_path=project_root)
    graph.load("mypkg")
    ctx = RefactorContext(graph=graph)

    # 3. Planning Phase
    op = RenameSymbolOperation(
        old_fqn="mypkg.core.OldHelper", new_fqn="mypkg.core.NewHelper"
    )
    file_ops = op.analyze(ctx)

    # 4. Execution Phase
    tm = TransactionManager(project_root)
    for op in file_ops:
        # In a real app, we might add ops one by one. Here we add all.
        # This assumes analyze() returns WriteFileOp with correct content.
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
    assert "mypkg.core.NewHelper" in modified_doc_data
    assert "mypkg.core.OldHelper" not in modified_doc_data
    assert modified_doc_data["mypkg.core.NewHelper"] == "This is the old helper."

    modified_sig_data = json.loads(sig_path.read_text("utf-8"))
    assert "mypkg.core.NewHelper" in modified_sig_data
    assert "mypkg.core.OldHelper" not in modified_sig_data
    assert (
        modified_sig_data["mypkg.core.NewHelper"]["baseline_code_structure_hash"]
        == "hash1"
    )
