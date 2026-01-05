好的，重构工作已经完成。现在我将生成一个 `[COMMIT]` 计划，将 `MoveDirectoryOperation` 的重构更改提交到 Git 仓库。

## [COMMIT] refactor(refactor): unify sidecar update logic in MoveDirectoryOperation using Mixin

### 用户需求
将 `MoveDirectoryOperation` 的重构改动进行提交，以持久化对边车更新逻辑的统一。

### 评论
这次重构不仅消除了冗余代码，还通过复用 `SidecarUpdateMixin` 增强了目录移动操作的健壮性，确保了在复杂的命名空间迁移中，边车文件（.stitcher.yaml 和签名 JSON）能够被正确地调和。

### 目标
1.  将修改后的 `move_directory.py` 添加到暂存区。
2.  创建一个清晰且符合规范的 Git 提交。

### 基本原理
遵循“指令级约束：脚本与 Git 操作互斥”原则，我们将 Git 提交操作放在一个独立的计划中执行。

### 标签
#intent/refine #flow/ready #priority/medium #comp/engine #task/domain/refactor #task/object/move-directory-operation #task/action/refactor-with-mixin #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构更改

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(refactor): unify sidecar update logic in MoveDirectoryOperation

Refactored MoveDirectoryOperation to inherit from SidecarUpdateMixin, aligning its sidecar handling logic with MoveFileOperation and RenameSymbolOperation.

Key changes:
- Removed redundant implementation of '_path_to_fqn' within MoveDirectoryOperation.
- Replaced manual string replacement for sidecar keys with 'self._update_sidecar_data' from the Mixin.
- This ensures robust handling of both FQNs and short-names in .stitcher.yaml files during directory-level namespace migrations.
~~~~~

### 下一步建议
- **代码审查**: 建议再次审查 `SidecarUpdateMixin` 的实现，看是否还有进一步提取通用逻辑的空间（例如文件移动本身的物理操作）。
- **扩展重构**: 检查项目中是否还有其他自定义的文件操作类，评估其是否也能从该 Mixin 中受益。
