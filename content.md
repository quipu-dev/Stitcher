好的，重构的第一阶段已经圆满完成。我们已经成功建立了自动索引机制，并将 `SignatureManager` 转型为纯粹的存储服务。现在是时候将这些基础性的重构成果正式提交到版本库了。

## [COMMIT] refactor: 解耦 SignatureManager 并集成自动索引机制

### 用户需求
按照 2.0 路线图，重构 `stitcher-application` 的核心流程：实现索引自动更新，并完成 `SignatureManager` 的职责分离。

### 评论
这是一次深层的架构调整。通过将“状态存储”与“逻辑计算”分离，我们为实现极速的、基于查询的语义检查打下了坚实的地基。虽然目前指纹计算暂时下放到了 Runners，但这仅仅是过渡状态，最终它们都将被索引查询所取代。

### 目标
1.  **自动索引**: 使 `StitcherApp` 在执行任何核心业务逻辑前自动确保索引是最新的。
2.  **职责分离**: `SignatureManager` 现在的唯一职责是管理 `.json` 基线文件的持久化。
3.  **单元测试恢复**: 修复并重构了所有受影响的测试用例，确保测试套件在新的架构下依然稳健。

### 基本原理
我们遵循了“显式由于隐式”和“职责单一”的原则。通过在 `StitcherApp` 这一层统一调度索引刷新，我们保证了系统状态的确定性。而 `SignatureManager` 的简化则移除了由于过度封装带来的认知负担，使其 API 变得更加纯粹（输入路径，得到哈希）。

### 标签
#intent/refactor #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/app #task/object/stitcher-app #task/action/integrate-index #task/state/end

---

### Script

#### Acts 1: 提交重构成果

我们将把所有涉及核心逻辑和测试修复的变更添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-application/src/stitcher/app/runners/check.py
packages/stitcher-application/src/stitcher/app/runners/init.py
packages/stitcher-application/src/stitcher/app/runners/pump.py
packages/stitcher-application/tests/unit/test_execution_planner.py
packages/stitcher-application/tests/unit/test_signature_extraction.py
packages/stitcher-application/tests/unit/test_signature_manager.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(app): decouple SignatureManager and integrate auto-indexing

- Implemented `StitcherApp.ensure_index_fresh()` and integrated it as a mandatory pre-step for all core commands (check, pump, generate, etc.).
- Refactored `SignatureManager` into a lightweight I/O service, removing AST dependencies and fingerprint calculation logic.
- Relocated fingerprint calculation logic to `CheckRunner`, `InitRunner`, and `PumpRunner` as a transitional step.
- Updated all affected unit tests to align with the new SignatureManager and Runner APIs.
- Verified test suite passes (214 passed).

This change establishes the foundation for the upcoming "Query-First" refactoring of the Check and Pump operations.
~~~~~

### 下一步建议
地基已经打好。接下来的宏观任务非常明确：

**实现 "Query-First" 检查模式**。

我们将彻底改造 `CheckRunner`。它将不再调用昂贵的 `_compute_fingerprints`（即不再需要实时解析 AST），而是通过 `IndexStore` 直接从 SQLite 数据库中提取新鲜的指纹，并与 `SignatureManager` 加载的基线进行内存对比。这将使 `stitcher check` 的运行速度实现跨越式的提升。
