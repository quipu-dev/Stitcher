好的，我明白了。 `patch_file` 操作收到了一个致命错误，因为它没有接收到 `old_string` 和 `new_string` 这两个必需的参数。我必须为每个 `patch_file` 操作提供完整的 `old` 和 `new` 内容块。

我将重新生成完全符合协议的计划。

---

我将生成一个计划来实现这个改动。

## [WIP] feat(adapter): 引入 Griffe 依赖并创建 GriffePythonParser 骨架

### 用户需求
根据技术提案，启动 Griffe 解析器集成工作：
1.  在 `stitcher-python-adapter` 中引入 `griffe` 库。
2.  创建 `GriffePythonParser` 类并实现 `LanguageParserProtocol` 协议结构。

### 评论
这是替换解析引擎的第一步。我们遵循“架构优先”的原则，先建立符合协议的空实现和依赖关系，确保系统可以编译和导入新组件，然后再填充具体的 ASTM (Abstract Syntax Tree Mapping) 逻辑。

### 目标
1.  修改 `packages/stitcher-python-adapter/pyproject.toml`，添加 `griffe` 依赖。
2.  创建 `packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py`，定义 `GriffePythonParser` 类。
3.  更新 `packages/stitcher-python-adapter/src/stitcher/adapter/python/__init__.py` 导出新类。

### 基本原理
通过先定义其接口契约（Protocol Implementation），我们可以在不破坏现有功能的情况下引入新组件。将实现文件放在 `adapter/python` 目录下符合现有的包结构规范。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/parser #scope/core #ai/instruct
#task/domain/engine #task/object/griffe-parser #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 添加依赖

首先，我们将 `griffe` 添加到适配器包的依赖列表中。

~~~~~act
patch_file
packages/stitcher-python-adapter/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "libcst",
]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "libcst",
    "griffe",
]
~~~~~

#### Acts 2: 创建解析器类骨架

我们创建 `GriffePythonParser` 类。现阶段它只包含初始化逻辑和抛出 `NotImplementedError` 的 `parse` 方法，用于确认协议签名。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python
import griffe
from stitcher.spec import ModuleDef, LanguageParserProtocol


class GriffePythonParser(LanguageParserProtocol):
    """
    A Python parser implementation using Griffe (https://mkdocstrings.github.io/griffe/).
    
    This parser provides enhanced capabilities for:
    - Type analysis (forward references, unions, generics)
    - Docstring parsing
    - Modern Python syntax support
    """
    
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef:
        """
        Parses the given source code into a Stitcher ModuleDef IR using Griffe.
        
        Args:
            source_code: The raw source code string.
            file_path: The relative path to the file (used for metadata).
            
        Returns:
            ModuleDef: The intermediate representation of the module.
        """
        # TODO: Implement the mapping logic from griffe.Module to stitcher.spec.ModuleDef
        # in the next phase of the implementation plan.
        
        # Temporary placeholder to validate instantiation
        raise NotImplementedError("Griffe mapping logic not yet implemented.")

~~~~~

#### Acts 3: 导出新组件

最后，我们在包的 `__init__.py` 中公开这个新类，使其对系统的其他部分可见。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/__init__.py
~~~~~
~~~~~python.old
from .parser import PythonParser
from .transformer import PythonTransformer
from .generator import PythonStubGenerator
from .fingerprint import PythonFingerprintStrategy
from .inspector import parse_plugin_entry, InspectionError

__all__ = [
    "PythonParser",
    "PythonTransformer",
    "PythonStubGenerator",
    "PythonFingerprintStrategy",
    "parse_plugin_entry",
    "InspectionError",
]
~~~~~
~~~~~python.new
from .parser import PythonParser
from .transformer import PythonTransformer
from .generator import PythonStubGenerator
from .fingerprint import PythonFingerprintStrategy
from .inspector import parse_plugin_entry, InspectionError
from .griffe_parser import GriffePythonParser

__all__ = [
    "PythonParser",
    "PythonTransformer",
    "PythonStubGenerator",
    "PythonFingerprintStrategy",
    "parse_plugin_entry",
    "InspectionError",
    "GriffePythonParser",
]
~~~~~

### 下一步建议

既然骨架和依赖已经就位，下一步我们将专注于最核心且复杂的任务：**实现 Griffe 对象模型到 Stitcher IR (ModuleDef) 的映射逻辑**。我们将首先创建一个简单的单元测试来驱动这个开发过程。
