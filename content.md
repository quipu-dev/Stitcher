好的，我们已经成功搭建了 `stitcher-index` 的骨架并实现了核心数据库层。现在我将生成一个 `[COMMIT]` 计划，将这些成果作为一个完整、稳固的逻辑单元提交到版本库中。

## [COMMIT] feat: Initialize stitcher-index package with core database layer

### 用户需求

初始化 `stitcher-index` 包，并实现基于 SQLite WAL 模式的持久化层，作为 Stitcher 2.0 语义索引的基石。

### 评论

这是 Stitcher 从“即时工具”向“知识平台”演进的第一个实体步骤。通过引入 URI 风格的标识符规范和支持别名（Alias）的图谱模型，我们从根本上解决了 Monorepo 多语言环境下的实体识别难题。

### 目标

1.  将 `stitcher-index` 包的所有源文件、配置和测试用例添加到 Git 暂存区。
2.  更新根目录及相关包的 `pyproject.toml` 以完成依赖集成。
3.  创建一个详细的 Git Commit 记录此次架构演进。

### 基本原理

此次提交包含了物理结构、配置定义、数据模型（Schema v1.0）以及经过验证的存储逻辑（IndexStore）。这为后续的扫描流水线（Scanner）和查询服务（Query Service）提供了确定的、类型安全的物理边界。

### 标签

#intent/architect #intent/build #flow/done #priority/high #comp/engine #comp/build #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/stitcher-index #task/action/integration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有相关变更打包提交。

~~~~~act
git_add
packages/stitcher-index
packages/stitcher-application/pyproject.toml
packages/stitcher-refactor/pyproject.toml
pyproject.toml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: Initialize stitcher-index package with core database layer

This commit marks the beginning of the Stitcher 2.0 architecture (The Semantic Hub).
It introduces the 'stitcher-index' package, designed to maintain a persistent
knowledge graph of project assets using a high-performance SQLite backend.

Key features implemented:
- **SURI (Stitcher URI) Specification**: A globally unique, human-readable
  identifier scheme (`py://<path>#<fragment>`) to handle symbols across 
  multi-language monorepos.
- **Database Schema v1.0**: A normalized relational schema supporting file 
  tracking (SHA256 based), symbol definitions, aliases, and directional 
  references (usages).
- **IndexStore & DatabaseManager**: Thread-safe (WAL mode) persistence layer 
  with atomic 'update_analysis' capabilities and transaction-aware CRUD ops.
- **Monorepo Integration**: Fully integrated into the project workspace (uv, 
  pytest, pyright) and added as a dependency to core application packages.

This foundation enables incremental scanning and sub-second global queries 
in future iterations.
~~~~~

### 下一步建议

随着数据库层的稳定，下一步我们将进入 **任务 1.3: 增量扫描流水线** 的开发。

我们将构建 `WorkspaceScanner`，其核心目标是实现“由轻到重”的四阶段过滤逻辑：
1.  **Git Discovery**: 瞬时识别待处理文件。
2.  **Stat Filtering**: 利用 `mtime` 排除 90% 以上未变动文件。
3.  **Hash Verification**: 确认内容是否真实变化。
4.  **Language Analysis**: 仅对确认脏（Dirty）的文件调用 AST 解析器。

如果你准备好开始扫描器的设计，请告诉我。
