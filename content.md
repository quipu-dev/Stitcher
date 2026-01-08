好的，我们开始实施“文档字符串格式化与插件系统”的第 0 阶段。

这是一个纯粹的架构奠基工作，它不会改变任何现有功能，但会为后续的所有开发（特别是插件系统和多格式支持）建立必需的数据结构（IR）和接口协议。这确保了我们未来的实现是建立在稳定、可扩展的契约之上的。

我将生成一个计划来创建这些基础组件。

## [WIP] feat(spec): 为文档字符串格式化实现 Phase 0 基础

### 用户需求

根据《实施路线图：文档字符串格式化与插件系统》，实施 Phase 0: 奠定基石 (Foundation & Scaffolding) 的所有任务。

### 评论

这是实现文档字符串格式化和插件系统功能的一个至关重要的第一步。通过首先定义一个通用的中间表示（`DocstringIR`）和清晰的协议，我们遵循了依赖倒置原则。应用层的逻辑将依赖于这些抽象，而不是具体的 Google/NumPy 解析器实现，这使得整个系统更具扩展性、更容易测试，并能确保后续阶段的开发工作顺利进行。

### 目标

1.  在 `stitcher-spec` 包中创建新的 `docstring.py` 文件，用于定义 `DocstringIR`、`DocstringSection` 和 `DocstringItem` 这些核心数据模型。
2.  更新 `stitcher-spec` 中的 `models.py`，在 `ModuleDef`, `FunctionDef`, 和 `ClassDef` 中添加新的 `docstring_ir` 字段，为存储结构化文档数据做准备。
3.  在 `stitcher-config` 包中扩展 `StitcherConfig` 模型，增加 `docstring_style` 配置项，使其能够支持未来的格式切换。
4.  在 `stitcher-spec` 中定义 `DocstringParserProtocol` 和 `DocstringRendererProtocol` 接口，为未来的解析器和渲染器实现建立契约。
5.  更新 `stitcher-spec` 的 `__init__.py` 以导出所有新创建的类型和协议。

### 基本原理

此阶段的核心是建立一个健壮的**数据契约**。通过将文档字符串抽象为一个通用的中间表示（IR），我们可以将“解析”（从源码到IR）、“序列化”（从IR到YAML）和“渲染”（从IR到注入代码）这三个过程完全解耦。未来的所有功能，无论是支持新的文档风格（如 NumPy）还是集成插件（Addons），都将围绕这个稳定的 IR 进行，而不是处理脆弱的、非结构化的字符串。这是一种典型的“接口先行”的架构方法，旨在降低未来变更的风险和成本。

### 标签

#intent/architect #intent/build #flow/ready #priority/high #comp/spec #comp/config #scope/api #scope/core #ai/instruct #task/domain/docstrings #task/object/ir-scaffolding #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 在 `stitcher-spec` 中定义文档字符串 IR

我们将首先创建 `docstring.py` 文件，其中包含所有文档操作的通用语言和核心数据结构。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/docstring.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any


@dataclass
class DocstringItem:
    """Represents a single item within a docstring section, like a parameter or a return value."""

    name: Optional[str] = None  # e.g., the parameter name
    annotation: Optional[str] = None  # e.g., the type annotation string
    description: str = ""  # The description text
    default: Optional[str] = None  # The default value as a string representation


@dataclass
class DocstringSection:
    """Represents a section of a docstring, like 'Args' or 'Returns'."""

    kind: str  # e.g., "params", "returns", "raises", "text"
    title: Optional[str] = None  # The rendered title, e.g., "Parameters"
    content: Union[str, List["DocstringItem"]] = ""


@dataclass
class DocstringIR:
    """The Intermediate Representation of a docstring."""

    summary: Optional[str] = None
    extended: Optional[str] = None
    sections: List[DocstringSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )  # For "See Also", "Notes"
    addons: Dict[str, Any] = field(default_factory=dict)  # For "Addon.*" data
~~~~~

#### Acts 2: 扩展核心 IR 模型以包含 `DocstringIR`

接下来，我们将 `DocstringIR` 集成到现有的 `ModuleDef`, `ClassDef`, 和 `FunctionDef` 模型中。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

from .docstring import DocstringIR
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
~~~~~
~~~~~python.new
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    is_async: bool = False
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
~~~~~
~~~~~python.new
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    attributes: List[Attribute] = field(default_factory=list)
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
~~~~~
~~~~~python.new
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    attributes: List[Attribute] = field(default_factory=list)
~~~~~

#### Acts 3: 扩展 `StitcherConfig`

现在，我们为项目配置添加 `docstring_style` 字段。

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.py
~~~~~
~~~~~python.old
    plugins: Dict[str, str] = field(default_factory=dict)
    stub_path: Optional[str] = None
    stub_package: Optional[str] = None
~~~~~
~~~~~python.new
    plugins: Dict[str, str] = field(default_factory=dict)
    stub_path: Optional[str] = None
    stub_package: Optional[str] = None
    docstring_style: str = "raw"
~~~~~

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.py
~~~~~
~~~~~python.old
                    stub_path=target_data.get("stub_path"),
                    stub_package=target_data.get("stub_package"),
                )
            )
~~~~~
~~~~~python.new
                    stub_path=target_data.get("stub_path"),
                    stub_package=target_data.get("stub_package"),
                    docstring_style=target_data.get("docstring_style", "raw"),
                )
            )
~~~~~

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.py
~~~~~
~~~~~python.old
                stub_path=stitcher_data.get("stub_path"),
                stub_package=stitcher_data.get("stub_package"),
            )
        )
~~~~~
~~~~~python.new
                stub_path=stitcher_data.get("stub_path"),
                stub_package=stitcher_data.get("stub_package"),
                docstring_style=stitcher_data.get("docstring_style", "raw"),
            )
        )
~~~~~

#### Acts 4: 在 `stitcher-spec` 中定义协议

我们定义解析器和渲染器必须遵守的接口。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
from typing import Protocol, Dict, Union, Optional, List
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint
~~~~~
~~~~~python.new
from typing import Protocol, Dict, Union, Optional, List
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint
from .docstring import DocstringIR
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
class StubGeneratorProtocol(Protocol):
    def generate(self, module: ModuleDef) -> str: ...
~~~~~
~~~~~python.new
class StubGeneratorProtocol(Protocol):
    def generate(self, module: ModuleDef) -> str: ...


class DocstringParserProtocol(Protocol):
    def parse(self, docstring_text: str) -> DocstringIR: ...


class DocstringRendererProtocol(Protocol):
    def render(self, docstring_ir: DocstringIR) -> str: ...
~~~~~

#### Acts 5: 在 `stitcher-spec` 中导出新符号

最后，确保所有新的模型和协议都可以从包中被外部访问。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
from .models import (
    Argument,
    ArgumentKind,
~~~~~
~~~~~python.new
from .docstring import DocstringIR, DocstringSection, DocstringItem
from .models import (
    Argument,
    ArgumentKind,
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
from .protocols import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    StubGeneratorProtocol,
)

__all__ = [
    "LanguageParserProtocol",
    "LanguageTransformerProtocol",
    "FingerprintStrategyProtocol",
    "StubGeneratorProtocol",
~~~~~
~~~~~python.new
from .protocols import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    StubGeneratorProtocol,
    DocstringParserProtocol,
    DocstringRendererProtocol,
)

__all__ = [
    "DocstringIR",
    "DocstringSection",
    "DocstringItem",
    "LanguageParserProtocol",
    "LanguageTransformerProtocol",
    "FingerprintStrategyProtocol",
    "StubGeneratorProtocol",
    "DocstringParserProtocol",
    "DocstringRendererProtocol",
~~~~~

### 下一步建议

基础架构现已到位。下一步是实施路线图中的 **Phase 1: 实现插件系统与混合模式 (The Addon Milestone)**。

这将是第一个利用新 `DocstringIR` 的功能，核心任务是重构 `DocumentManager`，使其能够：
1.  在加载 YAML 时，无论是纯字符串还是字典，都能统一反序列化为 `DocstringIR` 对象。
2.  在保存时，如果 `DocstringIR` 对象包含插件（addons）数据，能够自动将其结构从 `key: string` 升级为 `key: {Raw: ..., Addon.Something: ...}`。
3.  升级哈希计算逻辑，使其能够处理字典结构，确保稳定性。

如果你同意，我将为你生成实施 Phase 1 的计划。
