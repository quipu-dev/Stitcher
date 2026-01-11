好的，我们已经顺利完成了这一阶段庞大且关键的架构迁移。这是一个里程碑式的进展，Stitcher 2.0 的“语义中枢”与“重构引擎”终于在物理和逻辑上实现了闭环。

我将生成一个 `[COMMIT]` 计划，将这些涵盖了包拆分、职责合并以及重构引擎升级的变更正式提交到仓库。

## [COMMIT] refactor(arch): 统一工作区发现机制并打通索引与重构引擎

### 用户需求
需要将 `Workspace` 概念从 `stitcher-refactor` 剥离为独立的核心包，消除职责重复（合并 `WorkspaceScanner`），并让重构引擎（`SemanticGraph`）转向基于 `IndexStore` 的确定性查询。

### 评论
这是一次深度的“架构债务偿还”与“能力升级”的联合行动。通过提取 `stitcher-workspace`，我们解决了核心组件间的循环依赖和依赖倒置问题。更重要的是，重构引擎现在从“临时性的启发式扫描”转向了“持久性的索引查询”，这为未来处理百万行级代码库的即时重构奠定了坚实基础。

### 目标
1.  正式提交新创建的 `stitcher-workspace` 包及其发现逻辑。
2.  记录 `WorkspaceScanner` 到 `FileIndexer` 的更名及职责缩减。
3.  记录 `RefactorRunner` 和 `SemanticGraph` 接入 `IndexStore` 的 API 变更。
4.  保存所有为了适配新架构而进行的广泛测试套件更新。

### 基本原理
按照 Stitcher 2.0 路线图，我们必须建立单一事实来源 (SSoT)。
- **物理层面**：`Workspace` 成为所有组件理解项目布局的唯一入口。
- **逻辑层面**：`IndexStore` 成为所有组件理解符号关系的唯一入口。
本次提交标志着这两个入口在全系统范围内被确立并接管了原有的碎片化逻辑。同时，通过在重构查询中包含定义点，我们彻底解决了“只重命名引用，不重命名定义”的长期缺陷。

### 标签
#intent/refine #flow/ready #priority/critical 
#comp/engine #comp/refactor #comp/index #comp/workspace 
#concept/state #concept/history #scope/core #scope/api 
#ai/brainstorm
#task/domain/architecture
#task/object/workspace-and-index-integration
#task/action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交架构演进变更

我们将暂存区中的所有变更提交到 Git。这些变更已经过一系列 WIP 计划的验证和测试适配。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): centralize workspace discovery and integrate index with refactor engine

This commit represents a major structural evolution of Stitcher, achieving the "Semantic Hub" integration and addressing deep architectural debt regarding project structure awareness.

Key Changes:
1.  **Extraction of 'stitcher-workspace'**: Created a dedicated package to handle project layout analysis, pyproject.toml parsing, and file discovery. This resolves a critical dependency inversion where 'stitcher-application' previously relied on 'stitcher-refactor'.
2.  **Consolidated Discovery**: Merged the file discovery logic from 'stitcher-index' (previously 'WorkspaceScanner') into the 'Workspace' service. 'Workspace' is now the Single Source of Truth for "what files exist in the project", supporting both Git and OS-walk strategies.
3.  **Renamed 'WorkspaceScanner' to 'FileIndexer'**: Clarified the component's responsibility. It no longer "scans" the filesystem for paths; it receives a set of paths and "indexes" their semantic content.
4.  **Deterministic Refactoring**:
    - 'SemanticGraph' now accepts an 'IndexStore' and relies on it for all cross-reference queries.
    - Replaced 'graph.registry' (heuristic in-memory scan) with 'graph.find_usages()', which performs persistent SQLite queries.
    - Enhanced 'find_usages' to explicitly include the symbol's definition point, ensuring 'RenameSymbolOperation' updates both the definition and its references.
5.  **Workspace-Aware Adapters**: Updated 'PythonAdapter' to accept 'search_paths'. It now uses these paths to determine the correct logical FQN for files in monorepo structures, ensuring correct SURI generation.
6.  **Test Suite Overhaul**: Updated over 40 integration and unit tests to accommodate the new 'IndexStore' dependency and the shift to the 'stitcher-workspace' API.
7.  **Signature Updates**: Reflected the broad API changes in the Stitcher signature metadata.
~~~~~

### 下一步建议
- **执行一次全量索引构建**: 建议运行 `stitcher index:build`（如果该命令已就绪）或通过脚本调用 `IndexRunner` 以确保本地索引数据库与最新的架构代码同步。
- **压力测试**: 在一个真实的大型 Monorepo 上运行 `stitcher refactor` 以验证 `find_usages` 在数据库量级增加时的性能表现。
- **架构审计**: 检查是否还有残留的 `griffe` 直接加载逻辑可以被 `IndexStore` 查询进一步替代。
