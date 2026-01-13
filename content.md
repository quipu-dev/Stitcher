好的，我看到了新的错误报告。

1.  `test_execution_planner.py` 出现了 `NameError`，因为我忘记在测试文件中导入 `Workspace`, `LockManagerProtocol`, 和 `URIGeneratorProtocol`。
2.  `test_refactor_move_updates_suri_in_signatures.py` 出现了 `AssertionError`。这个测试是专门为旧的签名文件物理移动而设计的。现在我们迁移到了 `stitcher.lock`，这个测试的**整个逻辑和断言基础都已经失效**。它还在检查 `.stitcher/signatures/` 目录下的物理文件，而新系统根本不会创建这个目录。

**结论**：我必须同时修复 `NameError` 并彻底重写或删除那个过时的重构测试。由于“阶段 4”就是要简化重构引擎，现在重写这个测试是合适的，可以作为一个先行指标。

## [WIP] fix: 修复 NameError 并重写过时的重构测试

### 错误分析
1.  **`NameError`**: `test_execution_planner.py` 在 `mocker.create_autospec()` 中使用了 `Workspace` 等类型，但没有从各自的包中导入它们。
2.  **`AssertionError`**: `test_refactor_move_updates_suri_in_signatures.py` 的测试逻辑与新的 `stitcher.lock` 架构完全不兼容。它断言了旧的、基于物理文件的行为，而新系统致力于消除这种行为。

### 用户需求
1.  为 `test_execution_planner.py` 添加必要的导入语句来解决 `NameError`。
2.  重写 `test_refactor_move_updates_suri_in_signatures.py`，使其验证**新的正确行为**：当文件移动时，旧的 `stitcher.lock` 文件中的 SURI key 会被更新为新的 SURI key，而不是物理地移动一个 `.json` 文件。

### 评论
这次修复不仅是解决错误，更是将测试套件与新的架构愿景对齐。重写重构测试将迫使我们提前思考“阶段 4”中 `refactor` 模块的简化逻辑，确保我们的方向是正确的。这是一个很好的机会，用一个具体的测试来驱动下一步的开发。

### 目标
1.  修复 `packages/stitcher-application/tests/unit/test_execution_planner.py` 中的导入问题。
2.  重写 `packages/stitcher-refactor/tests/integration/test_refactor_move_updates_suri_in_signatures.py` 的测试逻辑，使其断言 `stitcher.lock` 文件的内容变化。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/tests #comp/refactor #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/suri-lockfile #task/action/test-suite-alignment #task/state/continue

---

### Script

#### Acts 1: 修复 `test_execution_planner.py` 的导入问题

添加缺失的导入语句。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python.old
from stitcher.app.services import DocumentManager, DocstringMerger
from stitcher.spec import (
    ModuleDef,
    FunctionDef,
    ResolutionAction,
)
~~~~~
~~~~~python.new
from stitcher.app.services import DocumentManager, DocstringMerger
from stitcher.spec import (
    ModuleDef,
    FunctionDef,
    ResolutionAction,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.workspace import Workspace
~~~~~

#### Acts 2: 重写过时的重构集成测试

这个测试需要被彻底改造，以验证 `stitcher.lock` 文件内部的 SURI key 是否被正确更新。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_refactor_move_updates_suri_in_signatures.py
~~~~~
~~~~~python
import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app


def test_move_file_operation_updates_suri_in_lockfile(tmp_path: Path):
    """
    Verify that moving a file updates the SURI keys in the corresponding stitcher.lock file.
    """
    # --- Arrange ---
    # Note: We now have a package structure.
    pkg_a_root = tmp_path / "packages" / "pkg-a"
    workspace_factory = WorkspaceFactory(root_path=tmp_path)
    workspace_root = (
        workspace_factory
        .with_config({
            "scan_paths": ["packages/pkg-a/src"]
        })
        .with_pyproject("packages/pkg-a")  # Creates pyproject.toml for pkg-a
        .with_source(
            "packages/pkg-a/src/my_app/logic.py",
            """
        def do_something():
            \"\"\"This is a docstring.\"\"\"
            pass
        """,
        )
        .build()
    )

    app = create_test_app(workspace_root)

    # --- Act 1: Initialize the project to create the lock file ---
    app.run_init()

    # --- Assert 1: Verify initial lock file and SURI key ---
    lock_path = pkg_a_root / "stitcher.lock"
    assert lock_path.exists(), "stitcher.lock should be created in the package root"

    old_suri = "py://packages/pkg-a/src/my_app/logic.py#do_something"
    new_suri = "py://packages/pkg-a/src/my_app/core/logic.py#do_something"

    initial_data = json.loads(lock_path.read_text())
    assert old_suri in initial_data["fingerprints"]
    assert "baseline_code_structure_hash" in initial_data["fingerprints"][old_suri]

    # --- Arrange 2: Create the migration script ---
    migration_script_content = """
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    spec.add(Move(
        Path("packages/pkg-a/src/my_app/logic.py"),
        Path("packages/pkg-a/src/my_app/core/logic.py")
    ))
"""
    migration_script_path = workspace_root / "migration.py"
    migration_script_path.write_text(migration_script_content)

    # --- Act 2: Run the refactor operation ---
    # We are asserting False because the refactor logic is not yet updated.
    # This is a placeholder to show what the new test *should* do.
    # The next step (Phase 4) will make this test pass.
    # For now, we expect it to fail, but for the right reasons.
    try:
        app.run_refactor_apply(migration_script_path, confirm_callback=lambda _: True)
    except Exception as e:
        # The refactor might fail because its internal logic is still old.
        # We accept this for now, the goal is to have the test structure ready.
        print(f"Refactor apply failed as expected (will be fixed in Phase 4): {e}")


    # --- Assert 2: Verify the lock file content was updated ---
    # The test will fail here until Phase 4 is complete. This is intentional.
    # The assertion is our goal.
    assert lock_path.exists(), "Lock file should still exist"
    
    # This part of the test will fail until the refactor logic is updated.
    if lock_path.exists():
        final_data = json.loads(lock_path.read_text())
        assert old_suri not in final_data["fingerprints"], "The old SURI key should be removed from the lock file"
        assert new_suri in final_data["fingerprints"], "The new SURI key should be present in the lock file"

        # Also verify the fingerprint data was preserved
        assert "baseline_code_structure_hash" in final_data["fingerprints"][new_suri]
    else:
        # This branch is for the current failing state, where the lock file might be deleted or not updated.
        assert False, "Lock file was not correctly updated or was deleted during refactor."
~~~~~

### 下一步建议
我们已经修复了 `NameError`，并且将一个关键的集成测试升级为符合新架构的“目标状态”测试。虽然这个测试现在预期会失败，但它为我们接下来的工作提供了明确的目标。

现在，测试套件应该能更完整地运行了。我们可以安全地进入 **阶段 4: 重构引擎简化 (Refactor Engine Lobotomy)**，其核心任务就是让这个刚刚重写的测试通过。
