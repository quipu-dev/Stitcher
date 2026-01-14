好的，整个架构分析子系统的重构和优化已经完成，且测试已修复。现在我将生成最终的 `[COMMIT]` 计划，将这些成果持久化到仓库中。

## [COMMIT] refactor(analysis): 深度重构循环依赖分析以提升性能与修复体验

### 用户需求

对 Stitcher 的架构检查子系统进行全面的性能和体验升级。解决大型项目中的性能爆炸问题，提供更具洞察力的耦合组件摘要和有序的修复路线图，并确保测试套件的完整性。

### 评论

这次提交标志着 Stitcher 架构分析能力的成熟。我们通过引入 `algo` 算法包，不仅解决了由于 `networkx` 简单环枚举导致的性能危机，还通过迭代式最短环移除（ISCR）算法实现了“修复路线图”这一高级特性。同时，对报告流程的重构彻底解决了信息冗余问题，为开发者提供了一个从“宏观视图（SCC 摘要）”到“微动视图（优先级环路）”的清晰报告层级。

### 目标

1.  将所有算法优化、报告重构、语言包更新以及测试修复相关的变更提交到 Git。
2.  确保提交记录详尽地描述了本次重构的技术深度和对 DX 的改进。

### 基本原理

遵循原子化提交原则。虽然涉及的文件较多，但它们共同构成了一个完整的功能/架构演进单元。通过将算法、业务逻辑、UI 呈现和验证代码一并提交，我们确保了仓库状态在逻辑上的连贯性。

### 标签

#intent/refine #flow/ready #priority/high #comp/analysis #comp/application #comp/common #concept/ui #scope/core #scope/ux #task/domain/analysis #task/object/cycle-detection #task/action/overhaul #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交全量变更

我们将所有受影响的文件添加到暂存区并进行最终提交。

~~~~~act
git_add
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/__init__.py
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/cycles.py
packages/stitcher-analysis/src/stitcher/analysis/graph/algorithms.py
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
packages/stitcher-analysis/tests/unit/graph/test_algorithms.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
packages/stitcher-application/tests/unit/runners/check/test_check_runner.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/architecture.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/architecture.json
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(analysis): overhaul architecture check for performance and DX

Completed a comprehensive overhaul of the circular dependency analysis subsystem to handle industrial-scale projects and provide a superior developer experience.

Key technical improvements:
- Algorithmic Optimization: Replaced exhaustive cycle enumeration with a linear-time SCC-based approach combined with Iterative Shortest Cycle Removal (ISCR). This solves the exponential complexity bottleneck in highly coupled graphs.
- New 'algo' Package: Extracted core graph logic into 'stitcher.analysis.graph.algo' for better modularity and future SDK reuse.
- Enhanced Reporting: Implemented a tiered reporting structure. Users now see a global summary of the entangled component (SCC) first, followed by a prioritized roadmap of cycles to break.
- Decoupled Reporter Logic: Refactored the data flow between StitcherApp, CheckRunner, and CheckReporter to separate global architectural issues from per-file consistency checks, eliminating redundant output.
- Fixed Unit Tests: Updated the test suite to align with the new structured algorithm returns and the revamped reporter interface.
- UI/I18N: Refined English and Chinese message templates to clearly display priority indices and component summaries.

This refactor ensures 'stitcher check' is both highly performant and highly actionable.
~~~~~

### 下一步建议

- **功能验证**: 建议在 `Cascade` 项目中重新运行一次全量的 `stitcher check`，享受秒级反馈和清晰的修复路线图。
- **文档沉淀**: 将 ISCR 算法的设计思想记录在开发文档中，作为未来算法扩展的参考。
- **持续观测**: 关注算法在更极端拓扑结构下的表现，根据需要微调启发式规则。
