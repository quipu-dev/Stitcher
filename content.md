这是一个逻辑完整的工作单元，我们完成了从 IR 定义到数据库存储的全链路“高保真”升级，彻底解决了符号位置精确度这一核心技术债务。

我将生成一个 `[COMMIT]` 计划，将这些变更持久化到 Git 仓库中。

## [COMMIT] feat: 实现高保真符号位置追踪与数据库 Schema 迁移

### 用户需求
记录并提交针对“符号位置精确度”债务的修复工作，包括 IR 模型扩展、解析器增强、数据库 Schema 迁移以及相关的 Bug 修复和测试更新。

### 评论
这次提交标志着 `stitcher-python` 索引系统从“原型阶段”向“工业级阶段”的跨越。我们现在不仅能知道“代码里有什么”，还能精确地知道“它们在哪里”。这种精度对于后续实现 IDE 集成（如 LSIF/SCIP 支持）至关重要。

### 目标
1.  将所有修改过的源码、配置和测试文件添加到 Git 暂存区。
2.  创建一个详尽的提交说明，记录这一重大的架构演进。

### 基本原理
遵循 Conventional Commits 规范，将此次变更标记为 `feat`，因为它为系统引入了精确空间定位的新能力，同时也包含了对现有不完善实现的重构 (`refactor`)。

### 标签
#intent/tooling #flow/ready #priority/medium
#comp/interfaces #comp/analysis #comp/index #comp/adapters #comp/tests
#concept/history #concept/state
#ai/instruct
#task/domain/tooling #task/object/git-commit #task/action/record
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交还债成果

我们将所有涉及到的包（spec, analysis, index, adapter）以及根目录的变更进行统一提交。

~~~~~act
git_add
packages/stitcher-spec/src/stitcher/spec/models.py
packages/stitcher-spec/src/stitcher/spec/__init__.py
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
packages/stitcher-index/src/stitcher/index/schema.sql
packages/stitcher-index/src/stitcher/index/types.py
packages/stitcher-index/src/stitcher/index/store.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/serializers.py
packages/stitcher-index/tests/unit/test_scanner.py
packages/stitcher-index/tests/unit/test_store.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(index): implement high-fidelity symbol location tracking and schema migration

This commit settles the 'Data Fidelity Debt' regarding inaccurate symbol locations by implementing a full-stack upgrade from IR models to persistent storage.

Core Changes:
- stitcher-spec: Introduced `SourceLocation` model and integrated it into `FunctionDef`, `ClassDef`, and `Attribute`.
- stitcher-python-analysis: 
    - Enhanced `IRBuildingVisitor` (LibCST) to extract line/column offsets using `PositionProvider`.
    - Updated `GriffePythonParser` to capture line information from Griffe objects.
- stitcher-index: 
    - Migrated Database Schema (v1.1) to support precise (line, col) -> (end_line, end_col) coordinates for both symbols and references.
    - Updated `SymbolRecord` and `ReferenceRecord` types to match the new schema.
    - Updated `IndexStore` insertion logic.
- stitcher-python-adapter: 
    - Updated `PythonAdapter` to map `SourceLocation` metadata to index records, replacing hardcoded placeholders.

Bug Fixes & Refinement:
- Fixed missing `SourceLocation` export in `stitcher.spec`.
- Fixed multiple Pyright type errors in `store.py`, `serializers.py`, and `index_adapter.py`.
- Updated index test suite to align with the new schema.

This infrastructure upgrade enables future precision-critical features like "Jump to Definition", hover tooltips, and AST-based refactorings.
~~~~~

### 下一步建议
我们已经拥有了坚实的数据地基，下一步可以专注于增强索引的“连接性”：
- **实现引用分析 (Debt 1.2)**: 完善 `UsageScanVisitor` 并打通 `PythonAdapter._extract_references`，将索引从“定义表”升级为“语义图谱”。
- **错误透明化 (Debt 2.1)**: 将解析过程中的异常持久化到 `indexing_errors` 表中，提升系统的鲁棒性和可观测性。
