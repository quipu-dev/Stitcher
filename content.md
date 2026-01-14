好的，我们已经完成了 `DocumentManager` 的迁移及所有相关导入路径的更新。现在是时候将这些改动作为一个完整的逻辑单元进行提交了。

这将标志着我们第一个宏观重构任务的圆满结束。

## [COMMIT] refactor(arch): Relocate DocumentManager to stitcher-lang-sidecar

### 用户需求

根据架构设计，将 `DocumentManager` 及其相关的 `DocstringMerger` 从 `stitcher-application` 迁移至 `stitcher-lang-sidecar` 包，并更新全量代码库中的引用路径。

### 评论

这次重构完成了关键的职责解耦。通过将 Sidecar 文件的管理权移交给专门的语言包，我们不仅提高了代码的内聚性，还为后续在索引层面通过“Zero-IO Path”优化检查性能扫清了障碍。

### 目标

1.  将改动涉及的所有文件（包括源文件、配置文件和测试文件）添加到 Git 暂存区。
2.  创建一个符合 Conventional Commits 规范的提交，记录这次重大的架构重定位。

### 基本原理

本计划是一个 `[COMMIT]` 计划，其唯一目的是将已经验证（或准备验证）的原子变更集固化到版本控制系统中。根据 **HFEA 真理单一来源原则**，这一步确保了我们的物理实现与逻辑架构模型保持同步。

### 标签

#intent/refine #flow/ready #priority/high 
#comp/application #comp/lang-sidecar #comp/stubgen #concept/dependency #scope/core
#ai/instruct 
#task/domain/architecture #task/object/component-relocation #task/action/refactor 
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加所有变更文件到暂存区

我们将把此次重构涉及的所有文件添加到 Git 暂存区。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/services/doc_manager.py
packages/stitcher-application/src/stitcher/services/merger.py
packages/stitcher-application/src/stitcher/services/__init__.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/pyproject.toml
packages/stitcher-application/tests/unit/test_execution_planner.py
packages/stitcher-application/tests/unit/test_docstring_hybrid.py
packages/stitcher-application/tests/unit/test_doc_manager_strategies.py
packages/stitcher-application/tests/unit/test_doc_manager.py
packages/stitcher-application/tests/unit/test_doc_overlay.py
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/merger.py
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/__init__.py
packages/stitcher-stubgen/src/stitcher/stubgen/runners.py
packages/stitcher-stubgen/src/stitcher/stubgen/__init__.py
~~~~~

#### Acts 2: 创建 Git 提交

执行正式提交，详细说明此次架构重构的内容。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): relocate DocumentManager to stitcher-lang-sidecar

Relocated the DocumentManager and DocstringMerger components from the application layer (stitcher-application) to the sidecar-specific language package (stitcher-lang-sidecar).

This move consolidates all Sidecar file lifecycle management logic within its natural domain, enabling better encapsulation and future indexing optimizations.

Key changes:
- Moved 'doc_manager.py' (renamed to 'manager.py') and 'merger.py' to stitcher-lang-sidecar.
- Updated 'stitcher-application' to explicitly depend on 'stitcher-lang-sidecar'.
- Corrected all import paths in 'StitcherApp', 'StubgenService', and the entire test suite.
- Updated package exports in respective __init__.py files.

This refactor is a prerequisite for introducing index-driven incremental loading for Sidecar files.
~~~~~

### 下一步建议

随着组件迁移的完成，我们现在已经准备好处理**性能挑战**了。

接下来的宏观任务是 **“引入索引驱动的 Sidecar 增量加载”**。我建议按照以下步骤进行：

1.  **数据库 Schema 扩展**：首先在 `stitcher-index` 包中增加 `doc_entries` 表，以便持久化 Sidecar 文件的摘要和 IR 数据。
2.  **实现 Sidecar 索引器**：在 `stitcher-lang-sidecar` 中实现 `LanguageAdapter` 接口，让索引系统能够“看懂”并索引 `.stitcher.yaml` 文件。

如果你准备好了，我们可以先从修改 `schema.sql` 开始。
