太棒了。既然所有测试都已通过，这标志着我们的基础架构调整和结构拆分已经达到了稳定状态。我们将把“索引升级（存储 Docstring）”和“CheckRunner 模块化”这两个关键步骤作为一个完整的逻辑单元提交。

这不仅是代码的迁移，更是为我们即将实现的“全量索引检测（Zero-IO Check）”清理出了一个干净的战场。

## [COMMIT] refactor: 升级索引以存储文档内容并模块化 CheckRunner

### 用户需求

1.  在索引中存储原始 Docstring 内容，以消除对源码文件的重复读取。
2.  在实施新逻辑前，先对 `CheckRunner` 进行物理拆分，解决“面条代码”带来的维护性挑战。

### 评论

这次提交奠定了新一代 Check 流程的基石。通过将 Docstring 内容直接纳入索引体系，我们将索引从“元数据仓库”升级为了“高保真代码镜像”。同时，`CheckRunner` 的拆分将分析（Analyzer）、解决（Resolver）和报告（Reporter）职责彻底分离，极大降低了后续逻辑重构的风险。

### 目标

1.  **索引升级**：
    *   在 SQLite `symbols` 表中添加 `docstring_content` 字段。
    *   在 `PythonAdapter` 中增加 Docstring 文本的实时采集。
2.  **CheckRunner 模块化**：
    *   将单一的 `check.py` 拆分为 `analyzer.py` (分析)、`resolver.py` (冲突处理)、`reporter.py` (输出) 和 `runner.py` (外观类)。
    *   确保对外接口（`StitcherApp` 调用的方法签名）保持不变。

### 基本原理

遵循“单一职责原则 (SRP)”和“显式状态管理”。索引现在包含了进行一致性检查所需的所有原材料（Hash + Content），这使得 `Analyzer` 可以在不触碰 `.py` 文件的情况下完成全部判定工作，极大提升了大型项目的扫描效率。

### 标签

#intent/refine #flow/ready #priority/high #comp/index #comp/application #scope/core #task/domain/storage #task/object/check-runner #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加更改到暂存区

我们将包含索引升级和 CheckRunner 拆分的所有相关文件添加到 Git。

~~~~~act
git_add
packages/stitcher-index/src/stitcher/index/schema.sql
packages/stitcher-index/src/stitcher/index/types.py
packages/stitcher-index/src/stitcher/index/store.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
packages/stitcher-application/src/stitcher/app/runners/check/analyzer.py
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
packages/stitcher-application/src/stitcher/app/runners/check/__init__.py
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~

#### Acts 2: 创建原子提交

执行最终的提交操作。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: store docstrings in index and modularize CheckRunner

This commit implements two major architectural improvements:

1. Index Enhancement:
   - Added `docstring_content` column to the `symbols` table in SQLite.
   - Updated `PythonAdapter` to capture raw docstring text during indexing.
   - Updated `IndexStore` and `SymbolRecord` to support the new field.
   This allows downstream tools to perform content-based checks (like generating diffs) without re-parsing the source files.

2. CheckRunner Decomposition:
   - Decomposed the bloated `check.py` into a modular package:
     - `analyzer.py`: Pure logic for detecting inconsistencies using hashes.
     - `resolver.py`: Handles interactive/non-interactive resolutions and state updates.
     - `reporter.py`: Manages the output to the FeedbackBus.
     - `runner.py`: A clean Facade class coordinating the sub-components.
   - This isolation of concerns simplifies the upcoming implementation of the "Index-First" detection logic.
~~~~~

### 下一步建议

现在基础架构和物理结构都已经就绪，我们可以直接进入核心战斗：**重写 `CheckAnalyzer` 以实现 Zero-IO 检测。**

在下一个计划中，我建议：
1.  **修改 `CheckAnalyzer`**：将其逻辑改为：
    *   从 `IndexStore` 获取指定文件的所有符号。
    *   从 YAML 加载该文件的文档映射。
    *   通过对比 `symbols.docstring_hash` 和 `yaml.hash` 进行状态判定。
    *   仅在 `Conflict` 时，直接利用 `symbols.docstring_content` 生成 Diff。
2.  **优化启动速度**：既然 Analyzer 不再需要 `ModuleDef`，我们将修改 `StitcherApp.run_check` 的顶层循环，避免在检测阶段预解析 AST。

如果您准备好了，请告知我，我将生成该核心逻辑重写的计划。
