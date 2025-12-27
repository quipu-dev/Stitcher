好的。我将创建一个包含所有架构和配置变更的完整提交。

## [COMMIT] feat(core): 实现多目标存根生成并完成自举配置

### 用户需求
将项目配置升级为多目标模式，以解决 Monorepo 中不同顶级包（`stitcher` 和 `pyneedle`）的存根生成冲突问题，并最终完成 Stitcher 在其自身项目中的自举配置（Dogfooding Setup）。

### 评论
这是一个关键的里程碑。通过引入 `[tool.stitcher.targets]` 配置结构，我们使 Stitcher 从一个单项目工具升级为真正的 Monorepo 类型协调器。新的架构更具鲁棒性、可扩展性，并正确遵循了 PEP 561 的分发包原则。所有配置、核心逻辑和测试都已更新以支持这一变化。

### 目标
1.  **提交** `pyproject.toml` 中新的 `[tool.stitcher.targets.stitcher-python]` 和 `[tool.stitcher.targets.pyneedle]` 配置。
2.  **提交** `stitcher-config` 和 `stitcher-application` 中对多目标解析和遍历的核心逻辑重构。
3.  **提交** 修复和新增的测试用例，确保新架构的正确性。

### 基本原理
新的多目标配置通过将扫描路径和输出路径与逻辑目标名称绑定，为 Monorepo 中的每个独立包创建了清晰的边界。这使得我们可以在项目的 `pyproject.toml` 中管理所有包的类型存根生成，并通过 `extraPaths` 将新生成的存根包路径注入到 IDE 和工具链中。

### 标签
#intent/build #intent/architect #intent/refine #flow/ready #priority/high #comp/config #comp/runtime #comp/tests #concept/build #concept/architecture #scope/core #scope/dx #ai/instruct #task/domain/build #task/object/multitarget-engine #task/action/implementation #task/state/end

---
### Script

#### Acts 1: 添加所有文件到暂存区

~~~~~act
git_add
.
~~~~~

#### Acts 2: 创建提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement multi-target stub generation for Monorepo support

This commit introduces a fundamental architectural upgrade to support generating type stubs for multiple distinct top-level packages within a single workspace (Monorepo).

Key changes:
1.  **Configuration Refactor**: Switched from a single [tool.stitcher] block to a multiple target structure via [tool.stitcher.targets.{name}]. This enables "dogfooding" the project by correctly configuring separate stub packages for `stitcher-python` and `pyneedle`.
2.  **Core Logic Update**: Refactored `StitcherApp` and `load_config_from_path` to process a *list* of `StitcherConfig` objects, enabling independent scanning and stub generation per target.
3.  **Testing**: Added new integration tests to cover the multi-target execution flow and fixed previous path assertion errors.
4.  **Cleanup**: Removed the unused `typings` directory and added scaffolded stub package directories (`stitcher-stubs`, `pyneedle-stubs`).
~~~~~

### 下一步建议
提交已完成。现在，请执行 `stitcher generate` 命令来运行自举过程。这将为 `stitcher` 和 `needle` 命名空间生成各自的 PEP 561 存根包。
