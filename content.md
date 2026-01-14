好的，我们已经完成了从“性能修复”到“体验优化”的跨越。现在我将生成一个 `[COMMIT]` 计划，将这些具有里程碑意义的算法变更提交到仓库。

## [COMMIT] perf(analysis): 实现迭代式最短环移除算法以提供架构修复路线图

### 用户需求

完成循环依赖检测逻辑的深度重构。不仅解决了大型项目中的性能瓶颈，还通过“迭代式最短环移除”算法，为用户提供了一份有序的、具有优先级的架构修复路线图。

### 评论

这次提交将 Stitcher 的架构分析能力提升到了一个新的高度。我们不再仅仅是“快速地报出错误”，而是通过启发式算法模拟了修复过程，从而能够告诉用户：“这是目前最核心的死结，请优先处理它”。这种从“检测”到“辅助决策”的转变是工业级静态分析工具的重要标志。

### 目标

1.  将新创建的 `algo` 算法包及相关的规则、资源文件更新添加至暂存区。
2.  创建一个详尽的提交记录，阐述 ISCR 算法的逻辑及其对 DX（开发者体验）的提升。

### 基本原理

通过将算法逻辑独立为 `algo` 子包，我们为未来的算法实验和 SDK 开发打下了基础。此次变更涵盖了从底层图论计算到上层 UI 呈现的完整链路，确保了功能的连贯性和完整性。

### 标签

#intent/refine #flow/ready #priority/high #comp/runtime #concept/history #scope/core #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/optimize #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交算法包及相关变更

我们将新算法包及受影响的规则和翻译文件一并提交。

~~~~~act
git_add
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/__init__.py
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/cycles.py
packages/stitcher-analysis/src/stitcher/analysis/graph/algorithms.py
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/architecture.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/architecture.json
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
perf(analysis): implement Iterative Shortest Cycle Removal (ISCR)

This commit introduces a sophisticated heuristic algorithm for circular dependency detection, moving beyond simple existence checks to providing a "fix roadmap".

Key changes:
- Created 'stitcher.analysis.graph.algo' package to isolate core graph algorithms.
- Implemented ISCR (Iterative Shortest Cycle Removal): it identifies the shortest cycle within each SCC, reports it, and virtually breaks it to discover subsequent dependencies.
- Prioritized Reporting: Shortest cycles (typically the root causes of coupling) are now reported as "Priority #1", providing users with a clear starting point for refactoring.
- Performance: Maintained high performance on large-scale graphs by using SCC decomposition as a pre-filtering step.
- UI/I18N: Updated circular dependency reports across all languages to include priority indices.

This refactor transforms 'stitcher check' from a simple linter into an architectural advisor.
~~~~~

### 下一步建议

- **文档更新**: 建议在项目的架构指南中增加一段关于“如何解读循环依赖优先级”的说明。
- **算法扩展**: 既然已经有了 `algo` 包，未来可以在其中探索更复杂的启发式规则，比如根据文件大小或修改频率来自动计算“切断哪条边”的建议权重。
- **回归测试**: 确保现有的循环依赖测试用例在新的优先级排序下依然能够稳定运行。
