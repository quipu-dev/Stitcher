简要回答
收到。测试失败确认了缺陷：当父目录（包）被重命名时，Sidecar 更新逻辑未能正确推导子模块的新 FQN，导致无法将符号的全限定名（FQN）还原为短名称。我将修复 `SidecarUpdateMixin` 中的这一逻辑。

## [WIP] fix: 修复 Sidecar 在包重命名时无法保持短名称的问题

### 错误分析
当前 `_update_sidecar_data` 方法在计算 `effective_new_module`（用于判断是否可以使用短名称的上下文）时，过于简单：
```python
effective_new_module = new_fqn if old_fqn == module_fqn else module_fqn
```
它只处理了“模块本身被重命名”的情况。当发生“模块的父包被重命名”（如 `mypkg.section` -> `mypkg.moved`）时，`old_fqn` (`mypkg.section`) 是 `module_fqn` (`mypkg.section.core`) 的前缀。此时，代码错误地认为模块名没变，导致后续尝试用旧的模块名去匹配新的符号 FQN，匹配失败，最终回退到了全限定名。

### 用户需求
Sidecar 文件（`.stitcher.yaml`）中的键名应尽可能保持简洁的短名称格式（如 `MyClass`），而不是全限定名（如 `pkg.mod.MyClass`），即使在发生目录移动或重构后也应如此。

### 评论
修复此问题对于保持文档的可读性至关重要，特别是对于大型项目，冗长的 FQN 会使 YAML 文件难以维护。

### 目标
修改 `stitcher/refactor/operations/base.py` 中的 `_update_sidecar_data` 方法，使其能够正确处理前缀重命名的情况，从而计算出正确的 `effective_new_module`。

### 基本原理
我们将增强 `effective_new_module` 的计算逻辑：
1.  **完全匹配**: 如果 `module_fqn == old_fqn`，则新模块名为 `new_fqn`。
2.  **前缀匹配**: 如果 `module_fqn` 以 `old_fqn + "."` 开头，说明模块在被重命名的命名空间内。此时取后缀并拼接到 `new_fqn` 上。
3.  **无匹配**: 其他情况，模块名保持不变。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/refactor #task/object/sidecar-updater #task/action/fix-bug #task/state/continue

---

### Script

#### Acts 1: 修复 SidecarUpdateMixin 逻辑

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python
            # Determine the effective module FQN for short-name restoration.
            # If the module itself is being renamed, the new context is new_fqn.
            effective_new_module = new_fqn if old_fqn == module_fqn else module_fqn

            new_key = key
            if key_fqn == old_fqn:
~~~~~
~~~~~python
            # Determine the effective module FQN for short-name restoration.
            if module_fqn == old_fqn:
                effective_new_module = new_fqn
            elif module_fqn and module_fqn.startswith(old_fqn + "."):
                # Module is inside the renamed namespace/directory
                suffix = module_fqn[len(old_fqn) :]
                effective_new_module = new_fqn + suffix
            else:
                effective_new_module = module_fqn

            new_key = key
            if key_fqn == old_fqn:
~~~~~

### 下一步建议
请再次运行刚才失败的测试 `packages/stitcher-refactor/src/stitcher/refactor/tests/integration/test_repro_sidecar_fqn.py`。预期它现在应该通过。如果通过，我们可以提交更改并删除该临时测试文件。
