from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.test_utils import WorkspaceFactory


def test_rename_symbol_via_attribute_access(tmp_path):
    # 1. Setup
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source(
            "main.py",
            """
            import mypkg.core

            h = mypkg.core.OldHelper()
            """,
        )
        .build()
    )

    # 2. Analyze
    graph = SemanticGraph(root_path=project_root)
    graph.load("mypkg")
    graph.load("main")
    ctx = RefactorContext(graph=graph)

    # 3. Plan
    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    ops = op.analyze(ctx)

    # 4. Verify (without committing, just check the planned ops)
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops}
    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content


def test_rename_symbol_imported_with_alias(tmp_path):
    # 1. Setup
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source(
            "main.py",
            """
            from mypkg.core import OldHelper as OH

            h = OH()
            """,
        )
        .build()
    )

    # 2. Analyze
    graph = SemanticGraph(root_path=project_root)
    graph.load("mypkg")
    graph.load("main")
    ctx = RefactorContext(graph=graph)

    # 3. Plan
    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    ops = op.analyze(ctx)

    # 4. Verify
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops}
    expected_main = "from mypkg.core import NewHelper as OH\n\nh = OH()"
    assert "core.py" in write_ops
    assert write_ops["core.py"].content == "class NewHelper: pass"
    assert "main.py" in write_ops
    assert write_ops["main.py"].content.strip() == expected_main.strip()
