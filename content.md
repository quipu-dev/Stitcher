根据 **Stitcher 架构重构路线图** 的阶段二规划，在完成了代码物理迁移后，现在需要完善新包 `stitcher-lang-python` 的 `__init__.py` 导出逻辑，以确保新包提供清晰、扁平的公共 API，并符合命名空间包规范。

## [WIP] refactor: 完善 stitcher-lang-python 包的成员导出

### 用户需求
完善 `stitcher-lang-python` 各级目录的 `__init__.py` 文件，导出核心组件（Parser, Adapter, Transformer, Analysis 等），使外部包可以方便地引用。

### 评论
通过在各层级建立明确的导出逻辑，我们将零散的内部实现转化为结构化的公共 API。这不仅提升了代码的可读性，也确保了重构后的包能够无缝替换原有的 `adapter` 和 `analysis` 包。

### 目标
1.  在 `analysis` 子包中导出作用域分析、引用提取和逻辑 FQN 转换工具。
2.  在 `docstring` 子包中导出编解码器工厂及相关协议实现。
3.  在 `parser` 和 `transform` 子包中分别导出对应的解析和转换门面。
4.  在顶级 `stitcher.lang.python` 中汇总所有公共 API，作为 Python 语言插件的统一入口。

### 基本原理
我们采用“分层导出”策略：底层模块负责具体实现，子包 `__init__.py` 负责汇总子领域 API，顶级 `__init__.py` 负责对外暴露。同时，继续维持顶级目录的 `extend_path` 声明，以保证命名空间包的兼容性。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/build #concept/parser #scope/dx
#ai/instruct
#task/domain/language-support
#task/object/stitcher-lang-python
#task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 完善各级子包的导出逻辑

首先，我们为分析、文档、解析和转换四个功能维度配置导出。

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/analysis/__init__.py
~~~~~
~~~~~python
from .models import UsageLocation, ReferenceType
from .scope import ScopeAnalyzer
from .usage_visitor import UsageScanVisitor, UsageRegistry
from .utils import path_to_logical_fqn

__all__ = [
    "UsageLocation",
    "ReferenceType",
    "ScopeAnalyzer",
    "UsageScanVisitor",
    "UsageRegistry",
    "path_to_logical_fqn",
]
~~~~~

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/docstring/__init__.py
~~~~~
~~~~~python
from .parsers import RawDocstringParser, GriffeDocstringParser
from .renderers import GoogleDocstringRenderer, NumpyDocstringRenderer
from .serializers import RawSerializer, GoogleSerializer, NumpySerializer
from .factory import get_docstring_codec, get_docstring_serializer

__all__ = [
    "RawDocstringParser",
    "GriffeDocstringParser",
    "GoogleDocstringRenderer",
    "NumpyDocstringRenderer",
    "RawSerializer",
    "GoogleSerializer",
    "NumpySerializer",
    "get_docstring_codec",
    "get_docstring_serializer",
]
~~~~~

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/parser/__init__.py
~~~~~
~~~~~python
from .griffe import GriffePythonParser
from .cst import PythonParser

__all__ = ["GriffePythonParser", "PythonParser"]
~~~~~

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/transform/__init__.py
~~~~~
~~~~~python
from .facade import PythonTransformer
from .cst_visitors import strip_docstrings, inject_docstrings
from .rename import SymbolRenamerTransformer, NamespaceRenamerTransformer

__all__ = [
    "PythonTransformer",
    "strip_docstrings",
    "inject_docstrings",
    "SymbolRenamerTransformer",
    "NamespaceRenamerTransformer",
]
~~~~~

#### Acts 2: 配置顶级包导出

最后，我们在 `stitcher.lang.python` 中提供汇总的公共 API。

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/__init__.py
~~~~~
~~~~~python
"""Python language support for Stitcher."""

from .adapter import PythonAdapter
from .fingerprint import PythonFingerprintStrategy
from .inspector import InspectionError, parse_plugin_entry
from .parser.griffe import GriffePythonParser
from .parser.cst import PythonParser
from .transform.facade import PythonTransformer
from .uri import SURIGenerator

__all__ = [
    "PythonAdapter",
    "PythonFingerprintStrategy",
    "InspectionError",
    "parse_plugin_entry",
    "GriffePythonParser",
    "PythonParser",
    "PythonTransformer",
    "SURIGenerator",
]
~~~~~

### 下一步建议
1.  **运行迁移脚本**：现在基础骨架和导出已就绪，你可以安全地运行 `002_phase_2_unify_python_lang.py` 重构脚本（请务必先带上 `--dry-run`）。
2.  **验证测试**：重构脚本执行后，`stitcher-lang-python/tests` 目录下的所有测试应当通过。
3.  **提交变更**：由于这是物理结构的大规模变动，建议在确认测试通过后单独提交一个 `[COMMIT]` 计划。
