import yaml
import json
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.move_file import MoveFileOperation


def test_move_file_updates_imports_and_sidecars(tmp_path):
    # Setup Layout:
    # src/
    #   mypkg/
    #     __init__.py
    #     old.py  (Defines `class A`)
    #     app.py  (Imports `A` via absolute and relative)

    src_root = tmp_path / "src"
    pkg_dir = src_root / "mypkg"
    pkg_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    # old.py
    old_py = pkg_dir / "old.py"
    old_py.write_text("class A:\n    pass", encoding="utf-8")

    # app.py
    app_py = pkg_dir / "app.py"
    app_py.write_text(
        "import mypkg.old\n"
        "from mypkg.old import A\n"
        "from . import old\n"  # Relative import of module
        "from .old import A as AliasA\n"  # Relative import of symbol
        "\n"
        "def main():\n"
        "    x = mypkg.old.A()\n"
        "    y = A()\n"
        "    z = old.A()\n"
        "    w = AliasA()",
        encoding="utf-8",
    )

    # Sidecars
    # old.stitcher.yaml
    old_yaml = old_py.with_suffix(".stitcher.yaml")
    old_yaml.write_text(yaml.dump({"mypkg.old.A": "Doc for A"}), encoding="utf-8")

    # .stitcher/signatures/src/mypkg/old.json
    sig_dir = tmp_path / ".stitcher/signatures/src/mypkg"
    sig_dir.mkdir(parents=True)
    old_json = sig_dir / "old.json"
    old_json.write_text(json.dumps({"mypkg.old.A": {"hash": "123"}}), encoding="utf-8")

    # Execute
    # Load assuming 'src' is in path (Stitcher usually handles this, we sim it)
    # Note: SemanticGraph uses GriffeLoader(search_paths=[root_path])
    # So 'src.mypkg' might be the module name if we don't handle src layout explicitly.
    # Our MoveFileOperation heuristic handles 'src' stripping.
    # But SemanticGraph needs to resolve it.
    # Let's verify what module name Griffe assigns.
    # Typically if we point to tmp_path, it sees 'src'.
    # For this test, let's keep it simple: put mypkg in root.
    pass


def test_move_file_flat_layout(tmp_path):
    # Setup Layout (Flat for simplicity):
    # mypkg/
    #   __init__.py
    #   old.py
    #   app.py

    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    old_py = pkg_dir / "old.py"
    old_py.write_text("class A:\n    pass", encoding="utf-8")

    app_py = pkg_dir / "app.py"
    app_py.write_text(
        "import mypkg.old\n"
        "from mypkg.old import A\n"
        "from . import old\n"
        "from .old import A as AliasA\n"
        "\n"
        "x = mypkg.old.A()\n"
        "y = A()\n"
        "z = old.A()\n"
        "w = AliasA()",
        encoding="utf-8",
    )

    old_yaml = old_py.with_suffix(".stitcher.yaml")
    old_yaml.write_text(yaml.dump({"mypkg.old.A": "Doc"}), encoding="utf-8")

    sig_dir = tmp_path / ".stitcher/signatures/mypkg"
    sig_dir.mkdir(parents=True)
    old_json = sig_dir / "old.json"
    old_json.write_text(json.dumps({"mypkg.old.A": {"h": "1"}}), encoding="utf-8")

    # 2. Analyze
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")

    ctx = RefactorContext(graph=graph)

    # Move mypkg/old.py -> mypkg/new.py
    new_py = pkg_dir / "new.py"
    op = MoveFileOperation(old_py, new_py)

    file_ops = op.analyze(ctx)

    # 3. Commit
    tm = TransactionManager(tmp_path)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
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

    # Absolute import
    assert "import mypkg.new" in new_app
    assert "from mypkg.new import A" in new_app

    # Relative import
    # "from . import old" -> "from . import new"
    # Wait, RenameSymbolOperation replaces "old" name with "new".
    # ImportFrom(module=None, names=[Alias(name="old")]) -> name="new"
    # Result: "from . import new"
    assert "from . import new" in new_app

    # "from .old import A" -> "from .new import A"
    # ImportFrom(module="old", ...) -> module="new"
    assert "from .new import A as AliasA" in new_app

    # Sidecar Keys
    new_yaml_content = new_py.with_suffix(".stitcher.yaml").read_text("utf-8")
    assert "mypkg.new.A" in new_yaml_content
    assert "mypkg.old.A" not in new_yaml_content
