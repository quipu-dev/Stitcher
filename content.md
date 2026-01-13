很好，我们已经完成了依赖注入（DI）重构的闭环，修复了生产代码中的关键 Bug 并同步更新了整个测试套件。

现在，我将把这些变更作为一个完整的逻辑单元进行提交。

## [COMMIT] refactor(core): 实现 SURI 生成的依赖注入

### 用户需求
完成 `URIGeneratorProtocol` 的依赖注入改造，确保整个系统（包括测试套件）遵循新的架构契约，并消除硬编码的依赖关系。

### 评论
这是一次深度的架构重构。通过将 `uri_generator` 的生命周期管理移至组合根（`StitcherApp`），我们不仅解决了组件间的强耦合问题，还修复了 `RefactorRunner` 在重构过程中因 re-indexing 失败而导致的生产 Bug。现在的系统更加模块化，也为未来支持 Python 以外的语言做好了准备。

### 目标
1.  提交 `stitcher-spec` 中新增的 `URIGeneratorProtocol`。
2.  提交 `stitcher-lang-python` 中更新后的 `PythonURIGenerator`。
3.  提交 `stitcher-application` 中经过 DI 改造的 `StitcherApp` 和各 Runner 逻辑。
4.  提交 `stitcher-refactor` 中更新后的 `RefactorContext` 及其广泛的测试修复。
5.  提交 `stitcher-test-utils` 和其他包中同步更新的测试辅助工具。

### 基本原理
我们遵循了“显式优于隐式”的原则，将组件所需的依赖通过构造函数明确定义。这种方式虽然导致了测试代码的大面积修改，但其带来的类型安全和可测试性提升是巨大的。

### 标签
#intent/refine #flow/ready #priority/critical #scope/core #comp/application #comp/refactor #comp/lang-python #comp/spec #comp/tests #concept/dependency-injection #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有受影响的包添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-spec
packages/stitcher-lang-python
packages/stitcher-application
packages/stitcher-refactor
packages/stitcher-test-utils
packages/stitcher-index
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): implement dependency injection for SURI generation

This major refactoring moves the SURI generation logic from hardcoded, 
on-the-fly instantiations to a formal protocol-based Dependency Injection (DI) model.

Key changes:
- Defined `URIGeneratorProtocol` in `stitcher-spec` to decouple URI generation from specific implementations.
- Updated `PythonURIGenerator` to implement the protocol.
- Centralized instantiation in `StitcherApp` (Composition Root) and propagated the instance down to Runners, SubjectAdapters, and RefactorContext.
- Fixed a critical production bug in `RefactorRunner` where incremental re-indexing would crash due to missing dependency initialization.
- Systematically updated the entire test suite (unit and integration tests) to comply with the new constructor signatures and interface requirements.

This change eliminates structural technical debt, enhances testability, and provides the architectural foundation for supporting multi-language SURI schemes in the future.
~~~~~

### 下一步建议

既然我们已经夯实了依赖注入的基础，建议接下来的行动方向如下：

1.  **增强 Workspace 确定性 (P1)**: 修改 `packages/stitcher-workspace/src/stitcher/workspace/workspace.py`。
    *   **现状**: `find_workspace_root` 在找不到根目录时会静默回退到当前目录，这会导致不稳定的 SURI 生成。
    *   **行动**: 强制要求必须在有效的 Workspace（包含 `.git` 或特定的 `pyproject.toml`）中运行。如果找不到，抛出 `WorkspaceNotFoundError`。这将确保坐标系的绝对稳定性。

2.  **完善 Python CST 解析 (P1)**: 增强 `IRBuildingVisitor` 对 `Tuple assignment` (如 `x, y = 1, 2`) 的支持。目前这部分被跳过了，导致部分公共 API 无法被索引。

我建议立即开始 **P1: 增强 Workspace 确定性**。如果你准备好了，请告诉我。
