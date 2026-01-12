好的，我们开始执行清理工作。

我将删除 `stitcher-analysis` 包中已废弃的、基于字符串 ID 和 Enum 的 Violation 定义及相关的规则文件。这确保了该包内部只存在一套统一的、基于 `SemanticPointer` 的分析契约。

## [WIP] chore: 清理 stitcher-analysis 中的死代码

### 用户需求

根据上一份分析报告，需要从 `stitcher-analysis` 包中删除代表“模式 B”（遗留/冲突实现）的死代码文件，以消除架构分歧。

### 评论

这是一个关键的“架构卫生”步骤。根据 HFEA 的“不可腐蚀性”原则，任何已知的架构异味都必须立即被清除。删除这些废弃文件可以防止未来的开发人员感到困惑，并确保 `stitcher-analysis` 包只提供一套清晰、一致的接口。

### 目标

1.  删除旧的 `Violation` 定义文件 (`violations.py`)。
2.  删除旧的、基于 `SymbolRule` 的规则实现文件 (`docstring.py`)。
3.  删除旧的规则基类定义文件 (`base.py`)。

### 基本原理

通过直接删除这些文件，我们可以以最小的成本消除代码库中的实现分歧。这些文件代表了一个已被 `SemanticPointer` 方案完全取代的早期设计，保留它们没有任何价值，只会增加技术债务。

### 标签

#intent/refine #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/testing #task/object/code-hygiene #task/action/cleanup #task/state/begin

---

### Script

#### Acts 1: 删除废弃的 Schema 和规则文件

我们将依次删除 `schema/violations.py`、`rules/consistency/docstring.py` 和 `rules/base.py`。

~~~~~act
delete_file
packages/stitcher-analysis/src/stitcher/analysis/schema/violations.py
~~~~~

~~~~~act
delete_file
packages/stitcher-analysis/src/stitcher/analysis/rules/consistency/docstring.py
~~~~~

~~~~~act
delete_file
packages/stitcher-analysis/src/stitcher/analysis/rules/base.py
~~~~~

### 下一步建议

代码库清理完成后，`stitcher-analysis` 的内部结构现在是一致的了。

根据我们修正后的计划，下一步是**提取 Pump 逻辑**。我将准备一个计划，将 `stitcher.app.runners.pump.analyzer.PumpAnalyzer` 的逻辑迁移到 `stitcher-analysis` 包中，并将其封装为一个新的 `PumpEngine`。
