You are absolutely right. My apologies. I incorrectly assumed `workspace_factory` was a globally available fixture. The traceback clearly shows it is not, and your diagnosis to instantiate it directly is the correct solution.

I will now correct the test file to properly set up the `WorkspaceFactory` using the standard `tmp_path` fixture provided by Pytest. This will resolve the setup error and allow the test to run and fail for the intended reason—the SURI bug.

## [WIP] fix: Correct test setup by instantiating WorkspaceFactory

### 错误分析

The previous plan generated a test that depended on a non-existent Pytest fixture named `workspace_factory`. The error `fixture 'workspace_factory' not found` indicates a failure in the test's setup phase, preventing the actual test logic from ever running. The correct approach is to instantiate the `WorkspaceFactory` class directly, providing it with a temporary directory managed by Pytest's built-in `tmp_path` fixture.

### 用户需求

Modify the newly created test file, `test_refactor_move_updates_suri_in_signatures.py`, to remove the dependency on the missing fixture and instead instantiate `WorkspaceFactory` manually.

### 评论

This is a necessary correction to the test harness itself. By fixing the setup, we ensure the test can proceed to accurately validate the behavior of the refactoring engine and correctly expose the SURI update bug. This aligns with the TDD principle of ensuring tests fail for the right reasons.

### 目标

1.  Modify the test function signature to accept the standard `tmp_path: Path` fixture.
2.  Inside the test, create an instance of `WorkspaceFactory` using the provided `tmp_path`.

### 基本原理

I will use a `patch_file` operation to replace the incorrect function signature and setup logic. The new code will request the `tmp_path` fixture and then use it to initialize `WorkspaceFactory`, which in turn sets up the test environment in that temporary directory. The rest of the test logic can then proceed as originally designed.

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-setup #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Correct the test setup

I will now patch the test file to fix the instantiation of `WorkspaceFactory`.

~~~~~act
patch_file
tests/integration/test_refactor_move_updates_suri_in_signatures.py
~~~~~
~~~~~python.old
def test_move_file_operation_updates_suri_in_signatures(workspace_factory: WorkspaceFactory):
    """
    Verify that moving a file also updates the SURI keys in the signature file.
    """
    # --- Arrange ---
    workspace_root = workspace_factory.with_config({
        "scan_paths": ["src"]
    }).with_source(
        "src/my_app/logic.py",
~~~~~
~~~~~python.new
def test_move_file_operation_updates_suri_in_signatures(tmp_path: Path):
    """
    Verify that moving a file also updates the SURI keys in the signature file.
    """
    # --- Arrange ---
    workspace_factory = WorkspaceFactory(root_path=tmp_path)
    workspace_root = workspace_factory.with_config({
        "scan_paths": ["src"]
    }).with_source(
        "src/my_app/logic.py",
~~~~~

### 下一步建议

The test setup has been corrected. Please run the test suite again. The test should now proceed past the setup phase and fail at the final assertion, successfully reproducing the SURI update bug.
