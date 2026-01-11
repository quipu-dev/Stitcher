好的，我们立即开始实施计划的第一阶段：**定义协议并创建适配器**。

这是一个纯粹的、无副作用的结构性重构。它将为我们后续的逻辑迁移创建一个稳定、可靠的“桥梁”，而不会改变任何现有的 `check` 行为。

## [WIP] refactor(check): 引入 CheckSubject 协议和 AST 适配器

### 用户需求

定义一个稳定的 `CheckSubject` 协议和一个 `SymbolState` 数据类，作为 `CheckAnalyzer` 的核心数据契约。然后，创建一个 `ASTCheckSubjectAdapter`，它将封装当前所有基于 AST 的分析逻辑，以符合这个新协议。

### 评论

这是应用“依赖倒置原则”的典范。通过引入一个抽象层 (`CheckSubject`)，我们将 `CheckAnalyzer`（高层策略）与数据来源（低层细节，无论是 AST 还是 DB）彻底解耦。`ASTCheckSubjectAdapter` 将作为现有逻辑的“容器”，确保在重构 `CheckAnalyzer` 时，我们有一个稳定、行为不变的数据源进行测试，从而将风险降至最低。

### 目标

1.  **创建协议文件**：在 `.../runners/check/` 目录下创建一个新的 `protocols.py` 文件。
2.  **定义数据契约**：在该文件中定义 `SymbolState` 数据类和 `CheckSubject` 协议。
3.  **创建适配器文件**：在 `.../runners/check/` 目录下创建一个新的 `subject.py` 文件。
4.  **实现 AST 适配器**：在该文件中实现 `ASTCheckSubjectAdapter`，它将封装当前 `CheckAnalyzer` 中所有的文件分析、指纹计算和哈希比较逻辑。

### 基本原理

此步骤的目的是引入一个“接缝 (Seam)”，一个我们可以安全切割和替换代码的边界。我们首先将现有逻辑“移动”到适配器中，然后重构 `CheckAnalyzer` 以调用这个适配器。一旦这个新的、基于协议的结构稳定并通过了所有测试，我们就可以放心地构建第二个适配器 (`IndexCheckSubjectAdapter`)，并在未来无风险地进行切换。

### 标签

#intent/refine #flow/ready #priority/high #comp/application #task/domain/quality #task/object/check-runner #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 定义核心协议与数据类

我们首先创建 `protocols.py` 文件，并定义 `SymbolState` 和 `CheckSubject`。这是我们新架构的基石。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Optional
from dataclasses import dataclass
from stitcher.spec import DocstringIR


@dataclass
class SymbolState:
    """A complete snapshot of a symbol's state from all sources."""

    fqn: str
    is_public: bool

    # --- Source Code State ---
    exists_in_code: bool
    source_doc_content: Optional[str]
    signature_hash: Optional[str]
    signature_text: Optional[str]

    # --- YAML Documentation State ---
    exists_in_yaml: bool
    yaml_doc_ir: Optional[DocstringIR]
    yaml_content_hash: Optional[str]


class CheckSubject(Protocol):
    """The contract for what the CheckAnalyzer can inspect."""

    @property
    def file_path(self) -> str:
        ...

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        """
        Gets the aggregated state of all symbols relevant to this subject.
        This includes symbols defined in code and/or documented in YAML.
        """
        ...
~~~~~

#### Acts 2: 实现 AST 适配器

现在，我们创建 `subject.py` 并实现 `ASTCheckSubjectAdapter`。这个类的核心职责是封装当前所有的分析逻辑，将 `ModuleDef` 对象转换为 `Dict[str, SymbolState]`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python
from typing import Dict
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager
from .protocols import SymbolState, CheckSubject


class ASTCheckSubjectAdapter(CheckSubject):
    """
    An adapter that provides a CheckSubject interface backed by
    a live-parsed AST (ModuleDef).
    """

    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self._module = module_def
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._fingerprint_strategy = fingerprint_strategy

    @property
    def file_path(self) -> str:
        return self._module.file_path

    def _compute_fingerprints(self) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in self._module.functions:
            fingerprints[func.name] = self._fingerprint_strategy.compute(func)
        for cls in self._module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self._fingerprint_strategy.compute(method)
        return fingerprints

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources (the old way)
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        
        fingerprints = self._compute_fingerprints()
        yaml_hashes = self._doc_manager.compute_yaml_content_hashes(self._module)
        
        all_fqns = set(source_docs.keys()) | set(yaml_docs.keys())
        states: Dict[str, SymbolState] = {}

        # 2. Iterate and build the state object for each symbol
        for fqn in all_fqns:
            fp = fingerprints.get(fqn, Fingerprint())
            source_ir = source_docs.get(fqn)
            
            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=(fqn in public_fqns),
                exists_in_code=(fqn in source_docs),
                source_doc_content=source_ir.summary if source_ir else None,
                signature_hash=fp.get("current_code_structure_hash"),
                signature_text=fp.get("current_code_signature_text"),
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_hashes.get(fqn),
            )
            
        return states
~~~~~

### 下一步建议

我们已经成功地创建了抽象层和第一个适配器。这为安全的重构铺平了道路。

下一步计划是：

1.  **重构 `CheckAnalyzer`**：
    *   修改其 `__init__` 方法，不再接收 `doc_manager`, `sig_manager` 等多个服务，而是只接收一个 `CheckSubject` 类型的对象。
    *   重写 `_analyze_file` 方法，使其逻辑完全建立在 `subject.get_all_symbol_states()` 返回的数据之上。这将极大地简化该方法。

2.  **更新 `CheckRunner` (Facade)**：
    *   修改 `analyze_batch` 方法，在循环中创建 `ASTCheckSubjectAdapter` 实例，并将其传递给 `CheckAnalyzer`。

在完成这些之后，整个 `check` 命令的功能应该**和现在完全一样**，所有测试都应该通过。这将验证我们抽象的正确性，并为最终切换到数据库驱动做好准备。
