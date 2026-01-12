好的，我们立即执行清理工作。

根据你的指示，我们将采用“受控拆除”策略：通过直接删除遗留代码来强制暴露测试套件和其他隐藏的依赖项。这是一个激进但必要的步骤，旨在彻底清除架构中的兼容性债务。

## [WIP] refactor(app): 移除 check 命令遗留的数据模型和协议

### 用户需求

系统在 `stitcher-application` 包内维护了多个与 `check` 功能相关的遗留数据模型和协议（`app.types.FileCheckResult`, `app.runners.check.protocols.py`）。这些定义是 `stitcher-analysis` 中现代数据模型的冗余副本，构成了必须被移除的技术债务。

本次任务的目标是物理删除这些遗留文件和类定义，以暴露并强制更新所有仍然依赖于它们的组件，特别是测试套件。

### 评论

这是一个典型的“架构债偿还”操作。我们正在故意破坏向后兼容性，以达成更高级别的架构纯净度。删除这些冗余的定义将：
1.  **暴露隐藏的依赖**: 测试用例是这些旧契约的最后“堡垒”。删除它们将立即导致测试失败，从而为我们提供一个清晰的、必须修复的“待办事项列表”。
2.  **强制架构统一**: 迫使所有代码（包括测试代码）都转向使用 `stitcher-analysis` 提供的单一、权威的数据模型。
3.  **遵循 HFEA 原则**: 严格遵守“真理单一来源 (SSoT)”原则，消除任何形式的冗余信息维持。我们是在拆除脚手架，以展现建筑的真实结构。

### 目标

1.  从 `stitcher.app.types` 中删除遗留的、基于字典的 `FileCheckResult` 类。
2.  删除整个 `stitcher.app.runners.check.protocols.py` 文件，该文件包含了 `SymbolState` 的影子副本以及基于旧数据模型的协议。
3.  为下一阶段的“测试修复”工作奠定基础。

### 基本原理

根据“回归驱动开发”和“激进重演逻辑”的原则，当底层架构发生重大演进时，测试套件必须随之演进。通过删除旧的实现，我们利用了编译器和测试运行器作为静态和动态的分析工具，来精确地定位所有需要更新的代码点。这是一个比手动搜索和替换更高效、更彻底的策略，确保了没有任何角落被遗漏。

### 标签

#intent/refine #flow/ready #priority/high #comp/app #comp/tests #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 移除遗留的数据模型

我们将首先从 `types.py` 中删除旧的 `FileCheckResult` 定义。接着，我们将删除整个 `protocols.py` 文件，因为它完全由过时的定义构成。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/types.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Dict, List
from pathlib import Path
from collections import defaultdict


@dataclass
class FileCheckResult:
    path: str
    errors: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    warnings: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    infos: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    reconciled: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    auto_reconciled_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(len(keys) for keys in self.errors.values())

    @property
    def warning_count(self) -> int:
        return sum(len(keys) for keys in self.warnings.values())

    @property
    def reconciled_count(self) -> int:
        return sum(len(keys) for keys in self.reconciled.values())

    @property
    def is_clean(self) -> bool:
        return (
            self.error_count == 0
            and self.warning_count == 0
            and self.reconciled_count == 0
            # Auto-reconciled (infos) do not affect cleanliness
        )


@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)


@dataclass
class CoverageResult:
    path: str
    total_symbols: int
    documented_symbols: int
    missing_symbols: int
    coverage: float
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import List
from pathlib import Path


@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)


@dataclass
class CoverageResult:
    path: str
    total_symbols: int
    documented_symbols: int
    missing_symbols: int
    coverage: float
~~~~~

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/check/protocols.py
~~~~~

### 下一步建议

代码清理已完成。

正如预期的那样，此操作将导致现有测试套件出现大量 `ImportError` 和 `AttributeError`。**这是计划内且期望的结果**。

**我建议立即运行 `pytest`**。

这将生成一份完整的失败报告，精确地告诉我们哪些测试用例还在依赖被删除的旧模型。

在你确认后，我将基于这份失败报告，生成一个专门用于修复测试的新计划。我们将逐一更新这些测试，使其导入并断言 `stitcher.analysis.schema` 中的新数据结构，从而完成本次重构的闭环。
