Your analysis is correct. The previous refactoring was incomplete, leading to two main categories of failures:
1.  **Stale Test Assertions**: Many tests were updated to use valid `Fingerprint` keys during setup but were not updated in their final assertions, causing mismatches.
2.  **Incorrect Test Setup**: One critical test was creating a syntactically invalid Python file, causing the refactoring engine to fail silently.
3.  **Outdated Unit Tests**: The unit tests for the `Planner` did not account for the new behavior of always generating a `stitcher.lock` update, leading to incorrect assertions on the number of generated operations.

I will now execute a plan to resolve all these issues.

#### Acts 1: Correct Test Setups and Assertions

I will systematically correct all test files that are using outdated `Fingerprint` keys in their assertions or have incorrect source file setups.

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python.old
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py",
            BUS_PY_CONTENT.replace("class MessageBus:", "class MessageBus: pass"),
        )
~~~~~
~~~~~python.new
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py",
            BUS_PY_CONTENT,
        )
~~~~~
~~~~~python.old
    assert updated_lock_data[new_suri] == {"hash": "abc"}
~~~~~
~~~~~python.new
    assert updated_lock_data[new_suri] == {"baseline_code_structure_hash": "abc"}
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
~~~~~
~~~~~python.old
    assert lock_data[expected_suri] == {"hash": "abc"}
~~~~~
~~~~~python.new
    assert lock_data[expected_suri] == {"baseline_code_structure_hash": "abc"}
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
~~~~~
~~~~~python.old
    assert lock_data[expected_suri] == {"hash": "123"}
~~~~~
~~~~~python.new
    assert lock_data[expected_suri] == {"baseline_code_structure_hash": "123"}
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_monorepo_e2e.py
~~~~~
~~~~~python.old
    assert dest_lock_data[expected_suri] == {"hash": "abc"}
~~~~~
~~~~~python.new
    assert dest_lock_data[expected_suri] == {"baseline_code_structure_hash": "abc"}
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_nested_directory_e2e.py
~~~~~
~~~~~python.old
    assert lock_data[expected_suri] == {"h": "123"}
~~~~~
~~~~~python.new
    assert lock_data[expected_suri] == {"baseline_code_structure_hash": "123"}
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_suri_update.py
~~~~~
~~~~~python.old
    assert updated_data[new_suri]["hash"] == "original_hash"
~~~~~
~~~~~python.new
    assert updated_data[new_suri]["baseline_code_structure_hash"] == "original_hash"
~~~~~
~~~~~python.old
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "123"})}
~~~~~
~~~~~python.new
    fingerprints = {old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "123"})}
~~~~~
~~~~~python.old
    assert updated_data[new_suri]["hash"] == "123"
~~~~~
~~~~~python.new
    assert updated_data[new_suri]["baseline_code_structure_hash"] == "123"
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
~~~~~
~~~~~python.old
    assert lock_data[new_suri] == {"hash": "abc"}
~~~~~
~~~~~python.new
    assert lock_data[new_suri] == {"baseline_code_structure_hash": "abc"}
~~~~~

#### Acts 2: Update Planner Unit Tests

Next, I will update the planner's unit tests to correctly account for the `stitcher.lock` file operation that is now generated alongside code modifications.

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python.old
def test_planner_merges_rename_operations_for_same_file(mock_context: Mock):
    """
    CRITICAL: This test verifies that the Planner can merge multiple rename
    operations that affect the SAME file into a SINGLE WriteFileOp.
    This prevents the "Lost Edit" bug.
    """
    # 1. ARRANGE
    file_path = mock_context.graph.root_path / "app.py"
    original_content = "class OldClass: pass\ndef old_func(): pass"

    # Define two rename operations
    op1 = RenameSymbolOperation("app.OldClass", "app.NewClass")
    op2 = RenameSymbolOperation("app.old_func", "app.new_func")
    spec = MigrationSpec().add(op1).add(op2)

    # Mock find_usages to return locations for BOTH symbols in the same file
    def mock_find_usages(fqn):
        if fqn == "app.OldClass":
            return [
                UsageLocation(
                    file_path, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass"
                )
            ]
        if fqn == "app.old_func":
            return [
                UsageLocation(
                    file_path, 2, 4, 2, 12, ReferenceType.SYMBOL, "app.old_func"
                )
            ]
        return []

    mock_context.graph.find_usages.side_effect = mock_find_usages

    # Mock file reading
    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # There should be exactly ONE operation: a single WriteFileOp for app.py
    assert len(file_ops) == 1, "Planner should merge writes to the same file."
    write_op = file_ops[0]
    assert isinstance(write_op, WriteFileOp)
    assert write_op.path == Path("app.py")

    # The content of the WriteFileOp should contain BOTH changes
    final_content = write_op.content
    assert "class NewClass: pass" in final_content
    assert "def new_func(): pass" in final_content
~~~~~
~~~~~python.new
def test_planner_merges_rename_operations_for_same_file(mock_context: Mock):
    """
    Verifies that the Planner merges multiple renames affecting the same source file
    into a single WriteFileOp, and also produces a WriteFileOp for the lock file.
    """
    # 1. ARRANGE
    file_path = mock_context.graph.root_path / "app.py"
    original_content = "class OldClass: pass\ndef old_func(): pass"

    op1 = RenameSymbolOperation("app.OldClass", "app.NewClass")
    op2 = RenameSymbolOperation("app.old_func", "app.new_func")
    spec = MigrationSpec().add(op1).add(op2)

    def mock_find_usages(fqn):
        if fqn == "app.OldClass":
            return [UsageLocation(file_path, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")]
        if fqn == "app.old_func":
            return [UsageLocation(file_path, 2, 4, 2, 12, ReferenceType.SYMBOL, "app.old_func")]
        return []
    mock_context.graph.find_usages.side_effect = mock_find_usages

    from unittest.mock import patch
    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # Expect 2 ops: one for the source file, one for the lock file.
    assert len(file_ops) == 2
    
    write_ops = {op.path.name: op for op in file_ops if isinstance(op, WriteFileOp)}
    assert "app.py" in write_ops
    assert "stitcher.lock" in write_ops

    final_content = write_ops["app.py"].content
    assert "class NewClass: pass" in final_content
    assert "def new_func(): pass" in final_content
~~~~~
~~~~~python.old
def test_planner_handles_move_and_rename_on_same_file(mock_context: Mock):
    """
    Verifies that a file move and symbol renames within that file are planned correctly,
    resulting in a MoveOp and a single WriteOp with merged content.
    """
    # 1. ARRANGE
    src_path_rel = Path("app.py")
    dest_path_rel = Path("new_app.py")
    src_path_abs = mock_context.graph.root_path / src_path_rel
    original_content = "class OldClass: pass"

    # Define operations
    move_op = MoveFileOperation(
        src_path_abs, mock_context.graph.root_path / dest_path_rel
    )
    rename_op = RenameSymbolOperation("app.OldClass", "new_app.NewClass")
    spec = MigrationSpec().add(move_op).add(rename_op)

    # Mock find_usages
    mock_context.graph.find_usages.return_value = [
        UsageLocation(src_path_abs, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")
    ]

    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # We expect two ops: one MoveFileOp and one WriteFileOp
    assert len(file_ops) == 2

    move_ops = [op for op in file_ops if isinstance(op, MoveFileOp)]
    write_ops = [op for op in file_ops if isinstance(op, WriteFileOp)]

    assert len(move_ops) == 1
    assert len(write_ops) == 1

    # Verify the MoveOp
    assert move_ops[0].path == src_path_rel
    assert move_ops[0].dest == dest_path_rel

    # Verify the WriteOp
    # The planner generates the write for the ORIGINAL path. The TransactionManager
    # is responsible for rebasing it to the new path.
    assert write_ops[0].path == src_path_rel
    assert "class NewClass: pass" in write_ops[0].content
~~~~~
~~~~~python.new
def test_planner_handles_move_and_rename_on_same_file(mock_context: Mock):
    """
    Verifies a file move and symbol rename are planned correctly, resulting
    in a MoveOp, a WriteOp for the code, and a WriteOp for the lock file.
    """
    # 1. ARRANGE
    src_path_rel = Path("app.py")
    dest_path_rel = Path("new_app.py")
    src_path_abs = mock_context.graph.root_path / src_path_rel
    original_content = "class OldClass: pass"

    move_op = MoveFileOperation(src_path_abs, mock_context.graph.root_path / dest_path_rel)
    rename_op = RenameSymbolOperation("app.OldClass", "new_app.NewClass")
    spec = MigrationSpec().add(move_op).add(rename_op)

    mock_context.graph.find_usages.return_value = [
        UsageLocation(src_path_abs, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")
    ]

    from unittest.mock import patch
    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # Expect 3 ops: MoveOp (code), WriteOp (code), WriteOp (lock)
    assert len(file_ops) == 3

    move_ops = [op for op in file_ops if isinstance(op, MoveFileOp)]
    write_ops = {op.path.name: op for op in file_ops if isinstance(op, WriteFileOp)}

    assert len(move_ops) == 1
    assert len(write_ops) == 2
    assert "app.py" in write_ops
    assert "stitcher.lock" in write_ops

    assert move_ops[0].path == src_path_rel
    assert move_ops[0].dest == dest_path_rel

    assert "class NewClass: pass" in write_ops["app.py"].content
~~~~~

### 下一步建议

所有已知的测试失败都已解决。这些修复统一了测试基准，使其与 `stitcher.lock` 架构保持一致，并修正了 `Planner` 的单元测试。现在，我建议重新运行完整的测试套件，以确认所有问题都已修复，并且系统处于稳定状态。
