好的，既然测试已经全部通过，我们现在将这些变更作为一个完整的逻辑单元提交到仓库中。

本次提交涵盖了交互式 CLI 的本地化重构，以及对 `FileSystemLoader` 及其相关测试的修复。

## [COMMIT] feat(cli): 交互式提示本地化与 FileSystemLoader 修复

### 用户需求
1.  将 CLI 交互式冲突解决菜单中的硬编码文本替换为基于 `L` 对象的本地化资源。
2.  修复 `pyneedle-runtime` 中因规范演进导致的过时测试用例。
3.  修正 `FileSystemLoader.put` 方法在处理 FQN 时的逻辑缺陷。

### 评论
这次重构不仅完善了系统的本地化覆盖，还通过引入语义渲染器模式提升了 CLI 代码的可维护性。同时，对核心加载器的修复确保了数据持久化的正确性。

### 目标
1.  将所有交互式 UI 文本移动到 `stitcher-common` 的 Needle 资源中。
2.  在 CLI 中实现 `TyperInteractiveRenderer` 以处理本地化输出。
3.  确保 `FileSystemLoader` 正确处理 FQN 到相对键的转换并能通过更新后的测试。
4.  完成 Git 提交。

### 基本原理
我们遵循“将表现与逻辑分离”的原则，通过 `InteractionHandler` (逻辑) 和 `InteractiveRenderer` (表现) 的协作，实现了 UI 文本的完全语义化。通过修复 `put` 方法的键转换逻辑，我们保证了文件系统存储结构的扁平化和 load/put 操作的可逆性。

### 标签
#intent/refine #intent/fix #flow/ready #comp/cli #comp/runtime #concept/ui #concept/state #scope/core #scope/ux #task/domain/ui #task/object/interactive-prompt #task/action/localize #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及到的文件添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/stitcher-common/src/stitcher/common/assets/needle/en/interactive.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/interactive.json
packages/stitcher-cli/src/stitcher/cli/interactive.py
packages/stitcher-cli/src/stitcher/cli/interactive.stitcher.yaml
packages/stitcher-cli/src/stitcher/cli/handlers.py
packages/stitcher-cli/src/stitcher/cli/main.py
packages/pyneedle-runtime/src/needle/loaders/fs_loader.py
packages/pyneedle-runtime/tests/test_assembly.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(cli): localize interactive prompts and fix FileSystemLoader bug

This commit completes the localization of the CLI by introducing a semantic
UI rendering layer for interactive sessions.

Changes:
- Added `interactive.json` assets in en/zh domains for common CLI prompts.
- Implemented `TyperInteractiveRenderer` to handle localized UI output via Nexus.
- Refactored `TyperInteractionHandler` to use semantic pointers instead of hardcoded strings.
- Fixed `FileSystemLoader.put` to correctly strip the FQN prefix before writing to files, preventing recursive key nesting.
- Updated `test_assembly.py` to align with the SST-based FQN synthesis logic.

This refactor ensures that all user-facing strings in the conflict resolution
workflow are now managed through the PyNeedle/L system.
~~~~~

### 下一步建议
- **多语言验证**: 您可以通过设置环境变量 `NEEDLE_LANG=zh` 来运行 `stitcher check`，亲身体验一下中文交互界面的效果。
- **扩展覆盖**: 检查是否有其他零星的 `typer.echo` 字符串可以进一步迁移到 `L` 空间。
