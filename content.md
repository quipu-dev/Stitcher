所有的架构调整、代码迁移及文档同步工作均已圆满完成并通过验证。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交到版本库，正式标志着重构路线图中“阶段三：语义分析层整合”的达成。

## [COMMIT] refactor(analysis): 建立统一的 Python 分析层并完成跨包逻辑下沉

### 用户需求

将当前所有涉及代码迁移、依赖更新和文档同步的变更提交到 Git。

### 评论

这次提交代表了 Stitcher 架构演进的一个重要里程碑。通过建立 `stitcher-python-analysis` 包，我们成功消除了原本在适配器层和重构引擎层之间的逻辑重叠，建立了一个清晰、分层且具备多语言扩展潜力的语义分析基础。

### 目标

1.  将所有新增文件（新包、新测试、新文档）添加到暂存区。
2.  将所有修改后的配置文件和源代码添加到暂存区。
3.  创建一个符合 Conventional Commits 规范且内容详尽的提交记录。

### 基本原理

遵循 `d3-constraint-quipu-plan-script-rules`，将 Git 提交操作放在独立的计划中执行。这不仅确保了提交原子性，也为回溯重构历史提供了清晰的节点。

### 标签

#intent/refine #flow/ready #priority/high #comp/analysis #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/analysis-layer #task/action/commit #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构变更

我们将所有变更打包提交，并在提交消息中详细说明重构的内容和影响。

~~~~~act
git_add
pyproject.toml
packages/stitcher-python-analysis/
packages/stitcher-python-adapter/
packages/stitcher-refactor/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(analysis): establish shared python analysis layer

- Created 'stitcher-python-analysis' package to house common CST/AST logic.
- Migrated LibCST visitors (IR building) and transformers (strip/inject) from adapter.
- Migrated Griffe-based parsing logic to the analysis layer.
- Centralized symbol usage scanning and renaming components from refactor engine.
- Updated 'stitcher-python-adapter' and 'stitcher-refactor' to depend on the new analysis package.
- Relocated and fixed unit tests to align with the new package structure.
- Synchronized .stitcher.yaml documentation assets across all affected modules.

This completes Stage 3 (Semantic Integration) of the refactoring roadmap, resolving DRY violations and providing a unified foundation for Python code analysis.
~~~~~

### 下一步建议

随着分析层的稳固，我们现在拥有了强大的底层工具。根据重构路线图，接下来的方向可以是：

1.  **阶段四：全域重构支持**: 利用分析层提供的能力，开始增强 `stitcher-refactor` 对 `examples/` 等周边组件的支持。
2.  **性能优化**: 实现“共享 Griffe 实例”，通过在 `StitcherApp` 中维护一个长生命周期的分析服务，避免在不同任务间重复加载和解析相同的代码库，从而显著提升大规模重构的速度。

你可以随时指示我开始后续阶段的工作。
