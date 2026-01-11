import json
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_move_file_flat_layout(tmp_path):
    # 1. Arrange: Declaratively build the project structure
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/old.py", "class A:\n    pass")
        .with_source(
            "mypkg/app.py",
            """
            import mypkg.old
            from mypkg.old import A
            from . import old
            from .old import A as AliasA

            x = mypkg.old.A()
            y = A()
            z = old.A()
            w = AliasA()
            """,
        )
        .with_docs("mypkg/old.stitcher.yaml", {"mypkg.old.A": "Doc"})
        .with_raw_file(
            ".stitcher/signatures/mypkg/old.json",
            json.dumps({"mypkg.old.A": {"h": "1"}}),
        )
        .build()
    )

    pkg_dir = project_root / "mypkg"
    old_py = pkg_dir / "old.py"
    app_py = pkg_dir / "app.py"
    old_yaml = old_py.with_suffix(".stitcher.yaml")
    sig_dir = project_root / ".stitcher/signatures/mypkg"
    old_json = sig_dir / "old.json"
    new_py = pkg_dir / "new.py"

    # 2. Analyze
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
    )
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveFileOperation(old_py, new_py)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    # 3. Commit
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. Verify
    # Files moved?
    assert not old_py.exists()
    assert new_py.exists()
    assert not old_yaml.exists()
    assert new_py.with_suffix(".stitcher.yaml").exists()
    assert not old_json.exists()
    assert (sig_dir / "new.json").exists()

    # Content updated?
    new_app = app_py.read_text("utf-8")
    assert "import mypkg.new" in new_app
    assert "from mypkg.new import A" in new_app
    assert "from . import new" in new_app
    # Note: Stitcher now converts relative imports with a module part to absolute imports for robustness
    assert "from mypkg.new import A as AliasA" in new_app

    # Sidecar Keys
    new_yaml_content = new_py.with_suffix(".stitcher.yaml").read_text("utf-8")
    assert "mypkg.new.A" in new_yaml_content
    assert "mypkg.old.A" not in new_yaml_content
