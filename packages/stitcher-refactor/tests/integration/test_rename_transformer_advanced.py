from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation


def test_rename_symbol_via_attribute_access(tmp_path):
    # 1. Setup: main.py imports a package and uses attribute access
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "core.py").write_text("class OldHelper: pass", encoding="utf-8")

    main_path = tmp_path / "main.py"
    main_path.write_text(
        "import mypkg.core\n\nh = mypkg.core.OldHelper()", encoding="utf-8"
    )

    # 2. Analyze
    # We must add tmp_path to search_paths for Griffe to find `mypkg` from `main.py`
    graph = SemanticGraph(root_path=tmp_path)
    # Load both the package and the standalone module that uses it
    graph.load("mypkg")
    graph.load("main")
    ctx = RefactorContext(graph=graph)

    # 3. Plan
    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    ops = op.analyze(ctx)

    # 4. Apply (simulated via direct code modification for test simplicity)
    assert len(ops) == 2  # Expect changes in core.py and main.py

    write_ops = {op.path.name: op for op in ops}

    # 5. Verify
    expected_core = "class NewHelper: pass"
    expected_main = "import mypkg.core\n\nh = mypkg.core.NewHelper()"

    assert "core.py" in write_ops
    assert write_ops["core.py"].content == expected_core

    assert "main.py" in write_ops
    assert write_ops["main.py"].content == expected_main


def test_rename_symbol_imported_with_alias(tmp_path):
    # 1. Setup: main.py imports a class with an alias
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "core.py").write_text("class OldHelper: pass", encoding="utf-8")

    main_path = tmp_path / "main.py"
    main_path.write_text(
        "from mypkg.core import OldHelper as OH\n\nh = OH()", encoding="utf-8"
    )

    # 2. Analyze
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")
    graph.load("main")
    ctx = RefactorContext(graph=graph)

    # 3. Plan
    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    ops = op.analyze(ctx)

    # 4. Verify
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops}

    expected_core = "class NewHelper: pass"
    # CRITICAL: The alias 'OH' is preserved, only the source name 'OldHelper' changes.
    expected_main = "from mypkg.core import NewHelper as OH\n\nh = OH()"

    assert "core.py" in write_ops
    assert write_ops["core.py"].content == expected_core

    assert "main.py" in write_ops
    assert write_ops["main.py"].content == expected_main
