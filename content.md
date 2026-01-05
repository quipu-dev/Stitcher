简要回答
好的，既然测试已经通过，我将按照你的指示保留该测试文件作为防回归测试。现在我将生成一个 `[COMMIT]` 计划，将修复代码和新的集成测试一并提交。

## [COMMIT] fix: 确保在命名空间重命名期间 Sidecar 键名保持为短名称

### 用户需求
在进行目录移动或包重构时，`.stitcher.yaml` 中的键名应当保持为相对于模块的短名称（Short Name），而非展开为全限定名（FQN）。

### 评论
保留复现测试作为回归测试是非常正确的做法。这确保了未来对重构引擎或 `SidecarUpdateMixin` 的任何修改都不会再次破坏 Sidecar 的可读性。

### 目标
1. 提交 `SidecarUpdateMixin` 的逻辑修复。
2. 提交新增的集成测试 `test_repro_sidecar_fqn.py`。

### 基本原理
我们在 `SidecarUpdateMixin` 中增强了模块路径推导逻辑，使其能够识别父包的变更并同步更新模块的上下文路径。这使得在重写 Sidecar 键名时，能够正确匹配并剥离新的 FQN 前缀，从而恢复短名称。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/refactor #task/object/sidecar-updater #task/action/fix-bug #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将修复的代码和新的回归测试添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
packages/stitcher-refactor/src/stitcher/refactor/tests/integration/test_repro_sidecar_fqn.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(refactor): preserve short names in sidecar keys during namespace renames

Previously, the SidecarUpdateMixin failed to correctly calculate the 'effective_new_module' path when a parent directory (package) was renamed. This resulted in the mixin being unable to strip the new FQN prefix from symbol keys in the sidecar YAML, causing them to be expanded to full FQNs, which reduced readability.

Changes:
- Enhanced `_update_sidecar_data` to handle prefix-based renames for modules.
- Added an integration test 'test_repro_sidecar_fqn.py' to verify short name retention when moving directories.

This fix ensures that sidecar documentation remains concise and follows the standard 'short-name' format expected by most Stitcher configurations.
~~~~~

### 下一步建议
我们已经解决了 Sidecar 键名 FQN 展开的问题。建议后续可以进一步审查 `RenameSymbolOperation` 在复杂嵌套类场景下的键名处理，确保其在各种深度重构下都能保持一致的简洁性。
