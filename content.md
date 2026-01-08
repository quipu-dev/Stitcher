好的，重构工作已经圆满完成。我们通过将样板逻辑上浮到 `StitcherApp`，显著提升了系统的内聚性，并确保了所有测试均在新的架构下通过。

我将生成一个 `[COMMIT]` 计划来提交这些变更。

## [COMMIT] refactor(app): 将 Runner 执行与配置/扫描逻辑解耦

### 用户需求
完成 Runner 架构的重构，将配置加载、服务初始化和文件扫描职责移至 `StitcherApp`，使 Runner 成为纯粹的数据执行器。

### 评论
这次重构极大地简化了系统的执行流，消除了大量的样板代码，并为未来支持多风格文档（Google/NumPy 风格）提供了统一的策略注入点。同时，修复了由于 API 变更导致的整个测试套件的失败。

### 目标
1.  提交所有重构后的 Runner 实现。
2.  提交更新后的 `StitcherApp` 编排逻辑。
3.  提交所有修复后的单元测试和集成测试。

### 基本原理
我们通过“控制反转”模式，让 `StitcherApp` 负责环境准备，Runner 负责核心算法。这种解耦提高了代码的重用性，并使得各个组件的职责更加单一、清晰。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #concept/executor #scope/core #ai/brainstorm #task/domain/architecture #task/object/runners #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交架构重构与测试修复

我们将所有变更添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/runners/check.py
packages/stitcher-application/src/stitcher/app/runners/generate.py
packages/stitcher-application/src/stitcher/app/runners/init.py
packages/stitcher-application/src/stitcher/app/runners/pump.py
packages/stitcher-application/src/stitcher/app/runners/coverage.py
packages/stitcher-application/src/stitcher/app/runners/transform.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/tests/unit/test_execution_planner.py
packages/stitcher-application/tests/integration/test_end_to_end.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(app): decouple runner execution from configuration and scanning

Refactored the Runner architecture to follow the Inversion of Control (IoC) principle. Previously, each Runner was responsible for loading its own configuration and performing its own file scanning, leading to duplicated logic and difficulty in injecting centralized service strategies.

Key changes:
- StitcherApp: Now acts as the central orchestrator, handling config loading, service strategy configuration, and file scanning. It passes prepared ModuleDef lists and StitcherConfig objects to the Runners.
- Runners: Transitioned all Runners (Check, Pump, Generate, etc.) to use 'batch' processing methods (e.g., run_batch, analyze_batch). They are now pure executors of business logic.
- Service Strategy: Prepared the ground for dynamic docstring style support by centralizing service configuration within StitcherApp.
- Tests: Updated all integration and unit tests to align with the new constructor signatures and API patterns, restoring the test suite to a healthy state.

This refactoring simplifies the system's execution pipeline and significantly improves maintainability and testability.
~~~~~

### 下一步建议

架构地基已经重新加固，现在我们可以回到最初的目标：**实施阶段 2 - 核心解耦与集成**。

具体的下一步任务将是：
1.  在 `StitcherApp` 的 `_configure_and_scan` 方法中，根据配置注入正确的 `DocstringSerializer`。
2.  修改 `DocumentManager` 以支持通过注入的 Serializer 处理结构化文档。
3.  更新 Hash 计算逻辑以支持结构化数据的规范化 Hash。
