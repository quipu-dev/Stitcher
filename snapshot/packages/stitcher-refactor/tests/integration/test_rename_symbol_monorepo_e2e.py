import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_rename_symbol_in_monorepo_updates_all_references_and_sidecars(tmp_path):
    # 1. ARRANGE: Build a monorepo with cross-package and test references
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")  # For top-level integration tests
        # --- Package A: Defines the symbol ---
        .with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class OldNameClass: pass")
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml",
            {"pkga_lib.core.OldNameClass": "Docs for the old class."},
        )
        .with_raw_file(
            ".stitcher/signatures/packages/pkg_a/src/pkga_lib/core.json",
            json.dumps({"pkga_lib.core.OldNameClass": {"hash": "abc"}}),
        )
        .with_source(
            "packages/pkg_a/tests/test_core.py",
            "from pkga_lib.core import OldNameClass\n\ndef test_local():\n    assert OldNameClass is not None",
        )
        # --- Package B: Consumes the symbol ---
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import OldNameClass\n\ninstance = OldNameClass()",
        )
        # --- Top-level integration test: Also consumes the symbol ---
        .with_source("tests/integration/__init__.py", "")
        .with_source(
            "tests/integration/test_system.py",
            "from pkga_lib.core import OldNameClass\n\ndef test_system_integration():\n    assert OldNameClass",
        )
        .build()
    )

    # Define paths for verification
    definition_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    pkg_a_test_path = project_root / "packages/pkg_a/tests/test_core.py"
    pkg_b_main_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"
    top_level_test_path = project_root / "tests/integration/test_system.py"
    doc_path = definition_path.with_suffix(".stitcher.yaml")
    sig_path = (
        project_root / ".stitcher/signatures/packages/pkg_a/src/pkga_lib/core.json"
    )

    # 2. ACT
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    graph.load("test_core")
    graph.load("integration")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )

    op = RenameSymbolOperation(
        "pkga_lib.core.OldNameClass", "pkga_lib.core.NewNameClass"
    )
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    # --- Code Files ---
    expected_import = "from pkga_lib.core import NewNameClass"
    assert "class NewNameClass: pass" in definition_path.read_text()
    assert expected_import in pkg_a_test_path.read_text()
    assert expected_import in pkg_b_main_path.read_text()
    assert expected_import in top_level_test_path.read_text()

    # --- Sidecar Files ---
    new_fqn = "pkga_lib.core.NewNameClass"
    old_fqn = "pkga_lib.core.OldNameClass"

    # YAML Doc file
    doc_data = yaml.safe_load(doc_path.read_text())
    assert new_fqn in doc_data
    assert old_fqn not in doc_data
    assert doc_data[new_fqn] == "Docs for the old class."

    # JSON Signature file
    sig_data = json.loads(sig_path.read_text())
    assert new_fqn in sig_data
    assert old_fqn not in sig_data
    assert sig_data[new_fqn] == {"hash": "abc"}
