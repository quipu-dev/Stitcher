You've correctly identified the bug. The `refactor apply` command's `try...except Exception` block is too broad, causing it to catch the `typer.Exit()` intended for a clean exit on `--dry-run` and then re-raising it as a generic error with exit code 1.

The correct approach for a successful exit in a Typer command function is to simply `return`. This signals a successful completion with exit code 0. I will generate a plan to replace the incorrect `raise typer.Exit()` calls with `return` for the successful "no-op" and "dry-run" paths.

## [WIP] fix: Correct exit code for successful refactor dry-run

### 错误分析

测试 `test_refactor_apply_dry_run` 失败的根本原因是 `refactor_command` 中的一个控制流缺陷。

1.  **异常捕获过于宽泛**: 整个命令的主体逻辑被包裹在一个 `try...except Exception:`块中。
2.  **不正确的成功退出**: 对于 `--dry-run` 成功或“无可执行操作”的场景，代码使用 `raise typer.Exit()` 来终止执行。
3.  **冲突**: `typer.Exit()` 继承自 `SystemExit`，而 `SystemExit` 又继承自 `BaseException`，但它也会被 `except Exception:` 块捕获。
4.  **结果**: 正常的 `typer.Exit()` 被异常处理块捕获，然后被当作一个未知错误重新抛出，并附带了 `code=1`，导致测试断言 `result.exit_code == 0` 失败。

### 用户需求

用户需要修复 `test_refactor_apply_dry_run` 测试。这要求 `stitcher refactor apply --dry-run` 命令在成功预览变更后，必须以退出码 `0` 结束。

### 评论

这是一个常见的编程错误，即使用异常处理来进行常规的控制流管理。在 `Typer` (以及 Click) 应用中，一个函数的正常返回 (`return`) 等同于成功的退出（`exit(0)`）。将表示成功的 `raise typer.Exit()` 修改为 `return` 可以使代码意图更清晰，并避免被宽泛的异常捕获块错误地处理。

### 目标

1.  定位到 `packages/stitcher-cli/src/stitcher/cli/commands/refactor.py` 文件中的 `refactor_command` 函数。
2.  将处理“无操作”情况的 `raise typer.Exit()` 替换为 `return`。
3.  将处理 `--dry-run` 成功的情况的 `raise typer.Exit()` 替换为 `return`。

### 基本原理

我们将修改控制流，以遵循 CLI 应用的最佳实践：仅对真正的错误情况使用异常和非零退出码。对于所有成功的执行路径，包括那些不执行任何操作的路径（如 dry-run），我们应该允许函数正常返回，`Typer` 会自动将其解释为 `exit(0)`。

### 标签

#intent/fix #flow/ready #priority/high #comp/cli #concept/executor #scope/dx #ai/instruct #task/domain/cli #task/object/refactor-command #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修正 refactor 命令的成功退出逻辑

我们将修改 `refactor.py`，将用于成功退出的 `raise typer.Exit()` 语句替换为 `return`，以防止它们被异常处理块错误捕获。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~python.old
        if not file_ops:
            bus.success(L.refactor.run.no_ops)
            raise typer.Exit()

        # 3. Preview and Confirm
        tm = TransactionManager(root_path)
        for op in file_ops:
            # This logic needs to be smarter based on op type
            if op.__class__.__name__ == "WriteFileOp":
                tm.add_write(op.path, op.content)
            elif op.__class__.__name__ == "MoveFileOp":
                tm.add_move(op.path, op.dest)
            elif op.__class__.__name__ == "DeleteFileOp":
                tm.add_delete_file(op.path)
            elif op.__class__.__name__ == "DeleteDirectoryOp":
                tm.add_delete_dir(op.path)

        bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
        for desc in tm.preview():
            typer.echo(f"  {desc}")

        if dry_run:
            raise typer.Exit()
~~~~~
~~~~~python.new
        if not file_ops:
            bus.success(L.refactor.run.no_ops)
            return

        # 3. Preview and Confirm
        tm = TransactionManager(root_path)
        for op in file_ops:
            # This logic needs to be smarter based on op type
            if op.__class__.__name__ == "WriteFileOp":
                tm.add_write(op.path, op.content)
            elif op.__class__.__name__ == "MoveFileOp":
                tm.add_move(op.path, op.dest)
            elif op.__class__.__name__ == "DeleteFileOp":
                tm.add_delete_file(op.path)
            elif op.__class__.__name__ == "DeleteDirectoryOp":
                tm.add_delete_dir(op.path)

        bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
        for desc in tm.preview():
            typer.echo(f"  {desc}")

        if dry_run:
            return
~~~~~

### 下一步建议

我们已经应用了修复。现在，我建议运行整个测试套件，特别是 `test_refactor_command.py`，以验证修复是否解决了问题，并且没有引入新的回归。
