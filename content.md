Quipu 计划 (AI 运行时)

[简要回答]
测试失败的根本原因在于 `RenameSymbolOperation` 中存在一个针对“短名称相等”的过早优化（Early Return）。在文件移动场景中，虽然符号的短名称（如 `class A`）未变，但其 FQN（`old.A` -> `new.A`）已变，这要求必须执行 Sidecar Key 的更新。我们将移除此优化，确保 Sidecar 更新逻辑始终执行。

## [WIP] fix: 修复 RenameSymbolOperation 忽略 FQN 变更的问题

### 错误分析
`RenameSymbolOperation` 的设计初衷是处理符号重命名（如 `OldClass` -> `NewClass`）。其代码中包含以下优化：
```python
old_name = self._get_base_name(self.old_fqn)
new_name = self._get_base_name(self.new_fqn)

if old_name == new_name:
    return []  # No change needed -> 导致 Sidecar 更新被跳过！
```
在文件移动场景（`MoveFileOperation`）中，我们调用 `RenameSymbolOperation("pkg.old.A", "pkg.new.A")`。此时 `old_name` ("A") 等于 `new_name` ("A")，导致操作被直接短路，Sidecar 文件（`.stitcher.yaml`）中的 Key 未能更新。

### 用户需求
1.  **正确处理 FQN 变更**: 即使符号短名称未变，只要 FQN 发生变化，就必须更新 Sidecar 文件中的 Key。
2.  **保留代码稳定性**: 如果短名称未变，不应产生无意义的代码变更（WriteFileOp）。

### 评论
这是一个典型的“优化导致语义错误”的案例。我们在处理重构操作时，必须区分“代码文本变更”和“元数据（FQN）变更”。

### 目标
1.  修改 `stitcher/refactor/operations/rename_symbol.py`，移除 `if old_name == new_name: return []` 的检查。
2.  在内部逻辑中，通过对比源代码的前后一致性（`modified_code != original_code`）来避免生成无意义的代码写入操作，从而自然地处理短名称不变的情况。

### 基本原理
*   **副作用分离**: 代码重命名和 Sidecar 重命名是两个独立的副作用。前者依赖短名称，后者依赖 FQN。不能因为前者不需要执行，就短路后者。
*   **幂等性**: `SymbolRenamerTransformer` 如果接收 `{ "A": "A" }` 的映射，会产生无变更的代码。配合 `code != original` 的检查，这天然是幂等的且安全的。

### 标签
#intent/fix #flow/ready #priority/high #comp/refactor #concept/operation #scope/core #ai/instruct #task/domain/refactor #task/object/rename-op #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `RenameSymbolOperation`

移除过早优化的检查，依靠后续的 Diff 检查来控制文件写入。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        old_name = self._get_base_name(self.old_fqn)
        new_name = self._get_base_name(self.new_fqn)

        if old_name == new_name:
            return []  # No change needed

        rename_map = {old_name: new_name}

        # 1. Find all usages
~~~~~
~~~~~python.new
    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        old_name = self._get_base_name(self.old_fqn)
        new_name = self._get_base_name(self.new_fqn)

        # Note: We do NOT return early if old_name == new_name.
        # Even if the short name hasn't changed (e.g. during a file move),
        # the FQN has changed, so we MUST update the Sidecar files.
        # The code transformation step below checks for actual content changes
        # before generating a WriteFileOp, so it's safe to proceed.

        rename_map = {old_name: new_name}

        # 1. Find all usages
~~~~~

### 下一步建议
再次运行集成测试 `test_move_file_e2e.py`，验证 Sidecar Key 是否已正确更新。
