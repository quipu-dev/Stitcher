我明白了。之前的修复是战术性的，但问题是战略性的。`AttributeError` 只是一个表象，根源在于 `AssetPathResolver` 作为一个遗留组件，与新的 `Workspace` 和 `SignatureManager` 架构产生了冲突，违反了“真理单一来源 (SSoT)”原则。

根据您“清除所有的 AssetPathResolver”的指令，以及 `HFEA` 协议中的“异味即缺陷”和“基础重构奖励”原则，我将执行一个更深层次的重构：彻底从系统中移除 `AssetPathResolver`，并将其职责整合到现代化的组件中。

## [WIP] refactor: 彻底移除 AssetPathResolver 并统一路径解析逻辑

### 错误分析
系统当前存在两种并行的、功能重叠的路径解析机制：
1.  **遗留机制**: `AssetPathResolver`，一个简单的、基于 `root_path` 的解析器，用于查找 `.stitcher.yaml` 和旧的 `.stitcher/signatures` 文件。
2.  **现代机制**: `Workspace` 和 `SignatureManager`，它们协同工作，能够感知 monorepo 布局、包边界，并正确定位新的 `stitcher.lock` 文件。

`SidecarManager` 在上次重构中被修改为依赖 `Workspace`，但其内部仍然错误地尝试初始化遗留的 `AssetPathResolver`，导致了 `AttributeError`。这暴露了两者不兼容的事实，`AssetPathResolver` 已成为必须被根除的架构异味。

### 用户需求
修复测试失败，并执行根治性重构，移除所有对 `AssetPathResolver` 的依赖。

### 评论
这是一个优秀的架构简化决策。通过消除冗余组件，我们降低了系统的认知负荷，增强了代码的内聚性，并确保了路径解析逻辑的唯一性和正确性。

### 目标
1.  删除 `asset_path_resolver.py` 文件。
2.  从 `services/__init__.py` 中移除其导出。
3.  重写 `SidecarManager`，使其不再依赖 `AssetPathResolver`，而是直接实现简单的文档路径逻辑，并继续委托 `SignatureManager` 处理复杂的签名路径逻辑。
4.  重构 `SidecarAdapter`，移除其对 `AssetPathResolver` 的依赖。
5.  **注意**: `stitcher-application` 中的 `DocumentManager` 也依赖 `AssetPathResolver`。由于我当前没有该文件的上下文，本次重构将导致 `ImportError`。这是预期的，我们将在下一步修复它。

### 基本原理
我们将把 `AssetPathResolver` 的两种职责进行拆分和吸收：
-   **文档路径解析 (`get_doc_path`)**: 逻辑非常简单 (`path.with_suffix(".stitcher.yaml")`)，将直接在 `SidecarManager` 和 `SidecarAdapter` 内部实现。
-   **签名路径解析 (`get_signature_path`)**: 其职责已被 `SignatureManager` 完全取代，因此所有调用都将直接委托给 `SignatureManager`。

### 标签
#intent/refine #flow/ready #priority/high #comp/refactor #concept/architecture #scope/core #ai/instruct #task/domain/architecture #task/object/asset-path-resolver #task/action/elimination #task/state/continue

---

### Script

#### Acts 1: 删除 AssetPathResolver

首先，我们物理删除该遗留组件。

~~~~~act
delete_file
packages/stitcher-common/src/stitcher/common/services/asset_path_resolver.py
~~~~~

#### Acts 2: 更新 services 包的导出

从 `__init__.py` 中移除对已删除模块的引用。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/services/__init__.py
~~~~~
~~~~~python.old
from .asset_path_resolver import AssetPathResolver
from .differ import Differ

__all__ = ["AssetPathResolver", "Differ"]
~~~~~
~~~~~python.new
from .differ import Differ

__all__ = ["Differ"]
~~~~~

#### Acts 3: 重构 SidecarManager

现在，我们重写 `SidecarManager`，使其完全独立于 `AssetPathResolver`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/sidecar/manager.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Union

from stitcher.lang.sidecar.signature_manager import SignatureManager
from stitcher.workspace import Workspace


class SidecarManager:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.signature_manager = SignatureManager(workspace)

    def get_doc_path(self, source_file_path: Union[str, Path]) -> Path:
        """
        Returns the path to the document sidecar (.stitcher.yaml) for a given source file.
        This logic is simple enough to live here directly.
        """
        return Path(source_file_path).with_suffix(".stitcher.yaml")

    def get_signature_path(self, source_file_path: Union[str, Path]) -> Path:
        """
        Returns the path to the signature lock file (stitcher.lock) containing the given source file.
        Delegates to SignatureManager to handle package root resolution.
        """
        # Ensure we pass an absolute path string, as expected by some internal logic flows.
        abs_path = self.workspace.root_path / Path(source_file_path)
        return self.signature_manager.get_signature_path(str(abs_path))
~~~~~

#### Acts 4: 重构 SidecarAdapter

最后，我们清理 `SidecarAdapter`。它的实现未使用 `resolver`，所以只需移除初始化代码。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
from ruamel.yaml.scalarstring import LiteralScalarString

from stitcher.spec import DocstringIR
from stitcher.spec.protocols import DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
from stitcher.lang.python.uri import SURIGenerator
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
    ):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)
        self._yaml = YAML()
        self._yaml.indent(mapping=2, sequence=4, offset=2)
~~~~~
~~~~~python.new
from ruamel.yaml.scalarstring import LiteralScalarString

from stitcher.spec import DocstringIR
from stitcher.spec.protocols import DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.lang.python.uri import SURIGenerator
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
    ):
        self.root_path = root_path
        self._yaml = YAML()
        self._yaml.indent(mapping=2, sequence=4, offset=2)
~~~~~

### 下一步建议
我们已经完成了核心重构。正如预期的那样，`stitcher-application` 包中的 `DocumentManager` 现在会因为 `ImportError: cannot import name 'AssetPathResolver'` 而构建失败。

请运行测试，确认 `ImportError` 的出现，然后向我提供 `packages/stitcher-application/src/stitcher/app/services/doc_manager.py` 的文件内容，我将生成计划以完成最后的清理工作。
