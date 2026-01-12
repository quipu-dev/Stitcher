Excellent. We are now at the core of this refactoring phase: decomposing the monolithic `CheckAnalyzer` into a set of clean, independent, and testable rules.

I will generate a plan to create the necessary infrastructure (rule protocols, violation schemas) and then implement the first set of consistency rules.

## [WIP] feat(analysis): Extract consistency rules from CheckAnalyzer

### 用户需求

根据 Phase 1 的第 3 步，将 `CheckAnalyzer` 中的逻辑拆解为独立的规则类。这需要首先建立规则的基础架构（基类、输出格式），然后将原有的 `if/else` 逻辑块迁移到新的规则实现中。

### 评论

这是本次重构的核心价值所在。通过将隐式的、混合在“面条代码”中的业务规则显式化、原子化，我们极大地提升了系统的可维护性、可测试性和可扩展性。每个规则文件都将成为一个独立的、可被理解的逻辑单元。

### 目标

1.  在 `stitcher.analysis.schema` 中定义一个标准的 `Violation` 数据结构，作为所有规则的统一输出格式。
2.  在 `stitcher.analysis.rules` 中定义 `SymbolRule` 和 `SubjectRule` 两个基础协议，分别用于处理符号级和文件级的检查。
3.  创建 `DocstringContentRule`，用于检查文档的 `conflict` (内容冲突) 和 `redundant` (冗余) 问题。
4.  创建 `ExistenceRule`，用于检查 `missing` (缺失), `pending` (待抽取) 和 `extra` (悬空) 的文档问题。

### 基本原理

我们将引入一个更结构化的 `Violation` 对象来替代之前 `FileCheckResult` 中基于字符串字典的错误报告方式。这将使结果更易于处理和分类。然后，我们定义两种规则协议：`SymbolRule` 对每个符号进行操作，`SubjectRule` 对整个文件进行操作。这种区分使得规则的职责更加清晰。最后，我们逐一将 `CheckAnalyzer` 中的逻辑块迁移到实现了这些协议的新规则类中。

### 标签

#intent/refine #intent/architect #flow/ready #priority/high #comp/engine #scope/core #ai/instruct #task/domain/architecture #task/object/analysis-engine #task/action/extract-rules #task/state/continue

---

### Script

#### Acts 1: 创建规则和一致性目录

为规则引擎和具体的规则集创建目录结构。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-analysis/src/stitcher/analysis/rules/consistency
touch packages/stitcher-analysis/src/stitcher/analysis/rules/__init__.py
touch packages/stitcher-analysis/src/stitcher/analysis/rules/consistency/__init__.py
~~~~~

#### Acts 2: 定义 `Violation` Schema

这是所有规则的标准化输出，比之前的字典结构更清晰。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/schema/violations.py
~~~~~
~~~~~python
from dataclasses import dataclass
from enum import Enum


class ViolationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Violation:
    """
    Represents a single issue found by a rule.
    """
    fqn: str
    rule_id: str
    level: ViolationLevel
    category: str
    message: str
~~~~~

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/schema/__init__.py
~~~~~
~~~~~python.old
from .symbol_state import SymbolState
from .results import FileCheckResult

__all__ = ["SymbolState", "FileCheckResult"]
~~~~~
~~~~~python.new
from .symbol_state import SymbolState
from .results import FileCheckResult
from .violations import Violation, ViolationLevel

__all__ = ["SymbolState", "FileCheckResult", "Violation", "ViolationLevel"]
~~~~~

#### Acts 3: 定义规则基础协议

创建 `SymbolRule` 和 `SubjectRule`，为不同粒度的检查提供接口。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/rules/base.py
~~~~~
~~~~~python
from typing import Protocol, List
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import SymbolState, Violation


class SymbolRule(Protocol):
    """A rule that checks a single symbol's state."""
    
    id: str

    def check(self, state: SymbolState) -> List[Violation]:
        ...


class SubjectRule(Protocol):
    """A rule that checks the entire subject (file)."""
    
    id: str

    def check(self, subject: AnalysisSubject) -> List[Violation]:
        ...
~~~~~

#### Acts 4: 提取 `DocstringContentRule`

此规则负责处理代码与 YAML 文档内容之间的一致性问题。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/rules/consistency/docstring.py
~~~~~
~~~~~python
from typing import List
from stitcher.analysis.schema import SymbolState, Violation, ViolationLevel
from stitcher.analysis.rules.base import SymbolRule


class DocstringContentRule(SymbolRule):
    """
    Checks for consistency between docstrings in source code and YAML.
    - `conflict`: Docstring summaries differ.
    - `redundant`: Docstring summaries are identical.
    """

    id = "CONSISTENCY_DOCSTRING_CONTENT"

    def check(self, state: SymbolState) -> List[Violation]:
        violations: List[Violation] = []
        if not (state.exists_in_code and state.exists_in_yaml):
            return violations
        
        if state.source_doc_content and state.yaml_doc_ir:
            if state.source_doc_content == state.yaml_doc_ir.summary:
                violations.append(
                    Violation(
                        fqn=state.fqn,
                        rule_id=self.id,
                        level=ViolationLevel.WARNING,
                        category="redundant",
                        message=(
                            "Docstring exists in both code and YAML. "
                            "Consider running `stitcher strip`."
                        ),
                    )
                )
            else:
                violations.append(
                    Violation(
                        fqn=state.fqn,
                        rule_id=self.id,
                        level=ViolationLevel.ERROR,
                        category="conflict",
                        message="Content differs between source code docstring and YAML.",
                    )
                )

        return violations
~~~~~

#### Acts 5: 提取 `ExistenceRule`

此规则负责检查符号在不同来源（代码、YAML）中是否存在，以发现缺失、待处理或悬空的文档。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/rules/consistency/existence.py
~~~~~
~~~~~python
from typing import List
from stitcher.analysis.schema import SymbolState, Violation, ViolationLevel
from stitcher.analysis.rules.base import SymbolRule


class ExistenceRule(SymbolRule):
    """
    Checks for the existence of symbols across code and YAML.
    - `pending`: Docstring exists in code, but not yet in YAML.
    - `missing`: Public symbol exists, but has no docstring anywhere.
    - `extra`: Docstring exists in YAML, but not in code (dangling).
    """

    id = "CONSISTENCY_EXISTENCE"

    def check(self, state: SymbolState) -> List[Violation]:
        violations: List[Violation] = []

        if state.exists_in_code and not state.exists_in_yaml:
            if state.is_public:
                if state.source_doc_content:
                    violations.append(
                        Violation(
                            fqn=state.fqn,
                            rule_id=self.id,
                            level=ViolationLevel.ERROR,
                            category="pending",
                            message="New docstring in code needs to be pumped to YAML.",
                        )
                    )
                else:
                    # Legacy: __doc__ is optional and doesn't trigger 'missing'
                    if state.fqn != "__doc__":
                        violations.append(
                            Violation(
                                fqn=state.fqn,
                                rule_id=self.id,
                                level=ViolationLevel.WARNING,
                                category="missing",
                                message="Public symbol is missing a docstring.",
                            )
                        )
        elif not state.exists_in_code and state.exists_in_yaml:
            violations.append(
                Violation(
                    fqn=state.fqn,
                    rule_id=self.id,
                    level=ViolationLevel.ERROR,
                    category="extra",
                    message="Documentation exists for a non-existent symbol in code.",
                )
            )

        return violations
~~~~~

### 下一步建议

我们已经成功地将 `CheckAnalyzer` 的核心逻辑拆分成了两个独立的规则。

下一步是继续这个过程，提取处理**签名**的规则（`SignatureRule`）和处理**未追踪文件**的规则（`UntrackedRule`）。完成后，我们就可以构建一个简单的规则引擎来编排和运行这些新创建的规则了。

如果你同意，我将生成提取 `SignatureRule` 和 `UntrackedRule` 的计划。
