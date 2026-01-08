[简要回答]
根据“架构重构分析”文档，我将执行 Pre-Phase 2 的重构工作。这包括提取 `Differ` 和 `Merger` 服务，并将 `CheckRunner` 和 `PumpRunner` 中的相关逻辑委托给这些新服务，从而解耦核心业务逻辑与底层实现细节，为后续引入结构化文档支持扫清障碍。

## [WIP] refactor: 提取 Differ 与 Merger 服务以解耦核心 Runner 逻辑

### 用户需求
当前的 `CheckRunner` 和 `PumpRunner` 包含重复的 Diff 生成逻辑，且 `PumpRunner` 内部耦合了文档合并的具体细节（如 Addon 保留）。为了支持未来更复杂的结构化文档（Phase 2），需要将这些逻辑剥离为独立的服务：`Differ`（负责对比）和 `Merger`（负责合并）。

### 评论
这是一个非常必要的架构清理。目前的 `PumpRunner.run` 方法确实有些臃肿，混合了 IO、流程控制和数据操作。提取 `Merger` 特别关键，因为它集中了“如何将代码变更应用到 YAML”的知识，这在未来引入多风格文档时会变得复杂。

### 目标
1.  创建 `stitcher/app/services/differ.py`：封装文本 Diff 逻辑。
2.  创建 `stitcher/app/services/merger.py`：封装 `DocstringIR` 的合并逻辑，确保在覆盖更新时保留 `Addon` 数据。
3.  重构 `CheckRunner` 使用 `Differ` 服务。
4.  重构 `PumpRunner` 使用 `Differ` 和 `Merger` 服务，并简化其主循环逻辑。
5.  在 `StitcherApp` 中注册并注入这些新服务。

### 基本原理
-   **单一职责原则 (SRP)**: Runner 应该只负责协调流程，不应该关心具体的文本对比算法或对象合并策略。
-   **为扩展做准备**: `DocstringMerger` 现在的逻辑很简单（保留 Addon），但未来它需要处理字段级合并（例如保留旧参数描述但更新类型）。现在建立这个抽象层可以避免未来修改 Runner 代码。
-   **DRY**: 消除 `CheckRunner` 和 `PumpRunner` 之间重复的 diff 代码。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/docstring #scope/core #ai/instruct
#task/domain/architecture #task/object/core-services #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 Differ 服务

封装 `difflib` 调用，提供统一的接口。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/differ.py
~~~~~
~~~~~python
import difflib
from typing import List


class Differ:
    """
    Service responsible for generating human-readable differences between text or objects.
    """

    def generate_text_diff(
        self, a: str, b: str, label_a: str = "old", label_b: str = "new"
    ) -> str:
        """
        Generates a unified diff string between two text blocks.
        """
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )
~~~~~

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/differ.stitcher.yaml
~~~~~
~~~~~yaml
"Differ": |-
  Service responsible for calculating and rendering differences.
"Differ.generate_text_diff": |-
  Generates a standard unified diff between two strings.
~~~~~

#### Acts 2: 创建 Merger 服务

封装文档对象模型的合并逻辑，特别是确保在覆盖操作时保留插件数据。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/merger.py
~~~~~
~~~~~python
import copy
from typing import Optional
from stitcher.spec import DocstringIR


class DocstringMerger:
    """
    Service responsible for merging DocstringIR objects.
    Encapsulates strategies for resolving conflicts and preserving data (like Addons).
    """

    def merge(
        self, base: Optional[DocstringIR], incoming: DocstringIR
    ) -> DocstringIR:
        """
        Merges an incoming docstring (usually from source code) into a base docstring (usually from YAML).

        Strategy:
        - The `incoming` content (summary/sections) takes precedence (Overwrite).
        - The `base` metadata (Addons) is preserved.

        Args:
            base: The existing documentation (can be None if new).
            incoming: The new documentation from source.

        Returns:
            A new DocstringIR object representing the merged state.
        """
        # If there is no base, there is nothing to preserve.
        if not base:
            return incoming

        # Create a deep copy of incoming to serve as the result foundation
        # We use incoming as the base for content because this is an "Overwrite/Update" merge.
        merged = copy.deepcopy(incoming)

        # Preserve Addons from base
        # This is the critical logic: Code changes shouldn't wipe out manual addons.
        if base.addons:
            merged.addons = copy.deepcopy(base.addons)

        # Future Phase: Smart merging of sections (e.g. keep parameter descriptions if missing in code)
        # would happen here.

        return merged
~~~~~

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/merger.stitcher.yaml
~~~~~
~~~~~yaml
"DocstringMerger": |-
  Service responsible for merging conflicting DocstringIR objects.
"DocstringMerger.merge": |-
  Merges an incoming docstring into a base docstring, preserving addons from the base.
~~~~~

#### Acts 3: 注册新服务

更新 `services/__init__.py` 以导出新类。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python.old
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .stub_package_manager import StubPackageManager
from .scanner import ScannerService

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "StubPackageManager",
    "ScannerService",
]
~~~~~
~~~~~python.new
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .stub_package_manager import StubPackageManager
from .scanner import ScannerService
from .differ import Differ
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "StubPackageManager",
    "ScannerService",
    "Differ",
    "DocstringMerger",
]
~~~~~

#### Acts 4: 重构 CheckRunner

移除私有的 `_generate_diff`，转而注入并使用 `Differ` 服务。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.interaction_handler = interaction_handler

    def _generate_diff(self, a: str, b: str, label_a: str, label_b: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )

    def _analyze_file(
        self, module: ModuleDef
~~~~~
~~~~~python.new
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    Differ,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
        self.interaction_handler = interaction_handler

    def _analyze_file(
        self, module: ModuleDef
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                sig_diff = None
                if baseline_sig_text and current_sig_text:
                    sig_diff = self._generate_diff(
                        baseline_sig_text,
                        current_sig_text,
                        "baseline",
                        "current",
                    )
                elif current_sig_text:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_text}"

                conflict_type = (
~~~~~
~~~~~python.new
            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                sig_diff = None
                if baseline_sig_text and current_sig_text:
                    sig_diff = self.differ.generate_text_diff(
                        baseline_sig_text,
                        current_sig_text,
                        "baseline",
                        "current",
                    )
                elif current_sig_text:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_text}"

                conflict_type = (
~~~~~

#### Acts 5: 重构 PumpRunner

注入 `Differ` 和 `Merger`，移除重复代码，并简化 `run` 循环中的合并逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.interaction_handler = interaction_handler

    def _generate_diff(self, a: str, b: str, label_a: str, label_b: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )

    def _generate_execution_plan(
~~~~~
~~~~~python.new
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        differ: Differ,
        merger: DocstringMerger,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.differ = differ
        self.merger = merger
        self.interaction_handler = interaction_handler

    def _generate_execution_plan(
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if not res["success"]:
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)
                    for key in res["conflicts"]:
                        # Extract summaries for diffing
                        yaml_summary = yaml_docs[key].summary if key in yaml_docs else ""
                        src_summary = source_docs[key].summary if key in source_docs else ""
                        
                        doc_diff = self._generate_diff(
                            yaml_summary or "",
                            src_summary or "",
                            "yaml",
                            "code",
                        )
                        all_conflicts.append(
                            InteractionContext(
                                module.file_path,
                                key,
                                ConflictType.DOC_CONTENT_CONFLICT,
                                doc_diff=doc_diff,
                            )
                        )
~~~~~
~~~~~python.new
                if not res["success"]:
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)
                    for key in res["conflicts"]:
                        # Extract summaries for diffing
                        yaml_summary = yaml_docs[key].summary if key in yaml_docs else ""
                        src_summary = source_docs[key].summary if key in source_docs else ""

                        doc_diff = self.differ.generate_text_diff(
                            yaml_summary or "",
                            src_summary or "",
                            "yaml",
                            "code",
                        )
                        all_conflicts.append(
                            InteractionContext(
                                module.file_path,
                                key,
                                ConflictType.DOC_CONTENT_CONFLICT,
                                doc_diff=doc_diff,
                            )
                        )
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if plan.hydrate_yaml:
                    if fqn in source_docs:
                        src_ir = source_docs[fqn]
                        existing_ir = new_yaml_docs.get(fqn)
                        
                        # Preserve addons if updating
                        if existing_ir:
                            src_ir.addons = existing_ir.addons
                        
                        if existing_ir != src_ir:
                            new_yaml_docs[fqn] = src_ir
                            updated_keys_in_file.append(fqn)
                            file_had_updates = True
~~~~~
~~~~~python.new
                if plan.hydrate_yaml:
                    if fqn in source_docs:
                        src_ir = source_docs[fqn]
                        existing_ir = new_yaml_docs.get(fqn)

                        # Use merger service to handle logic (e.g. preserve addons)
                        merged_ir = self.merger.merge(existing_ir, src_ir)

                        if existing_ir != merged_ir:
                            new_yaml_docs[fqn] = merged_ir
                            updated_keys_in_file.append(fqn)
                            file_had_updates = True
~~~~~

#### Acts 6: 在 StitcherApp 中组装

更新 `core.py`，实例化新服务并将其传递给 Runner。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
)
from .protocols import InteractionHandler
~~~~~
~~~~~python.new
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from .protocols import InteractionHandler
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            transformer,
            interaction_handler,
        )
~~~~~
~~~~~python.new
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
        )
~~~~~

### 下一步建议
我们已经完成了 Pre-Phase 2 的核心解耦工作。现在的 Runner 更加干净，且对 `Addon` 插件数据的保护已经被封装到了 `DocstringMerger` 中。

下一步，我们可以：
1.  **Phase 2**: 开始引入 `Griffe` 解析器和结构化 Renderer（Google/NumPy 风格支持）。由于我们已经有了 `Differ` 和 `Merger`，可以更容易地扩展它们来处理结构化 Diff 和字段级合并。
2.  **完善测试**: 针对新的 `Merger` 服务编写单元测试，验证其在各种场景下（特别是 Addon 存在时）的合并行为是否符合预期。
