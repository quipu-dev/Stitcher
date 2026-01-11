我将生成一份新的、架构上正确的计划。其唯一目标是：
1.  修改 `PythonAdapter` 的构造函数，使其接受一个简单的 `search_paths: List[Path]` 参数，而不是整个 `Workspace` 对象。
2.  修改 `PythonAdapter` 内部的逻辑，使其使用这个 `search_paths` 列表来确定正确的源码根。
3.  修改上游的调用方（即测试辅助函数 `create_populated_index`），由它负责创建 `Workspace` 实例，从中提取 `search_paths`，然后将其传递给 `PythonAdapter`。

这个方案既满足了 `PythonAdapter` 对上下文信息的需求，又彻底切断了与 `stitcher-refactor` 包的依赖关系，维护了清晰的架构分层。

---

## [WIP] fix(arch): 解耦 PythonAdapter 与 refactor 包以消除循环依赖

### 错误分析

我之前的修复计划引入了一个严重的架构缺陷：为了让 `PythonAdapter` 能够感知 Monorepo 的源码根（source roots），我提议将高层的 `Workspace` 对象（定义在 `stitcher-refactor` 包中）注入到低层的 `PythonAdapter`（定义在 `stitcher-python-adapter` 包中）。

这导致了一个不可接受的循环依赖关系：`adapter` -> `refactor` -> `index` -> `adapter`。低层的基础设施（如语言适配器）绝对不能依赖于使用它的高层业务逻辑（如重构引擎）。

### 用户需求

在修复 FQN 生成逻辑的同时，必须保持清晰的、无循环依赖的架构分层。

### 评论

这是一个至关重要的架构修正。通过将依赖从一个复杂的对象（`Workspace`）降级为一个简单的数据结构（`List[Path]`），我们遵循了“依赖倒置原则”的精神：高层和低层都应依赖于抽象（或简单数据），而非具体实现。这个修复不仅能解决当前的 Bug，还能保证项目的长期可维护性。

### 目标

1.  **修改 `PythonAdapter`**：
    *   更改其 `__init__` 方法，使其接受 `root_path: Path` 和 `search_paths: List[Path]`。
    *   移除对 `Workspace` 对象的依赖。
    *   更新内部逻辑，使用传入的 `search_paths` 来查找文件的源码根。
2.  **更新 `create_populated_index` 测试辅助函数**：
    *   由该函数负责实例化 `Workspace`，获取 `search_paths`，然后用这些路径来配置 `PythonAdapter`。
3.  **修复 `test_rename_symbol_definition.py` 中过时的断言**。

### 基本原理

我们将通过“依赖注入”一个简单的数据结构来解耦。

1.  更高层的组件（在测试中是 `create_populated_index`，在实际应用中会是 `StitcherApp` 或类似的引导程序）将负责构建 `Workspace` 并调用 `workspace.get_search_paths()` 来获取源码根列表。
2.  这个简单的 `List[Path]` 将被传递给 `PythonAdapter` 的构造函数。
3.  `PythonAdapter` 内部的 `_get_source_root_for_file` 方法将不再引用 `self.workspace`，而是直接遍历 `self.search_paths` 列表来找到最匹配的源码根。

这样，信息流是单向的（`Workspace` -> `search_paths` -> `PythonAdapter`），并且 `PythonAdapter` 对 `Workspace` 的存在一无所知，从而彻底解决了循环依赖问题。

### 标签

#intent/fix #intent/architect #flow/ready #priority/critical #comp/python-adapter #comp/refactor #comp/tests #concept/architecture #concept/dependency-inversion #scope/core #ai/refine #task/domain/refactor #task/object/definition-renaming #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 PythonAdapter 的依赖和逻辑

我们将重构`PythonAdapter`，使其不再依赖`Workspace`，而是依赖一个简单的`search_paths`列表。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Tuple, Optional

from stitcher.spec import ModuleDef
from stitcher.index.protocols import LanguageAdapter
from stitcher.index.types import SymbolRecord, ReferenceRecord

import libcst as cst
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python.fingerprint import PythonFingerprintStrategy
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry
from stitcher.python.analysis.scope import ScopeAnalyzer
from stitcher.python.analysis.utils import path_to_logical_fqn
from .uri import SURIGenerator


class PythonAdapter(LanguageAdapter):
    def __init__(self, root_path: Path, search_paths: List[Path]):
        self.root_path = root_path
        self.search_paths = search_paths
        self.parser = GriffePythonParser()
        self.hasher = PythonFingerprintStrategy()

    def _get_source_root_for_file(self, file_path: Path) -> Path:
        """Finds the deepest matching source root for a given file."""
        longest_match: Optional[Path] = None
        for root in self.search_paths:
            try:
                if file_path.is_relative_to(root):
                    if longest_match is None or len(root.parts) > len(
                        longest_match.parts
                    ):
                        longest_match = root
            except ValueError:  # For Python < 3.9 compatibility
                if str(file_path).startswith(str(root)):
                    if longest_match is None or len(root.parts) > len(
                        longest_match.parts
                    ):
                        longest_match = root
        return longest_match or self.root_path

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        # 1. Determine the correct source root and calculate relative path for FQN
        source_root = self._get_source_root_for_file(file_path)
        fqn_rel_path = file_path.relative_to(source_root).as_posix()

        # Physical rel_path for SURI should always be from project root
        physical_rel_path = file_path.relative_to(self.root_path).as_posix()

        # 2. Parse into ModuleDef
        module_def = self.parser.parse(content, file_path=physical_rel_path)

        # Pre-calculate logical FQN for the module using the correct relative path
        logical_module_fqn = path_to_logical_fqn(fqn_rel_path)

        # 3. Project to Symbols
        symbols = self._extract_symbols(
            physical_rel_path, module_def, logical_module_fqn
        )

        # 4. Project to References
        references = self._extract_references(
            physical_rel_path, module_def, content, file_path, logical_module_fqn
        )

        return symbols, references

    def _extract_symbols(
        self, rel_path: str, module: ModuleDef, logical_module_fqn: str
    ) -> List[SymbolRecord]:
        symbols: List[SymbolRecord] = []

        # 0. Module Symbol (The file/module itself)
        # This allows other files to import this module.
        module_name = logical_module_fqn.split(".")[-1]
        module_suri = SURIGenerator.for_file(rel_path)

        symbols.append(
            SymbolRecord(
                id=module_suri,
                name=module_name,
                kind="module",
                lineno=0,
                col_offset=0,
                end_lineno=0,
                end_col_offset=0,
                logical_path=None,  # Module root has no logical path suffix
                canonical_fqn=logical_module_fqn,
                alias_target_fqn=None,
                alias_target_id=None,
                signature_hash=None,
            )
        )

        # Helper to add symbol
        def add(
            name: str,
            kind: str,
            entity_for_hash: Optional[object] = None,
            parent_fragment: str = "",
        ):
            fragment = f"{parent_fragment}.{name}" if parent_fragment else name
            suri = SURIGenerator.for_symbol(rel_path, fragment)
            canonical_fqn = f"{logical_module_fqn}.{fragment}"

            # Compute Hash
            sig_hash = None
            if entity_for_hash:
                fp = self.hasher.compute(entity_for_hash)  # type: ignore
                sig_hash = fp.get("current_code_structure_hash")

            # Location Handling
            loc = getattr(entity_for_hash, "location", None)

            # Alias Handling
            alias_target_fqn: Optional[str] = None
            final_kind = kind

            # Check for alias target in the entity
            target_attr = getattr(entity_for_hash, "alias_target", None)
            if target_attr:
                final_kind = "alias"
                alias_target_fqn = target_attr

            symbols.append(
                SymbolRecord(
                    id=suri,
                    name=name,
                    kind=final_kind,
                    lineno=loc.lineno if loc else 0,
                    col_offset=loc.col_offset if loc else 0,
                    end_lineno=loc.end_lineno if loc else 0,
                    end_col_offset=loc.end_col_offset if loc else 0,
                    logical_path=fragment,
                    canonical_fqn=canonical_fqn,
                    alias_target_fqn=alias_target_fqn,
                    alias_target_id=None,  # Decoupled: Linker will fill this
                    signature_hash=sig_hash,
                )
            )
            return fragment

        # 1. Functions
        for func in module.functions:
            add(func.name, "function", func)

        # 2. Classes
        for cls in module.classes:
            cls_frag = add(cls.name, "class", cls)

            # Methods
            for method in cls.methods:
                add(method.name, "method", method, parent_fragment=cls_frag)

            # Attributes
            for attr in cls.attributes:
                add(attr.name, "variable", attr, parent_fragment=cls_frag)

        # 3. Module-level Attributes
        for attr in module.attributes:
            add(attr.name, "variable", attr)

        return symbols

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
        try:
            wrapper = cst.MetadataWrapper(cst.parse_module(content))
            registry = UsageRegistry()

            visitor = UsageScanVisitor(
                file_path=file_path,
                local_symbols=local_symbols,
                registry=registry,
                current_module_fqn=logical_module_fqn,
                is_init_file=rel_path.endswith("__init__.py"),
            )
            wrapper.visit(visitor)

            # 3. Convert Registry to ReferenceRecords
            for target_fqn, locations in registry.get_all_usages().items():
                for loc in locations:
                    refs.append(
                        ReferenceRecord(
                            target_fqn=target_fqn,
                            target_id=None,
                            kind=loc.ref_type.value,
                            lineno=loc.lineno,
                            col_offset=loc.col_offset,
                            end_lineno=loc.end_lineno,
                            end_col_offset=loc.end_col_offset,
                        )
                    )

        except Exception:
            # If CST parsing fails (syntax error), we just return empty refs
            pass

        return refs
~~~~~

#### Acts 2: 更新测试辅助函数的初始化逻辑

现在，我们更新`create_populated_index`，使其遵循新的、解耦的初始化流程。

~~~~~act
write_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.refactor.workspace import Workspace

from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.scanner import WorkspaceScanner
from stitcher.adapter.python.index_adapter import PythonAdapter


def create_populated_index(root_path: Path) -> IndexStore:
    """Creates a temporary IndexStore and performs a full scan."""
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The scanner needs a workspace-aware adapter.
    # The adapter itself is decoupled; the context is provided here.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    scanner = WorkspaceScanner(root_path, store)
    scanner.register_adapter(".py", PythonAdapter(root_path, search_paths))
    scanner.scan()

    return store


def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    return StitcherApp(
        root_path=root_path,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=interaction_handler,
    )


def get_stored_hashes(project_root: Path, file_path: str) -> dict:
    sig_file = (
        project_root / ".stitcher/signatures" / Path(file_path).with_suffix(".json")
    )
    if not sig_file.exists():
        return {}
    with sig_file.open("r") as f:
        return json.load(f)
~~~~~

#### Acts 3: 修正过时的测试用例

最后，我们应用之前确认的修复，更新那个现在应该通过的测试用例。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_operation_succeeds_in_renaming_symbol_definition_simple(tmp_path):
    """
    This test verifies that RenameSymbolOperation successfully renames both
    the definition and a simple import usage of a symbol.
    """
    # 1. ARRANGE: Create a project structure mirroring the scenario.
    # common/
    #   __init__.py -> from .messaging.bus import MessageBus
    #   messaging/
    #     bus.py    -> class MessageBus: pass
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("common/__init__.py", "from .messaging.bus import MessageBus")
        .with_source("common/messaging/bus.py", "class MessageBus: pass")
    ).build()

    definition_file = project_root / "common/messaging/bus.py"
    usage_file = project_root / "common/__init__.py"

    # 2. ACT: Run the refactoring operation.
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("common")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "common.messaging.bus.MessageBus", "common.messaging.bus.FeedbackBus"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT: Verify the complete refactoring.
    # The usage in __init__.py should be updated.
    updated_usage_code = usage_file.read_text()
    assert "from .messaging.bus import FeedbackBus" in updated_usage_code
    assert "from .messaging.bus import MessageBus" not in updated_usage_code

    # CRITICAL: The definition in bus.py should now be correctly updated.
    definition_code = definition_file.read_text()
    assert "class FeedbackBus: pass" in definition_code, (
        "The class definition was not renamed!"
    )
    assert "class MessageBus: pass" not in definition_code


def test_rename_operation_succeeds_in_renaming_symbol_definition(tmp_path):
    """
    This test reproduces a critical bug where RenameSymbolOperation renames
    all usages of a symbol but fails to rename the class definition itself.
    """
    # 1. ARRANGE: Create a project with a definition and a usage.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldName: pass")
        .with_source(
            "mypkg/app.py", "from mypkg.core import OldName\n\ninstance = OldName()"
        )
    ).build()

    definition_file = project_root / "mypkg/core.py"
    usage_file = project_root / "mypkg/app.py"

    # 2. ACT: Run the refactoring operation.
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.OldName", "mypkg.core.NewName")
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT: Verify the incomplete refactoring.
    # Assert that the usage file was correctly updated.
    updated_usage_code = usage_file.read_text()
    assert "from mypkg.core import NewName" in updated_usage_code
    assert "instance = NewName()" in updated_usage_code

    # Assert that the definition file WAS correctly updated.
    definition_code = definition_file.read_text()
    assert "class NewName: pass" in definition_code
    assert "class OldName: pass" not in definition_code
~~~~~

### 下一步建议

我们已经执行了一次彻底的、架构感知的修复。这个计划不仅解决了症状（错误的FQN），还根除了病因（循环依赖）。

请运行完整的测试套件。我非常有信心，这次所有测试都将通过。

```bash
pytest
```

如果测试通过，我将生成最终的`[COMMIT]`计划来结束这个任务。
