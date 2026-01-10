好的，我们已经完成了代码架构的梳理和测试文件的归位。现在我将生成一个计划，将这些变更作为一个完整的逻辑单元提交到 Git 仓库。

## [COMMIT] refactor(python): 解耦 analysis 与 adapter 层并规范测试布局

### 用户需求
完成 `stitcher-python-analysis` 与 `stitcher-python-adapter` 的解耦工作，并按照 monorepo 规范完成测试文件的重组。

### 评论
这是一次重要的架构清理。通过将 `GriffePythonParser` 的实现移动到 `adapter` 层，我们确保了 `analysis` 包作为一个纯粹的工具库，不再逆向依赖应用层的 `stitcher-spec` 协议。同时，测试文件的归位使得每个包都符合“代码与测试共存”的原则，极大提升了项目的可维护性和清晰度。

### 目标
1. 提交 `GriffePythonParser` 从 `analysis` 包迁移至 `adapter` 包的变更。
2. 提交测试文件在 `adapter` 与 `analysis` 包之间的重新组织和归类。
3. 清理掉不再需要的代理模块和目录。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules-D3-P2`，在完成文件系统操作后，在一个独立的 `[COMMIT]` 计划中执行 Git 提交。这将所有架构优化动作封装在一个清晰的历史节点中，便于回溯。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #comp/engine #scope/core #dx #ai/instruct #task/domain/testing #task/object/test-organization #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有受影响的文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
packages/stitcher-python-adapter/tests/
packages/stitcher-python-analysis/tests/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(python): decouple analysis and adapter layers

This commit performs a major architectural cleanup between the Python
analysis and adapter packages:

1. Relocated `GriffePythonParser` implementation from `stitcher-python-analysis`
   to `stitcher-python-adapter`. This restores the correct dependency flow
   where the adapter package implements application protocols using the
   pure utility analysis package.
2. Reorganized test files across both packages to follow the monorepo
   standard (tests live with the code they verify).
3. Corrected test classification by moving integrated component tests
   from `unit/` to `integration/` directories.
4. Cleaned up redundant proxy modules in the adapter layer.

These changes significantly improve architectural integrity and developer
experience by making the project structure more predictable and decoupled.
~~~~~

### 下一步建议
- **依赖分析**: 建议运行 `uv tree` 或类似的工具检查 `stitcher-python-analysis` 的依赖，确认其是否已彻底不再依赖 `stitcher-spec`。
- **环境验证**: 运行 `pytest` 确保所有移动后的测试都能正常发现并执行。由于测试文件位置发生了变化，可能需要更新 CI 配置中的测试路径。
