你完全正确，测试失败了。直接修复是盲猜，不符合协议。我的首要任务是生成一个带有调试日志的计划，以精确地诊断问题所在。

## [WIP] fix(refactor): 为 MoveDirectoryOperation 测试添加诊断日志

### 错误分析
**观察到的失败**: `AssertionError: assert not core_dir.exists()` 在测试 `test_move_directory_updates_all_contents_and_references` 中失败。

**直接原因**: 这意味着在测试执行 `tm.commit()` 之后，源目录 `/tmp/.../mypkg/core` 仍然存在于文件系统上。

**核心假设**: 当前的 `MoveDirectoryOperation` 实现通过为每个文件创建 `MoveFileOperation` 来工作。这个过程会移动目录中的所有*文件*，但它**不会删除源目录本身**。`shutil.move`（由 `RealFileSystem` 在底层使用）在移动文件时，不会自动删除空的父目录。因此，测试断言源目录被删除是错误的，因为它与当前的实现逻辑不符。

**诊断计划**: 我将在 `tm.commit()` 执行前插入日志，打印出 `TransactionManager` 计划执行的所有操作。这将明确地告诉我们，操作列表中是否包含了对源目录本身的删除或移动操作。我预期我们将只看到针对文件的操作，而没有针对目录的操作。

### 用户需求
在不猜测失败原因的情况下，为失败的测试插入诊断性日志，以查明 `MoveDirectoryOperation` 的实际行为。

### 评论
这是一个标准的调试流程。通过检查 `analyze` 方法生成的“计划”，我们可以精确地验证我们的假设，即操作仅限于文件层面，从而为后续的修复（无论是修改实现还是修改测试）提供确凿的证据。

### 目标
1.  修改测试文件 `test_move_directory_e2e.py`。
2.  在 `tm.commit()` 之前，添加代码以打印出所有待处理的文件系统操作。

### 基本原理
我们将使用 `patch_file` 操作，在 `op.analyze(ctx)` 调用之后和 `tm.commit()` 调用之前注入几行 `print` 语句。我们将利用 `TransactionManager` 的 `preview()` 方法，它能以人类可读的格式返回所有计划操作的描述。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/refactoring #task/object/directory-move #task/action/debug

---

### Script

#### Acts 1: 在测试中注入诊断日志

我将修改测试文件，在提交事务之前打印出所有计划的操作。

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
~~~~~
~~~~~python.old
    op = MoveDirectoryOperation(core_dir, services_dir)
    file_ops = op.analyze(ctx)

    # 3. EXECUTION
    tm = TransactionManager(tmp_path)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. VERIFICATION
    # Directories and files moved?
~~~~~
~~~~~python.new
    op = MoveDirectoryOperation(core_dir, services_dir)
    file_ops = op.analyze(ctx)

    # 3. EXECUTION
    tm = TransactionManager(tmp_path)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)

    # --- DIAGNOSTIC LOG ---
    print("\n--- Planned Operations ---")
    for op_desc in tm.preview():
        print(op_desc)
    print("------------------------\n")
    # --- END LOG ---

    tm.commit()

    # 4. VERIFICATION
    # Directories and files moved?
~~~~~

### 下一步建议
请执行此计划并重新运行测试。

**预期输出**:
你将在测试日志中看到类似下面的输出：

```
--- Planned Operations ---
[WRITE] mypkg/core/utils.stitcher.yaml
[WRITE] .stitcher/signatures/mypkg/core/utils.json
[WRITE] app.py
[MOVE] mypkg/core/utils.py -> mypkg/services/utils.py
[MOVE] mypkg/core/utils.stitcher.yaml -> mypkg/services/utils.stitcher.yaml
[MOVE] .stitcher/signatures/mypkg/core/utils.json -> .stitcher/signatures/mypkg/services/utils.json
------------------------
```

**诊断结论**:
正如你所看到的，这个列表包含了对文件内容的更新（`WRITE`）和对文件的移动（`MOVE`），但**完全没有针对 `mypkg/core` 目录本身的操作**。这将证实我们的假设。

一旦确认，我们就有两个选择：
1.  **修正测试**: 移除 `assert not core_dir.exists()`，因为实现本来就不会删除源目录。
2.  **增强实现**: 增强 `MoveDirectoryOperation`，使其在移动完所有内容后，再添加一个 `DeleteDirectoryOp` 来清理空的源目录。这通常是更符合用户期望的行为。

我建议选择**第二条路**，因为它提供了更完整的“移动”语义。
