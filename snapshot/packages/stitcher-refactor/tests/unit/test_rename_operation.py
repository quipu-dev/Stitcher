from unittest.mock import Mock
from pathlib import Path
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import (
    SemanticGraph,
    UsageRegistry,
    UsageLocation,
    SymbolNode,
)
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.transaction import WriteFileOp
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace


def test_rename_symbol_analyze_orchestration():
    # 1. Setup Mocks
    mock_registry = Mock(spec=UsageRegistry)
    mock_graph = Mock(spec=SemanticGraph)
    mock_graph.registry = mock_registry

    tmp_path = Path("/tmp/fake_project")  # conceptual
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    mock_workspace = Mock(spec=Workspace)
    mock_sidecar_manager = Mock(spec=SidecarManager)
    mock_sidecar_manager.get_doc_path.return_value.exists.return_value = False
    mock_sidecar_manager.get_signature_path.return_value.exists.return_value = False

    ctx = RefactorContext(
        graph=mock_graph,
        workspace=mock_workspace,
        sidecar_manager=mock_sidecar_manager,
    )

    # 2. Define Test Data
    old_fqn = "mypkg.core.OldHelper"
    new_fqn = "mypkg.core.NewHelper"

    file_a_path = tmp_path / "mypkg" / "a.py"
    file_b_path = tmp_path / "mypkg" / "b.py"

    source_a = "from mypkg.core import OldHelper\n\nobj = OldHelper()"
    source_b = "def func():\n    from mypkg.core import OldHelper\n    return OldHelper"

    from stitcher.refactor.engine.graph import ReferenceType

    locations = [
        UsageLocation(
            file_a_path,
            1,
            23,
            1,
            32,
            ReferenceType.IMPORT_PATH,
            "mypkg.core.OldHelper",
        ),
        UsageLocation(
            file_a_path, 3, 6, 3, 15, ReferenceType.SYMBOL, "mypkg.core.OldHelper"
        ),
        UsageLocation(
            file_b_path,
            2,
            27,
            2,
            36,
            ReferenceType.IMPORT_PATH,
            "mypkg.core.OldHelper",
        ),
        UsageLocation(
            file_b_path,
            3,
            11,
            3,
            20,
            ReferenceType.SYMBOL,
            "mypkg.core.OldHelper",
        ),
    ]

    mock_registry.get_usages.return_value = locations

    # Configure the mock graph for the _find_definition_node logic
    mock_graph._modules = {"mypkg": Mock()}
    mock_definition_node = Mock(spec=SymbolNode)
    mock_definition_node.fqn = old_fqn
    mock_definition_node.path = file_a_path  # Assume definition is in file_a
    mock_graph.iter_members.return_value = [mock_definition_node]

    # Mock file system reads
    def mock_read_text(path, *args, **kwargs):
        if path == file_a_path:
            return source_a
        if path == file_b_path:
            return source_b
        raise FileNotFoundError(f"Mock read_text: {path}")

    from unittest.mock import patch

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    with patch.object(Path, "read_text", side_effect=mock_read_text, autospec=True):
        # 3. Execute
        op = RenameSymbolOperation(old_fqn, new_fqn)
        spec = MigrationSpec().add(op)
        planner = Planner()
        file_ops = planner.plan(spec, ctx)

    # 4. Verify
    # The planner will get usages for the old_fqn and potentially its prefixes.
    # We can check that it was called with the specific FQN.
    mock_registry.get_usages.assert_any_call(old_fqn)

    # We expect 2 code change ops + potentially sidecar ops
    # Since we mocked .exists() to False, we expect only the 2 code ops.
    assert len(file_ops) == 2
    # Ensure type narrowing
    write_ops = [op for op in file_ops if isinstance(op, WriteFileOp)]
    assert len(write_ops) == 2

    op_a = next(op for op in write_ops if op.path == file_a_path.relative_to(tmp_path))
    op_b = next(op for op in write_ops if op.path == file_b_path.relative_to(tmp_path))

    expected_code_a = "from mypkg.core import NewHelper\n\nobj = NewHelper()"
    expected_code_b = (
        "def func():\n    from mypkg.core import NewHelper\n    return NewHelper"
    )

    assert op_a.content == expected_code_a
    assert op_b.content == expected_code_b
