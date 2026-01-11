好的，我们继续执行统一路线图。现在进入 **Phase B: 抽象作用域构建器**。

此计划将创建一个共享的 `ScopeAnalyzer` 组件。它的唯一职责是分析模块的顶层结构（无论是来自 Griffe 还是 Stitcher IR），并生成一个权威的“本地符号映射表”。这将彻底消除 `refactor` 和 `index` 两个引擎在准备 `UsageScanVisitor` 上下文时的重复逻辑。

## [WIP] refactor(analysis): 抽象作用域分析器以统一符号映射逻辑

### 错误分析

无。这是对组件统一与瘦身路线图的第二步实施。

### 用户需求

实现 Phase B 路线图：在 `stitcher-python-analysis` 包中创建一个共享的 `ScopeAnalyzer`，用于抽象和统一 `local_symbols` 映射表的构建逻辑，并重构 `stitcher-refactor` 和 `stitcher-python-adapter` 以使用该新组件。

### 评论

这是继 FQN 工具化之后的又一次关键重构。构建符号作用域（即“在这个文件里，`utils` 到底指向哪个模块？”）是静态分析中最复杂、最容易出错的部分之一。通过将此逻辑抽象到一个单一、可测试的 `ScopeAnalyzer` 中，我们不仅消除了代码重复，更重要的是，我们保证了重构引擎和索引引擎在进行引用分析时，其“世界观”是完全一致的。这是通往“确定性链接”的必要基石。

### 目标

1.  在 `stitcher-python-analysis` 中创建新的 `scope.py` 模块。
2.  实现 `ScopeAnalyzer` 类，它能够从 `stitcher.spec.ModuleDef` (Stitcher IR) 中构建出 `local_symbols` 映射表。
3.  为 `ScopeAnalyzer` 添加全面的单元测试。
4.  重构 `stitcher-refactor` 中的 `SemanticGraph`，用 `ScopeAnalyzer` 替换其手动的符号表构建逻辑。
5.  重构 `stitcher-python-adapter` 中的 `PythonAdapter`，同样用 `ScopeAnalyzer` 替换其符号表构建逻辑。

### 基本原理

核心思想是将“作用域分析”视为一种独立的、可重用的能力。我们创建 `ScopeAnalyzer` 作为这项能力的唯一实现。它的输入是代码的结构化表示（当前阶段为 Stitcher IR），输出是一个标准的符号映射表（`Dict[str, str]`）。这样，无论上游是重构引擎还是索引引擎，它们在调用 `UsageScanVisitor` 之前，都会通过同一个“镜头”来观察和理解代码的作用域。这从根本上消除了因实现差异导致分析结果不一致的风险。

### 标签

#intent/refine #flow/ready #priority/high #comp/refactor #comp/index #comp/python-analysis #comp/tests #scope/dx #ai/delegate #task/domain/architecture #task/object/component-unification #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `ScopeAnalyzer` 及其单元测试

我们在 `stitcher-python-analysis` 包中创建 `scope.py` 模块，并实现 `ScopeAnalyzer`。为了简化，我们先让它支持从 Stitcher IR (`ModuleDef`) 构建符号表，因为这是两个消费者都能获取到的数据模型。同时，我们为其编写单元测试。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/scope.py
~~~~~
~~~~~python
from typing import Dict
from stitcher.spec import ModuleDef


class ScopeAnalyzer:
    def build_from_ir(
        self, module: ModuleDef, logical_module_fqn: str
    ) -> Dict[str, str]:
        """
        Builds a local symbol map (name -> FQN) from a Stitcher ModuleDef IR.
        This map is used by UsageScanVisitor to resolve names in a file's scope.
        """
        local_symbols: Dict[str, str] = {}

        # 1. Register imported aliases (e.g., 'helper' -> 'pkg.utils.helper')
        for attr in module.attributes:
            if attr.alias_target:
                local_symbols[attr.name] = attr.alias_target

        # 2. Register local definitions
        def register_local(name: str, parent_fqn: str = "") -> str:
            fqn = (
                f"{parent_fqn}.{name}"
                if parent_fqn
                else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            cls_fqn = register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
                    local_symbols[attr.name] = attr.alias_target
            # Methods are handled by visitor's scope analysis (e.g., self.method)

        return local_symbols
~~~~~
~~~~~act
write_file
packages/stitcher-python-analysis/tests/unit/test_scope.py
~~~~~
~~~~~python
from stitcher.spec import ModuleDef, Attribute, FunctionDef, ClassDef
from stitcher.python.analysis.scope import ScopeAnalyzer


def test_scope_analyzer_from_ir():
    # 1. Setup: Create a mock ModuleDef IR
    module_ir = ModuleDef(
        file_path="src/main.py",
        attributes=[
            # import os -> alias 'os' -> 'os'
            Attribute(name="os", alias_target="os"),
            # from utils import helper -> alias 'helper' -> 'utils.helper'
            Attribute(name="helper", alias_target="utils.helper"),
        ],
        functions=[FunctionDef(name="my_func")],
        classes=[
            ClassDef(
                name="MyClass",
                attributes=[
                    # from .models import User -> alias 'User' -> 'main.models.User'
                    Attribute(name="User", alias_target="main.models.User")
                ],
            )
        ],
    )

    analyzer = ScopeAnalyzer()

    # 2. Act
    symbol_map = analyzer.build_from_ir(module_ir, logical_module_fqn="main")

    # 3. Assert
    assert symbol_map["os"] == "os"
    assert symbol_map["helper"] == "utils.helper"
    # Local function definition should be mapped to its FQN
    assert symbol_map["my_func"] == "main.my_func"
    # Local class definition
    assert symbol_map["MyClass"] == "main.MyClass"
    # Class-level alias
    assert symbol_map["User"] == "main.models.User"
~~~~~

#### Acts 2: 改造 `stitcher-python-adapter` (`PythonAdapter`)

现在，我们让 `PythonAdapter` 使用新的 `ScopeAnalyzer`，移除其内部重复的逻辑。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python.fingerprint import PythonFingerprintStrategy
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry
from stitcher.python.analysis.utils import path_to_logical_fqn
from .uri import SURIGenerator
~~~~~
~~~~~python.new
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python.fingerprint import PythonFingerprintStrategy
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry
from stitcher.python.analysis.scope import ScopeAnalyzer
from stitcher.python.analysis.utils import path_to_logical_fqn
from .uri import SURIGenerator
~~~~~
~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
    def _extract_references(
        self,
        rel_path: str,
        module: ModuleDef,
        content: str,
        file_path: Path,
        logical_module_fqn: str,
    ) -> List[ReferenceRecord]:
        refs: List[ReferenceRecord] = []

        # 1. Build local_symbols map (Name -> FQN)
        # This helps the visitor distinguish between local usages and globals/builtins.
        # It maps a name visible in the current scope to its fully-qualified name.
        local_symbols = {}

        # 1a. Register all imported aliases (e.g., 'helper' -> 'pkg.utils.helper')
        for attr in module.attributes:
            if attr.alias_target:
                local_symbols[attr.name] = attr.alias_target

        # 1b. Register all local definitions
        def register_local(name: str, parent_fqn: str = "") -> str:
            fqn = (
                f"{parent_fqn}.{name}" if parent_fqn else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            cls_fqn = register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
                    local_symbols[attr.name] = attr.alias_target
            # Methods are handled by the visitor's scope analysis (e.g., self.method)
            # so we don't need to register them as top-level local symbols.

        # 2. Parse CST and Run Visitor
~~~~~
~~~~~python.new
    def _extract_references(
        self,
        rel_path: str,
        module: ModuleDef,
        content: str,
        file_path: Path,
        logical_module_fqn: str,
    ) -> List[ReferenceRecord]:
        refs: List[ReferenceRecord] = []

        # 1. Build local_symbols map using the centralized analyzer
        analyzer = ScopeAnalyzer()
        local_symbols = analyzer.build_from_ir(module, logical_module_fqn)

        # 2. Parse CST and Run Visitor
~~~~~

#### Acts 3: 改造 `stitcher-refactor` (`SemanticGraph`)

由于 `refactor` 的 `SemanticGraph` 直接消费 Griffe 对象而非 Stitcher IR，我们将暂时跳过对其的重构。当前的 `ScopeAnalyzer` 只支持 IR。在未来的重构中，当 Refactor 引擎也开始消费 Stitcher IR 或 Index 数据时，才能彻底移除其重复逻辑。**此计划将优先统一 Index 端的逻辑，因为它直接影响“确定性链接”路线图**。

### 下一步建议

我们已经成功地将作用域分析逻辑抽象化，并应用到了 `stitcher-index` 的流程中。`PythonAdapter` 现在更加简洁，其行为也与未来的 Refactor 引擎保持了一致性。

现在，底层的分析工具已经得到了强化和统一。我们准备好正式开始实施“确定性链接”路线图的第一步了：

**下一步：执行 Phase 1: 数据模型解耦 (Schema Decoupling)**。

我将为你生成一个计划，该计划将修改数据库的 `schema.sql`，调整 `symbols` 和 `references` 表，以分离“逻辑意图”和“物理链接”。
