好的，我们已经成功消除了系统中最后一处“MVP 痕迹”，完成了 `URIGeneratorProtocol` 在 Sidecar 层和重构引擎中的彻底注入，并修复了所有相关的单元测试。

现在，我将把这些收尾工作作为一个完整的逻辑单元进行提交。

## [COMMIT] refactor(sidecar): 完成全系统的 SURI 依赖注入

### 用户需求
彻底消除 `stitcher-lang-sidecar` 和 `DocumentManager` 中硬编码的 `PythonURIGenerator` 实例化逻辑，确保 Sidecar 文件的处理逻辑完全基于协议（Protocol）而非具体实现。

### 评论
这是一次关键的“架构补丁”。通过将 `SidecarAdapter` 和 `SidecarTransformer` 纳入 DI 体系，我们解除了 Sidecar 层对 Python 语言实现的隐式依赖。这不仅使代码更符合依赖倒置原则，也为未来支持多语言项目（如同时包含 Python 和 TypeScript 的仓库）铺平了道路。

### 目标
1.  提交 `SidecarAdapter` 和 `SidecarTransformer` 的 DI 改造。
2.  提交 `DocumentManager` 接收并传递 `uri_generator` 的变更。
3.  提交 `StitcherApp` 中更新后的组件组装逻辑。
4.  提交对 `packages/stitcher-refactor/tests/unit/engine/test_planner.py` 的关键修复，确保 Mock 环境符合新的接口定义。
5.  移除全系统中所有关于 `Phase 3 DI` 的 TODO 注释。

### 基本原理
我们将依赖的“水管”延伸到了系统的最末端。通过构造函数注入，底层组件（如 `SidecarAdapter`）现在不再主动寻找生成器，而是被动接收。这种“控制反转”确保了逻辑定位模型在整个系统中的高度统一和可测试性。

### 标签
#intent/refine #flow/ready #priority/high #scope/core #comp/lang-sidecar #comp/application #comp/refactor #comp/tests #concept/dependency-injection #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 Sidecar 层的 DI 改造

我们将所有受影响的物理文件添加到暂存区。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(sidecar): complete URIGenerator dependency injection

This commit finalizes the Phase 3 DI refactoring by injecting URIGeneratorProtocol 
into the sidecar handling layer and the refactoring planner.

Key changes:
- Refactored `SidecarAdapter` and `SidecarTransformer` to receive `uri_generator` via constructor.
- Updated `DocumentManager` to orchestrate the dependency flow to the adapter.
- Fixed a remaining unit test failure in `test_planner.py` by providing the missing `uri_generator` to the mock RefactorContext.
- Removed all obsolete "TODO: Phase 3" comments related to temporary generator instantiation.

With this change, the Resource Addressing Model (SURI) is now consistently 
injected across all layers, from language adapters to sidecar persistence 
and high-level refactoring operations.
~~~~~

### 下一步建议

我们已经夯实了依赖注入的基础。基于之前的架构分析，建议立即转向解决系统稳定性的下一个核心隐患：

*   **增强 Workspace 确定性 (P1)**: 
    *   **文件**: `packages/stitcher-workspace/src/stitcher/workspace/workspace.py`
    *   **行动**: 修改 `find_workspace_root`。目前它在找不到根目录时会静默回退到当前目录（`start_path`），这会导致不稳定的 SURI 生成（因为基准点变了）。
    *   **目标**: 强制要求必须在有效的 Workspace（包含 `.git` 或特定的 `pyproject.toml`）中运行。如果找不到，抛出 `WorkspaceNotFoundError`。

如果你准备好进行下一步，请告诉我，我将为你生成实施计划。
