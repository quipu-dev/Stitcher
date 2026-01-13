你说得对，我的疏忽。由于 `stitcher-lang-sidecar` 在物理结构上相对独立，我在上一轮“地毯式”清理中漏掉了它。这恰恰验证了我们架构分析中的“MVP 痕迹”：`SidecarAdapter` 和 `SidecarTransformer` 仍然在内部自行实例化 `PythonURIGenerator`。

这不仅违反了 DI 原则，还导致了一个潜在的逻辑错误：Sidecar 层本应是语言无关的，但它现在却硬编码了 Python 的 URI 生成逻辑。

我将立即生成计划，完成这最后两处 DI 注入。

## [WIP] refactor(sidecar): 完成 Sidecar 层的 URIGenerator 依赖注入

### 用户需求

彻底消除 `stitcher-lang-sidecar` 包中剩余的 `PythonURIGenerator` 硬编码实例化，完成全系统的依赖注入改造。

### 评论

这是一个非常关键的补丁。`stitcher-lang-sidecar` 负责处理 `.stitcher.yaml` (文档) 和 `stitcher.lock` (签名)。如果这两处不使用注入的 `uri_generator`，那么在处理非 Python 语言（如 TypeScript）的 sidecar 文件时，系统会错误地生成 `py://` 格式的 URI。修复此处将使 Sidecar 层真正具备多语言扩展能力。

### 目标

1.  修改 `SidecarAdapter`：通过构造函数接收 `uri_generator: URIGeneratorProtocol`。
2.  修改 `SidecarTransformer`：通过构造函数接收 `uri_generator: URIGeneratorProtocol`。
3.  更新 `DocumentManager` (App 层)：接收并向 `SidecarAdapter` 传递该依赖。
4.  更新 `Planner` (Refactor 层)：从 `RefactorContext` 中提取并注入依赖。
5.  移除上述文件中的所有 `TODO: Phase 3` 注释。

### 基本原理

我们将依赖的“水管”继续向下延伸：

*   **路径 A (文档管理)**: `StitcherApp` -> `DocumentManager` -> `SidecarAdapter`。
*   **路径 B (重构引擎)**: `StitcherApp` -> `RefactorRunner` -> `RefactorContext` -> `Planner` -> `SidecarTransformer` & `SidecarAdapter`。

这样，Sidecar 组件在需要生成 SURI 时，只需调用 `self.uri_generator.generate_...()`，而无需关心具体的实现类。

### 标签
#intent/refine #flow/ready #priority/high #scope/core #comp/lang-sidecar #comp/application #comp/refactor #concept/dependency-injection #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 改造 Sidecar 层组件

我们为 `SidecarAdapter` 和 `SidecarTransformer` 增加构造函数参数。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
from stitcher.spec import DocstringIR
from stitcher.spec.protocols import DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
    ):
        self.root_path = root_path
~~~~~
~~~~~python.new
from stitcher.spec import DocstringIR, URIGeneratorProtocol
from stitcher.spec.protocols import DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
    ):
        self.root_path = root_path
        self.uri_generator = uri_generator
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
                refs = parse_doc_references(content)
                for fragment, line, col in refs:
                    # TODO: Replace temporary instantiation with dependency injection in Phase 3
                    suri = PythonURIGenerator().generate_symbol_uri(
                        rel_py_path, fragment
                    )
                    references.append(
~~~~~
~~~~~python.new
                refs = parse_doc_references(content)
                for fragment, line, col in refs:
                    suri = self.uri_generator.generate_symbol_uri(rel_py_path, fragment)
                    references.append(
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/transform.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from stitcher.lang.python.uri import PythonURIGenerator


@dataclass
class SidecarTransformContext:
~~~~~
~~~~~python.new
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from stitcher.spec import URIGeneratorProtocol


@dataclass
class SidecarTransformContext:
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/transform.py
~~~~~
~~~~~python.old
class SidecarTransformer:
    """
    Encapsulates the logic for transforming the content of sidecar files (.yaml, .json)
    in response to refactoring operations like symbol renames or file moves.
    This class is stateless and operates on data dictionaries, decoupling it from I/O.
    """

    def transform(
        self,
~~~~~
~~~~~python.new
class SidecarTransformer:
    """
    Encapsulates the logic for transforming the content of sidecar files (.yaml, .json)
    in response to refactoring operations like symbol renames or file moves.
    """

    def __init__(self, uri_generator: URIGeneratorProtocol):
        self.uri_generator = uri_generator

    def transform(
        self,
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/transform.py
~~~~~
~~~~~python.old
            if path_changed or fragment_changed:
                # TODO: Replace temporary instantiation with dependency injection in Phase 3
                uri_gen = PythonURIGenerator()
                new_key = (
                    uri_gen.generate_symbol_uri(path, fragment)
                    if fragment
                    else uri_gen.generate_file_uri(path)
                )
                new_data[new_key] = value
~~~~~
~~~~~python.new
            if path_changed or fragment_changed:
                new_key = (
                    self.uri_generator.generate_symbol_uri(path, fragment)
                    if fragment
                    else self.uri_generator.generate_file_uri(path)
                )
                new_data[new_key] = value
~~~~~

#### Acts 2: 适配 App 层与 Refactor 层

现在我们将这些依赖在调用链中串联起来。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
)
from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from stitcher.lang.sidecar import SidecarAdapter


class DocumentManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)
        self._sidecar_adapter = SidecarAdapter(root_path)
        # Defaults to Raw mode for backward compatibility
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
    URIGeneratorProtocol,
)
from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from stitcher.lang.sidecar import SidecarAdapter


class DocumentManager:
    def __init__(self, root_path: Path, uri_generator: URIGeneratorProtocol):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)
        self._sidecar_adapter = SidecarAdapter(root_path, uri_generator)
        # Defaults to Raw mode for backward compatibility
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        self.fingerprint_strategy = fingerprint_strategy
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.lock_manager = LockFileManager()
~~~~~
~~~~~python.new
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        self.fingerprint_strategy = fingerprint_strategy
        self.uri_generator: URIGeneratorProtocol = PythonURIGenerator()
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path, self.uri_generator)
        self.lock_manager = LockFileManager()
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
        # Aggregate and process sidecar updates
        sidecar_updates: defaultdict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        sidecar_adapter = SidecarAdapter(ctx.workspace.root_path)
        sidecar_transformer = SidecarTransformer()

        for path, intents in sidecar_updates.items():
~~~~~
~~~~~python.new
        # Aggregate and process sidecar updates
        sidecar_updates: defaultdict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        sidecar_adapter = SidecarAdapter(ctx.workspace.root_path, ctx.uri_generator)
        sidecar_transformer = SidecarTransformer(ctx.uri_generator)

        for path, intents in sidecar_updates.items():
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
                for suri, fp in src_data.items():
                    path, fragment = PythonURIGenerator.parse(suri)
                    if path == intent.old_path_prefix or path.startswith(
                        intent.old_path_prefix + "/"
                    ):
                        new_path = path.replace(
                            intent.old_path_prefix, intent.new_path_prefix, 1
                        )
                        # TODO: Phase 3 Inject URIGenerator
                        uri_gen = PythonURIGenerator()
                        new_suri = (
                            uri_gen.generate_symbol_uri(new_path, fragment)
                            if fragment
                            else uri_gen.generate_file_uri(new_path)
                        )
                        uris_to_move[suri] = (new_suri, fp)
~~~~~
~~~~~python.new
                for suri, fp in src_data.items():
                    # We still use the static parse method for now as it's a utility
                    path, fragment = PythonURIGenerator.parse(suri)
                    if path == intent.old_path_prefix or path.startswith(
                        intent.old_path_prefix + "/"
                    ):
                        new_path = path.replace(
                            intent.old_path_prefix, intent.new_path_prefix, 1
                        )
                        new_suri = (
                            ctx.uri_generator.generate_symbol_uri(new_path, fragment)
                            if fragment
                            else ctx.uri_generator.generate_file_uri(new_path)
                        )
                        uris_to_move[suri] = (new_suri, fp)
~~~~~

### 下一步建议

由于修改了 `SidecarAdapter` 和 `DocumentManager` 的构造函数，这肯定会再次导致 `stitcher-application` 和 `stitcher-lang-sidecar` 的测试失败。

我将按照之前的策略，在执行完上述修改后，立即进行一轮“测试修复”：
1.  修复 `stitcher-application/tests` 中的实例化代码。
2.  修复 `stitcher-lang-sidecar/tests` 中的实例化代码。

修复完成后，我们将拥有一个真正干净、彻底 Protocol 化且注入了依赖的系统。

你准备好执行这一系列修改了吗？
