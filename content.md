好的，我们已经完成了 `CheckRunner` 和 `PumpRunner` 的解耦重构，建立了清晰的依赖注入模式，并修复了相关的测试回归。现在我将生成一个 `[COMMIT]` 计划来提交这些架构改进。

## [COMMIT] refactor: 通过依赖注入和模块化重构实现 Runner 解耦

### 用户需求
用户要求提交最近关于 `CheckRunner` 和 `PumpRunner` 的模块化重构工作。这包括将复杂的逻辑拆分为可注入的子组件，应用依赖注入模式，并修复由此产生的导入和测试错误。

### 评论
这是一次重要的工程实践。通过将“上帝类”式的 Runner 拆分为 `Analyzer`, `Executor`, `Resolver` 等单一职责的组件，我们不仅提升了代码的可读性，更重要的是让单元测试变得真正可行。现在我们可以独立地测试规划逻辑或分析逻辑，而无需依赖完整的 Runner 运行环境。此外，将这些 Runner 移入各自的子包中，也为未来支持多语言（如针对不同语言有不同的 Analyzer）奠定了物理结构基础。

### 目标
1.  提交 `CheckRunner` 的解耦重构，包括新增的 `protocols.py` 和修正后的 `runner.py`, `resolver.py`, `subject.py`。
2.  提交 `PumpRunner` 的模块化拆分，包括新创建的 `pump` 子包及其 `analyzer.py`, `executor.py`, `protocols.py`。
3.  提交 `StitcherApp` 作为组合根（Composition Root）的更新，负责实例化并注入所有依赖。
4.  提交对单元测试 `test_execution_planner.py` 的重构，使其针对新的 `PumpExecutor` 组件运行。

### 基本原理
本阶段重构遵循 **单一职责原则 (SRP)** 和 **依赖倒置原则 (DIP)**。我们通过 **依赖注入 (DI)** 将决策逻辑与执行逻辑分离，并将所有组件的组装工作集中在 `StitcherApp` 中。这消除了 Runner 内部的硬编码，实现了“高内聚、低耦合”的设计目标。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #comp/interfaces #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交解耦重构变更

我们将所有新增、移动和修改的文件添加到 Git 暂存区。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: modularize runners and apply dependency injection

This commit implements a major structural refactoring of the application runners to improve testability and maintainability.

Key changes:
- Decomposed monolithic 'PumpRunner' into 'PumpAnalyzer' and 'PumpExecutor', moving them into a dedicated 'pump' sub-package.
- Refactored 'CheckRunner' to use dependency injection for its internal components (Analyzer, Resolver, Reporter).
- Established 'StitcherApp' as the system's Composition Root, responsible for wiring together all services and runners.
- Introduced explicit protocols for all runner sub-components to ensure strict interface compliance.
- Fixed unit test regressions in 'test_execution_planner.py' by retargeting them to the new 'PumpExecutor' class.
- Resolved circular dependencies and missing types in the 'check' runner's protocol definitions.

These improvements align with Phase 3 of the refactoring roadmap, transitioning the codebase towards a more decoupled and modular architecture.
~~~~~

### 下一步建议
现在应用层的核心解耦已基本完成，我们可以正式进入 **“阶段四：Refactor 引擎泛化”**。首要任务是分析 `stitcher-refactor` 包，提取并抽象其对 Python 语言（LibCST/Griffe）的直接依赖，将其转换为可注入的策略。
