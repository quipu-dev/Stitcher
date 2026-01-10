[简要回答]
是的，`CliRunner` 默认会捕获 `sys.stderr` 和 `sys.stdout`，将其存入 `result.stdout` (如果混合) 或 `result.stderr`。由于测试代码只断言了 `result.stdout`，而没有打印 `result.stderr`，导致我们错过了捕获到的调试信息。

为了强行在终端看到输出，我们将修改代码，使其直接写入 `sys.__stderr__`（原始标准错误流），从而绕过 `CliRunner` 的捕获机制。

## [WIP] fix(debug): 使用 sys.__stderr__ 绕过 CliRunner 捕获

### 错误分析
`typer.testing.CliRunner` 捕获了所有发往标准输出和标准错误的打印内容。当前的测试断言失败时仅打印了 `result.stdout`，而我们将调试信息打印到了 `sys.stderr`，如果 Runner 未配置为混合输出，这些信息就被隐藏在了 `result.stderr` 中。此外，`SpyBus` 拦截了业务日志，导致标准输出为空。

### 用户需求
在 `pytest -s` 执行时，必须能在控制台直接看到调试日志。

### 评论
使用 `sys.__stderr__` 是针对测试框架捕获机制的“越狱”手段，仅用于临时调试。

### 目标
1.  修改 `packages/stitcher-application/src/stitcher/app/runners/refactor.py`，将调试打印目标改为 `sys.__stderr__`。
2.  修改 `packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py`，将调试打印目标改为 `sys.__stderr__`。

### 基本原理
`sys.__stderr__` 保存了程序启动时的原始 stderr 文件句柄，通常不会被 `CliRunner` 或 `pytest` 的 `capsys` 劫持。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #task/domain/refactoring #task/object/logging #task/action/debug

---

### Script

#### Acts 1: 更新 `RefactorRunner` 使用 `sys.__stderr__`

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
        except (MigrationError, FileNotFoundError) as e:
            import sys
            import traceback
            print(f"DEBUG: Known Error caught in RefactorRunner: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            bus.error(L.error.generic, error=str(e))
            return False
        except Exception as e:
            import sys
            import traceback
            print(f"DEBUG: Unexpected Error caught in RefactorRunner: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            bus.error(L.error.generic, error=f"An unexpected error occurred: {e}")
            return False
~~~~~
~~~~~python.new
        except (MigrationError, FileNotFoundError) as e:
            import sys
            import traceback
            print(f"DEBUG: Known Error caught in RefactorRunner: {e}", file=sys.__stderr__)
            traceback.print_exc(file=sys.__stderr__)
            bus.error(L.error.generic, error=str(e))
            return False
        except Exception as e:
            import sys
            import traceback
            print(f"DEBUG: Unexpected Error caught in RefactorRunner: {e}", file=sys.__stderr__)
            traceback.print_exc(file=sys.__stderr__)
            bus.error(L.error.generic, error=f"An unexpected error occurred: {e}")
            return False
~~~~~

#### Acts 2: 更新 `SemanticGraph` 使用 `sys.__stderr__`

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def load_from_workspace(self) -> None:
        import sys
        print(f"DEBUG: Graph loading from workspace. Search paths: {self.search_paths}", file=sys.stderr)
        # 1. Load all main packages
        for pkg_name in self.workspace.import_to_source_dirs.keys():
            print(f"DEBUG: Loading package '{pkg_name}'", file=sys.stderr)
            try:
                module = self._griffe_loader.load(pkg_name, submodules=True)
                if isinstance(module, griffe.Module):
                    self._modules[pkg_name] = module
                else:
                    print(f"DEBUG: '{pkg_name}' loaded as {type(module)}, not Module", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Failed to load package '{pkg_name}': {e}", file=sys.stderr)
                raise
~~~~~
~~~~~python.new
    def load_from_workspace(self) -> None:
        import sys
        print(f"DEBUG: Graph loading from workspace. Search paths: {self.search_paths}", file=sys.__stderr__)
        # 1. Load all main packages
        for pkg_name in self.workspace.import_to_source_dirs.keys():
            print(f"DEBUG: Loading package '{pkg_name}'", file=sys.__stderr__)
            try:
                module = self._griffe_loader.load(pkg_name, submodules=True)
                if isinstance(module, griffe.Module):
                    self._modules[pkg_name] = module
                else:
                    print(f"DEBUG: '{pkg_name}' loaded as {type(module)}, not Module", file=sys.__stderr__)
            except Exception as e:
                print(f"DEBUG: Failed to load package '{pkg_name}': {e}", file=sys.__stderr__)
                raise
~~~~~

### 下一步建议
再次运行 `pytest -s packages/stitcher-cli/tests/integration/test_refactor_command.py`。这一次，你应该能看到异常堆栈了。
