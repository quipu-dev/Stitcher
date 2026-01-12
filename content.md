太棒了。我们已经成功建立了 `application` 与 `analysis` 之间的“钢缆”，并解决了一系列复杂的架构挑战，包括循环依赖、生命周期管理和类型系统的统一。

我将生成一个 `[COMMIT]` 计划，将这些具有里程碑意义的变更正式固化。

## [COMMIT] refactor: 将 ConsistencyEngine 集成到 CheckRunner

### 用户需求
完成 Phase 1 中关于 `check` 命令逻辑的迁移和集成，确保所有集成测试和单元测试通过。

### 评论
这次提交标志着我们将“业务编排”与“领域分析”进行物理分离的战略取得了初步成功。通过引入 `ConsistencyEngine` 并重构违规生命周期，我们不仅使 `CheckRunner` 变得更加精简和纯粹，还为未来引入更复杂的分析逻辑（如基于图的推理）打下了坚实的基础。

### 目标
1.  提交 `stitcher-analysis` 的清理和规则完善。
2.  提交 `Differ` 服务下沉到 `stitcher-common` 的变更。
3.  提交 `CheckRunner` 和 `CheckResolver` 的核心集成代码。
4.  提交相关的测试更新和陈旧代码清理。

### 基本原理
按照 HFEA 协议，我们将这一逻辑完整、状态稳定的工作单元进行提交。此次变更涵盖了从协议层（Spec 指针化）到实现层（服务重定位）再到业务层（生命周期重构）的全面升级。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #comp/analysis #comp/common #concept/architecture #scope/core #ai/instruct #task/domain/storage #task/object/check-lifecycle #task/action/integration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有涉及到的文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/stitcher-application/pyproject.toml
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
packages/stitcher-application/src/stitcher/app/services/__init__.py
packages/stitcher-common/src/stitcher/common/services/differ.py
packages/stitcher-common/src/stitcher/common/services/__init__.py
packages/stitcher-analysis/src/stitcher/analysis/engines/consistency/engine.py
packages/stitcher-analysis/src/stitcher/analysis/rules/consistency/signature.py
packages/stitcher-application/tests/unit/runners/check/test_check_runner.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(app): integrate ConsistencyEngine into CheckRunner

Migrates the core analysis logic of the 'check' command to the new
stitcher-analysis package, achieving a clean separation between
orchestration and rule evaluation.

Core improvements:
- Decoupled logic: CheckRunner now delegates to ConsistencyEngine and 
  translates unified Violation objects into application-specific results.
- Resolved circular dependencies: Moved the Differ utility from 
  stitcher-application to stitcher-common.
- Lifecycle refactoring: Implemented a deferred error reporting model 
  where interactive violations (drifts, conflicts) are managed solely by 
  the Resolver, preventing double-counting and logic gaps.
- Enhanced Resolver: Added support for HYDRATE actions and dynamic 
  error clearing upon successful resolution.
- Protocol alignment: Adapted subject adapters to implement the new 
  AnalysisSubject protocol.
- Cleanup: Removed obsolete CheckAnalyzer and associated stale tests.

This completes the first major integration point of the Analysis Engine.
~~~~~

### 下一步建议
我们已经完成了 Check 链路的重构。下一步建议按照原计划处理 **Phase 1.5: 提取 Pump 逻辑**。

具体的行动点将是：
1.  在 `stitcher-analysis` 中创建 `PumpEngine`。
2.  将 `PumpAnalyzer` 的逻辑（主要是脏文档检测和冲突预判）迁移至引擎。
3.  修改 `PumpRunner` 以使用新引擎。

完成这一步后，`stitcher-application` 中将不再包含任何原生的“分析/判断”代码。
