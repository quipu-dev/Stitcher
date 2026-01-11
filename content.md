好的，我们终于找到了根本原因！

`An unexpected error occurred: no such table: files`

这个 `sqlite` 错误信息清晰地表明，`refactor` 命令在执行时，索引数据库（`index.db`）是存在的，但内部是空的，连最基本的 `files` 表都没有。

## [WIP] fix: 确保重构命令在执行前初始化索引数据库

### 错误分析

调试探针测试捕获到的 SQLite 错误 `"no such table: files"` 明确地暴露了问题的根源。

`RefactorRunner` 依赖一个功能完备的语义索引来查找符号用法。它通过 `run_index_build` 来更新索引，但这个更新过程**假设数据库的表结构已经存在**。`FileIndexer.index_files` 方法会直接对 `files` 表进行 `SELECT` 和 `UPDATE` 操作，如果表不存在，就会立即导致 `sqlite3.OperationalError: no such table` 异常。

在正常的 CLI 工作流中，用户通常会先手动运行 `stitcher index build`，这个命令的执行入口 `IndexRunner.run_build` 包含了 `self.db_manager.initialize()` 这一关键步骤，它会执行 `schema.sql` 来创建所有必要的表。

然而，`RefactorRunner` 为了保证索引是最新的，自己调用了 `self.file_indexer.index_files()`，但它**遗漏了**在调用索引器之前先调用 `self.db_manager.initialize()` 的步骤。

这个缺陷在之前的测试中没有被发现，可能是因为其他的测试（比如 `check` 命令的测试）在 `refactor` 测试之前运行，并“意外地”初始化了数据库，从而掩盖了这个问题。但当测试被隔离执行时，这个隐藏的依赖问题就暴露了出来。

### 用户需求

修复 `refactor apply` 命令，使其能够在执行索引更新之前，确保索引数据库的表结构已经被正确创建。

### 评论

这是一个典型的“隐式依赖”或“状态假设”错误。`RefactorRunner` 错误地假设了数据库总是处于一个可用的状态。修复这个问题的关键是让 `RefactorRunner` 对自己的依赖项（一个初始化好的数据库）负起责任，而不是依赖外部或偶然的状态。

### 目标

修改 `packages/stitcher-application/src/stitcher/app/runners/refactor.py` 中的 `run_apply` 方法，在调用 `self.file_indexer.index_files(files_to_index)` 之前，显式地调用 `self.db_manager.initialize()`。

### 基本原理

这个修复方案确保了 `refactor` 命令的原子性和自足性。无论当前的 `.stitcher/index/index.db` 文件是否存在或是空的，`run_apply` 命令总能保证在开始任何数据库操作之前，表结构是完整且正确的。这消除了对外部状态的依赖，使得命令在任何情况下都能可靠地执行。

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/integration-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 RefactorRunner 中添加数据库初始化步骤

我将修改 `refactor.py` 文件，在更新索引之前确保数据库 schema 已经创建。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
            bus.info(L.index.run.start)
            workspace = Workspace(self.root_path, config)

            # The FileIndexer was created with an unconfigured workspace.
            # We must re-register the adapter with the correct search paths.
            self.file_indexer.register_adapter(
                ".py", PythonAdapter(self.root_path, workspace.get_search_paths())
            )

            files_to_index = workspace.discover_files()
            self.file_indexer.index_files(files_to_index)
~~~~~
~~~~~python.new
            bus.info(L.index.run.start)
            workspace = Workspace(self.root_path, config)

            # Ensure the database schema is initialized before indexing.
            from stitcher.index.db import DatabaseManager
            db_manager = DatabaseManager(
                self.root_path / ".stitcher" / "index" / "index.db"
            )
            db_manager.initialize()

            # The FileIndexer was created with an unconfigured workspace.
            # We must re-register the adapter with the correct search paths.
            self.file_indexer.register_adapter(
                ".py", PythonAdapter(self.root_path, workspace.get_search_paths())
            )

            files_to_index = workspace.discover_files()
            self.file_indexer.index_files(files_to_index)
~~~~~

#### Acts 2: 删除临时调试探针测试

既然我们已经找到了根本原因并制定了修复计划，这个调试测试文件就不再需要了。

~~~~~act
delete_file
packages/stitcher-cli/tests/integration/test_refactor_debug_probe.py
~~~~~

#### Acts 3: 移除 `test_refactor_command.py` 中的临时调试代码

我们现在可以清理之前为增加可观测性而添加的 `print` 语句和 `--verbose` 标志。

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["--verbose", "refactor", "apply", str(migration_script), "--yes"],
            catch_exceptions=False,
        )

    # 3. Assert
    print(result.stdout)
    print(result.stderr)
    assert result.exit_code == 0, result.stdout
~~~~~
~~~~~python.new
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--yes"],
            catch_exceptions=False,
        )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["--verbose", "refactor", "apply", str(migration_script), "--dry-run"],
            catch_exceptions=False,
        )

    # 3. Assert
    print(result.stdout)
    print(result.stderr)
    assert result.exit_code == 0, result.stdout
~~~~~
~~~~~python.new
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--dry-run"],
            catch_exceptions=False,
        )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
~~~~~

### 下一步建议

这个修复方案直接命中了问题的核心。请应用此计划并重新运行完整的测试套件。我非常有信心这次所有测试都将通过。
