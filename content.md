太棒了！测试通过意味着这一核心架构变迁已经稳健落地。

现在，我们将把这些改进作为一个逻辑完整单元正式提交。

## [COMMIT] refactor(app): 迁移覆盖率 runner 以使用语义索引

### 用户需求
将 `stitcher cov` 命令的底层实现从实时的 AST 解析迁移到基于语义索引的查询，以实现更高的性能。

### 评论
这是一次非常成功的“瘦身”重构。通过将 `cov` 的数据源从 `ModuleDef` (AST) 切换到 `IndexStore` (数据库)，我们不仅大幅降低了命令的运行成本，还进一步巩固了索引作为项目结构“单一事实来源”的地位。

### 目标
1.  正式提交对 `CoverageRunner` 的重构。
2.  正式提交对 `StitcherApp` 流程的优化。
3.  确保 Git 历史中清晰地记录了这一架构演进。

### 基本原理
我们通过在 `StitcherApp` 层面拦截文件流，并让 `CoverageRunner` 直接从已刷新的索引中获取符号元数据，成功实现了从“计算驱动”到“查询驱动”的转变。这种模式是大型工具链走向工业级稳定性和性能的必经之路。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/engine #concept/state #scope/core #scope/dx #ai/instruct #task/domain/testing #task/object/coverage #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及到的修改（application 包中的核心逻辑和 runner 实现）添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/runners/coverage.py
packages/stitcher-application/src/stitcher/app/core.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(app): migrate coverage runner to use semantic index

Refactored the CoverageRunner and StitcherApp.run_cov() to utilize the
persistent semantic index instead of performing full AST parsing for
every run.

- Updated CoverageRunner to accept and query IndexStore.
- Modified _analyze_path_coverage to derive visibility and symbol
  status directly from indexed symbol records.
- Updated StitcherApp.run_cov to bypass expensive scanner-based
  AST generation, moving from CPU-bound parsing to I/O-bound
  database queries.

This change significantly improves performance for coverage reports,
especially in large codebases.
~~~~~

### 下一步建议
- **重构 generate 命令**: 既然 `cov` 已成功，建议下一步对 `generate` (存根生成) 进行类似的重构，尝试在不解析源文件的情况下生成 `.pyi`。
- **缓存策略优化**: 随着越来越多的命令依赖索引，可以考虑在 `StitcherApp` 中引入更细粒度的“索引状态检查”，避免在连续运行多个只读命令时重复调用 `ensure_index_fresh`。
