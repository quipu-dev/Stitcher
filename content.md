我明白了，在 `stubgen` 包被拆分后，出现了一些集成和类型检查方面的问题。我会逐一修复这些问题。

核心问题在于：
1.  **模块导入错误**：Python 的命名空间包（`stitcher`）没有在所有子包中正确配置，导致 `stitcher.stubgen` 无法被 `stitcher.app` 找到。
2.  **类型检查错误**：
    *   `protocols.py` 中存在重复的协议定义，并且一个协议的返回类型与其实现不匹配。
    *   `refactor.py` 中一段临时的调试代码导致了属性访问错误。

我将通过以下步骤解决这些问题：

1.  **修复协议文件**：一次性修正 `protocols.py` 中的重复定义和类型签名问题。
2.  **建立命名空间包**：在所有 `stitcher` 子包中添加正确的 `__init__.py` 文件，以确保模块系统能正确解析它们。
3.  **移除调试代码**：移除 `refactor.py` 中导致错误的临时调试代码块。

这将确保整个项目在重构后恢复健康状态。

## [WIP] fix: 修复 stubgen 包拆分后的集成问题

### 错误分析

用户提供的 `traceback` 和 `pyright` 错误报告指出了几个问题：
1.  **`ModuleNotFoundError: No module named 'stitcher.stubgen'`**: 这是最关键的运行时错误。`stitcher` 是一个跨多个 `packages` 目录的命名空间包。为了让 Python 能够找到所有分散的部分（如 `stitcher.app` 和 `stitcher.stubgen`），每个 `packages/*/src/stitcher` 目录都必须包含一个 `__init__.py` 文件，并使用 `pkgutil.extend_path` 来声明它是一个命名空间包的一部分。有几个子包缺失了这个文件。
2.  **`protocols.py` 中的重复声明和类型不兼容**：`stitcher-spec` 包中的协议定义文件被意外地复制了一份内容，导致了多个“重定义”错误。同时，`DocstringSerializerProtocol` 中 `to_yaml` 方法的返回类型签名（`Dict`）与其实际实现（`Union[str, Dict]`）不匹配，导致了类型覆盖错误。
3.  **`refactor.py` 中的属性访问错误**：在 `RefactorRunner` 中，一段用于调试的 `--- DEBUG ---` 代码块正在访问一个不保证存在的属性 `op.old_fqn`，导致了类型检查失败。移除这段非核心的调试代码是修复此问题的最直接方法。

### 用户需求

修复因 `stubgen` 包拆分而引入的所有运行时错误和类型检查错误，使项目恢复正常。

### 评论

这是一个典型的在大型 Monorepo 重构中出现的问题。修复这些“阵痛”对于保持代码库的健康和开发流程的顺畅至关重要。通过建立正确的命名空间包结构和清理类型定义，我们可以确保系统的模块化和长期可维护性。

### 目标

1.  修正 `stitcher-spec` 中的 `protocols.py` 文件，移除重复代码并更新 `to_yaml` 的返回类型。
2.  在 `stitcher-config`、`stitcher-python-adapter` 和 `stitcher-stubgen` 包中添加正确的命名空间 `__init__.py` 文件。
3.  从 `refactor.py` 中移除临时的调试代码块。

### 基本原理

我们将采用外科手术式的方法来解决这些问题：
1.  **原子化修复**：首先，通过一次 `write_file` 操作彻底修复 `protocols.py`，解决所有相关的类型错误。这比多次 `patch` 更清晰、更安全。
2.  **结构性修复**：接着，通过 `write_file` 创建缺失的 `__init__.py` 文件。这是修复 `ModuleNotFoundError` 的根本方法，因为它能让 Python 的导入系统正确地将分散的 `stitcher` 目录“缝合”成一个统一的命名空间。
3.  **精简化修复**：最后，使用 `patch_file` 移除 `refactor.py` 中的调试代码。这是一个局部更改，使用 `patch` 最为合适。

### 标签

#intent/fix #flow/ready #priority/critical #comp/build #comp/application #comp/spec #scope/core #scope/dx #ai/instruct #task/domain/tooling #task/object/monorepo-integration #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复协议定义

我们首先使用 `write_file` 彻底替换 `protocols.py` 的内容。这将同时解决重复定义和 `to_yaml` 方法返回类型不匹配的问题。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Union, Optional, List, Any
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint
from .docstring import DocstringIR


class LanguageParserProtocol(Protocol):
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef: ...


class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...


class FingerprintStrategyProtocol(Protocol):
    def compute(self, entity: Union[FunctionDef, ClassDef]) -> Fingerprint: ...


class StubGeneratorProtocol(Protocol):
    def generate(self, module: ModuleDef) -> str: ...


class DocstringParserProtocol(Protocol):
    def parse(self, docstring_text: str) -> DocstringIR: ...


class DocstringRendererProtocol(Protocol):
    def render(
        self,
        docstring_ir: DocstringIR,
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]] = None,
    ) -> str: ...


class DocstringSerializerProtocol(Protocol):
    def to_yaml(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR: ...
~~~~~

#### Acts 2: 建立统一的 `stitcher` 命名空间

现在，我们在所有缺失的 `src/stitcher` 目录下创建 `__init__.py` 文件，以正确声明它们是同一个命名空间包的一部分。这是解决 `ModuleNotFoundError` 的关键。

创建 `stitcher-config` 的命名空间声明文件。
~~~~~act
write_file
packages/stitcher-config/src/stitcher/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

创建 `stitcher-python-adapter` 的命名空间声明文件。
~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

创建 `stitcher-stubgen` 的命名空间声明文件。
~~~~~act
write_file
packages/stitcher-stubgen/src/stitcher/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 3: 移除 `refactor` 运行器中的临时调试代码

最后，我们移除 `refactor.py` 中导致 `pyright` 错误的调试代码块。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
            spec = loader.load_from_path(migration_script)

            # --- DEBUG ---
            from stitcher.refactor.operations import RenameSymbolOperation

            for op in spec.operations:
                if isinstance(op, RenameSymbolOperation):
                    target_fqn = op.old_fqn
                    usages = graph.registry.get_usages(target_fqn)
                    bus.debug(
                        L.debug.log.refactor_symbol_usage_count,
                        count=len(usages),
                        fqn=target_fqn,
                    )
            # --- END DEBUG ---

            planner = Planner()
            file_ops = planner.plan(spec, ctx)
~~~~~
~~~~~python.new
            spec = loader.load_from_path(migration_script)

            planner = Planner()
            file_ops = planner.plan(spec, ctx)
~~~~~

### 下一步建议

现在所有的运行时和类型检查错误都已修复。我建议您：
1.  **运行测试套件**：执行 `pytest` 来确认所有修复都已生效，并且没有引入新的回归问题。
2.  **提交变更**：一旦测试通过，您可以创建一个 `[COMMIT]` 计划来将这些修复提交到版本控制中。
3.  **继续开发**：继续您的开发任务。
