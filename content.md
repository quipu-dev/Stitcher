## [COMMIT] fix: 恢复 SemanticGraph.load 并增强 RenameSymbolOperation 容错性

### 用户需求

1.  修复因移除 `SemanticGraph.load(package_name)` 导致的大量测试失败。
2.  增强 `RenameSymbolOperation` 的容错性，使其在找不到符号定义时不再抛出异常，而是优雅地降级（仅执行代码重命名，跳过 Sidecar 更新）。

### 评论

这次修复同时兼顾了向后兼容性和系统的健壮性。恢复 `load` 方法使得单一包的分析再次成为可能，这对于单元测试至关重要。而改进 `RenameSymbolOperation` 的错误处理逻辑，则消除了一个隐蔽的崩溃源，使重构引擎在面对不完整的语义信息时更加有韧性。

### 目标

1.  在 `SemanticGraph` 中恢复 `load` 方法。
2.  在 `SemanticGraph` 中新增 `find_symbol` 方法，提供全图符号查找能力。
3.  重构 `RenameSymbolOperation` 以使用 `find_symbol` 并移除静默异常处理。
4.  更新 `Workspace` 以支持周边路径（peripheral paths）的识别。

### 基本原理

通过显式地将“符号查找失败”视为一种有效状态而非异常，我们允许重构操作在信息不完全的情况下继续进行“尽力而为”的处理。这符合实际工程场景，因为静态分析并不总是完美的。同时，保留 `load` 方法作为 helper，避免了为了适配新 API 而大规模重写现有测试的成本。

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #scope/core #scope/dx #ai/instruct #task/domain/refactoring #task/object/resilience #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 提交变更

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
packages/stitcher-application/src/stitcher/app/runners/refactor.py
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
packages/stitcher-refactor/tests/unit/operations/test_rename_symbol_operation.py
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(refactor): restore SemanticGraph.load and improve rename resilience

1.  **Restore `SemanticGraph.load`**: Re-added the `load(package_name)` method to `SemanticGraph` to fix backward compatibility with existing unit tests and to support isolated package analysis.
2.  **Add `SemanticGraph.find_symbol`**: Introduced a robust public API for finding symbol definitions across the entire loaded graph.
3.  **Enhance `RenameSymbolOperation`**:
    *   Refactored to use `find_symbol`.
    *   Removed silent `try...except ValueError` block.
    *   Now gracefully handles missing symbol definitions by skipping sidecar updates instead of crashing or raising errors.
4.  **Update `Workspace`**: Added support for identifying and loading `peripheral_paths` (e.g. examples, scripts) as distinct from core source paths.
5.  **Refactor `RefactorRunner`**: Simplified loading logic to use the new `SemanticGraph.load_from_workspace`.

This change stabilizes the refactoring engine and ensures that refactoring operations are resilient to partial semantic information.


- Corrected an AttributeError in `SemanticGraph.load_from_workspace` where `self._griffe_loader.modules_collection` (a `ModulesCollection` object) was being accessed with `.values()`. It now correctly uses `.members.values()`.
- Replaced silent `try-except: pass` blocks with explicit `logging` calls and selective re-raising in `SemanticGraph`. This ensures that critical parsing or loading failures are visible in the logs rather than failing silently.
- Cleaned up temporary debug prints to `sys.__stderr__` used during troubleshooting.
- Verified the fix by successfully running integration tests for the `refactor apply` command.
~~~~~

### 下一步建议

现在测试已经通过，基础组件也已增强，我们可以继续执行原计划的 **4.2 调整 Planner 策略**。

具体任务是：修改 `Planner`（或相关的 Operation），在生成 Sidecar 更新意图之前，利用 `Workspace.is_peripheral(path)` 检查文件是否属于周边代码。如果是，则**不生成** `SidecarUpdateIntent`，因为周边代码不应该有伴生的 `.stitcher.yaml` 文件。
