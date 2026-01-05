from unittest.mock import Mock
from pathlib import Path
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph, UsageRegistry, UsageLocation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.transaction import WriteFileOp
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace


def test_rename_symbol_analyze_orchestration():
    # 1. Setup Mocks
    mock_registry = Mock(spec=UsageRegistry)
    mock_graph = Mock(spec=SemanticGraph)
    mock_graph.registry = mock_registry

    # Let's use a real tmp_path for reading files to simplify mocking Path.read_text
    # We will create fake files that the operation can read.
    tmp_path = Path("/tmp/fake_project")  # conceptual
    mock_graph.root_path = tmp_path

    mock_workspace = Mock(spec=Workspace)
    mock_sidecar_manager = Mock(spec=SidecarManager)
    # Prevent sidecar logic from running in this unit test
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

    locations = [
        # Locations in a.py
        UsageLocation(file_a_path, 1, 23, 1, 32),  # from mypkg.core import OldHelper
        UsageLocation(file_a_path, 3, 6, 3, 15),  # obj = OldHelper()
        # Locations in b.py
        UsageLocation(file_b_path, 2, 27, 2, 36),  # from mypkg.core import OldHelper
        UsageLocation(file_b_path, 3, 11, 3, 20),  # return OldHelper
    ]

    mock_registry.get_usages.return_value = locations

    # Mock file system reads
    def mock_read_text(path, *args, **kwargs):
        if path == file_a_path:
            return source_a
        if path == file_b_path:
            return source_b
        raise FileNotFoundError(f"Mock read_text: {path}")

    # Use monkeypatch to control Path.read_text
    # This is slightly more integration-y but tests the real interaction with LibCST better.
    from unittest.mock import patch

    with patch.object(Path, "read_text", side_effect=mock_read_text, autospec=True):
        # 3. Execute
        op = RenameSymbolOperation(old_fqn, new_fqn)
        file_ops = op.analyze(ctx)

    # 4. Verify
    mock_registry.get_usages.assert_called_once_with(old_fqn)

    assert len(file_ops) == 2
    assert all(isinstance(op, WriteFileOp) for op in file_ops)

    op_a = next(op for op in file_ops if op.path == file_a_path.relative_to(tmp_path))
    op_b = next(op for op in file_ops if op.path == file_b_path.relative_to(tmp_path))

    expected_code_a = "from mypkg.core import NewHelper\n\nobj = NewHelper()"
    expected_code_b = (
        "def func():\n    from mypkg.core import NewHelper\n    return NewHelper"
    )

    assert op_a.content == expected_code_a
    assert op_b.content == expected_code_b
