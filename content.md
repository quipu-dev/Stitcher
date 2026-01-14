好的，我们开始执行 `DocumentManager` 的迁移。

这是一个关键的架构重构步骤，旨在将 Sidecar 文件的生命周期管理逻辑（加载、解析、序列化）内聚到 `stitcher-lang-sidecar` 包中。这遵循了单一职责原则，将应用层与文档的具体持久化细节解耦，为后续引入索引驱动的增量加载奠定了基础。

## [WIP] refactor(arch): 将 DocumentManager 迁移至 stitcher-lang-sidecar

### 用户需求

根据架构分析，将 `DocumentManager` 及其紧密耦合的 `DocstringMerger` 从通用的 `stitcher.services` 包迁移到专门负责 Sidecar 逻辑的 `stitcher-lang-sidecar` 包中。

### 评论

这是一个对项目架构健康度至关重要的重构。它纠正了组件职责划分的模糊地带，将“Sidecar 管理”这一核心领域能力固化到其专属的包中。此举不仅提升了代码的可维护性，更是实现 Zero-IO Path 性能优化的前置条件。

### 目标

1.  将 `doc_manager.py` 和 `merger.py` 文件从 `stitcher-application` 移动到 `stitcher-lang-sidecar`。
2.  将 `doc_manager.py` 重命名为 `manager.py` 以适应新包的命名约定。
3.  更新所有受影响的 `__init__.py` 文件，以正确导出和移除相关类。
4.  调整 `stitcher-application` 的 `pyproject.toml`，添加对 `stitcher-lang-sidecar` 的新依赖。
5.  修正所有已知代码库中对 `DocumentManager` 和 `DocstringMerger` 的导入路径。

### 基本原理

遵循**单一职责原则 (SRP)** 和**高内聚、低耦合**的设计思想。`DocumentManager` 的核心职责是处理 `.stitcher.yaml` 文件的读、写和解析，这完全属于 `stitcher-lang-sidecar` 包的领域范畴。通过将实现细节（如 `ruamel.yaml` 的使用）封装在 `sidecar` 包内部，应用层（`stitcher-application`）可以更清晰地依赖于一个稳定的接口，而无需关心其底层实现。

### 标签

#intent/refine #flow/ready #priority/high #comp/application #comp/lang-sidecar #concept/dependency #scope/core #ai/instruct #task/domain/architecture #task/object/component-relocation #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 移动并重命名核心逻辑文件

我们将 `DocumentManager` 和 `DocstringMerger` 的源文件移动到 `stitcher-lang-sidecar` 包中，并将 `doc_manager.py` 重命名为 `manager.py`。

~~~~~act
move_file
packages/stitcher-application/src/stitcher/services/doc_manager.py
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~

~~~~~act
move_file
packages/stitcher-application/src/stitcher/services/merger.py
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/merger.py
~~~~~

#### Acts 2: 更新包的导出接口 (`__init__.py`)

现在，我们需要更新 `stitcher.services` 和 `stitcher.lang.sidecar` 的 `__init__.py` 文件，以反映这次迁移。

首先，从 `stitcher.services` 中移除 `DocumentManager` 和 `DocstringMerger` 的导出。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/services/__init__.py
~~~~~
~~~~~python.old
from .doc_manager import DocumentManager
from .scanner import ScannerService
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "ScannerService",
    "DocstringMerger",
]
~~~~~
~~~~~python.new
from .scanner import ScannerService

__all__ = [
    "ScannerService",
]
~~~~~

然后，在 `stitcher.lang.sidecar` 中添加新的导出。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter
from .lock_manager import LockFileManager
from .parser import parse_doc_references, parse_signature_references
from .transform import SidecarTransformContext, SidecarTransformer

__all__ = [
    "SidecarAdapter",
    "LockFileManager",
    "parse_doc_references",
    "parse_signature_references",
    "SidecarTransformContext",
    "SidecarTransformer",
]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter
from .lock_manager import LockFileManager
from .parser import parse_doc_references, parse_signature_references
from .transform import SidecarTransformContext, SidecarTransformer
from .manager import DocumentManager
from .merger import DocstringMerger

__all__ = [
    "SidecarAdapter",
    "LockFileManager",
    "parse_doc_references",
    "parse_signature_references",
    "SidecarTransformContext",
    "SidecarTransformer",
    "DocumentManager",
    "DocstringMerger",
]
~~~~~

#### Acts 3: 调整包依赖关系

由于 `stitcher-application` 现在依赖于 `stitcher-lang-sidecar` 中的 `DocumentManager`，我们需要在其 `pyproject.toml` 中声明这个新的依赖关系。

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-common",
    "stitcher-lang-python",
    "stitcher-stubgen",
~~~~~
~~~~~toml.new
    "stitcher-common",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-stubgen",
~~~~~

#### Acts 4: 更新导入路径

最后，我们将修复 `StitcherApp` 核心类中的导入路径，使其指向 `DocumentManager` 和 `DocstringMerger` 的新位置。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.services import (
    DocumentManager,
    ScannerService,
    DocstringMerger,
)
~~~~~
~~~~~python.new
from stitcher.services import (
    ScannerService,
)
from stitcher.lang.sidecar import DocumentManager, DocstringMerger
~~~~~

### 下一步建议

我们已经完成了对当前可见文件的迁移工作。然而，`rg` 的搜索结果表明，还有一些测试文件和 `stitcher-stubgen` 包中的文件也需要更新导入路径。

由于我当前的上下文（文件树）中不包含这些文件的内容，我无法为它们生成精确的 `patch`。

**建议的操作**：
请为我提供以下文件的内容，或者你也可以手动将它们的导入从 `from stitcher.services import ...` 修改为 `from stitcher.lang.sidecar import ...`：
*   `packages/stitcher-application/tests/unit/test_execution_planner.py`
*   `packages/stitcher-application/tests/unit/test_docstring_hybrid.py`
*   `packages/stitcher-application/tests/unit/test_doc_manager_strategies.py`
*   `packages/stitcher-stubgen/src/stitcher/stubgen/runners.py`
*   `packages/stitcher-stubgen/src/stitcher/stubgen/__init__.py`
*   `packages/stitcher-application/tests/unit/test_doc_manager.py`
*   `packages/stitcher-application/tests/unit/test_doc_overlay.py`

完成这些导入更新后，整个迁移任务就完成了，我们可以继续进行下一步的索引器增强工作。
