因此，我提议将当前任务的目标从“添加更多日志”**变更为**“构建一个工作区上下文感知的索引适配器”。只有在这个基础组件就位后，我们才能在确定性的基础上继续原有的开发任务。

我将生成一份新的计划，其唯一目标是：
1.  **移除**之前添加的诊断日志。
2.  **重构** `PythonAdapter`，使其能够感知并利用`Workspace`提供的源码根信息来生成正确的`canonical_fqn`。
3.  **修复**测试辅助函数`create_populated_index`，使其在创建索引时正确地初始化`PythonAdapter`。

这将从根本上解决所有与重命名相关的测试失败。

## [WIP] fix: 使索引适配器感知工作区以生成正确的FQN

### 错误分析

所有与符号重命名相关的测试失败，根源在于索引器（`PythonAdapter`）在生成符号的完全限定名（`canonical_fqn`）时存在一个根本性缺陷。它错误地将文件的物理路径从项目根目录（`root_path`）开始计算，而不是从其所属的源码根（例如`src/`目录）开始计算。

这导致数据库中存储的`canonical_fqn`包含了`packages/pkg_name/src`等多余的前缀，使得重构引擎使用正确的、逻辑上的FQN（如`stitcher.core.bus.MessageBus`）进行查询时，永远无法匹配到符号的定义记录。因此，重命名操作只影响了被正确索引的“引用”，而定义本身从未被修改。

### 用户需求

修复索引器，使其能够为Monorepo和`src`布局下的代码文件生成正确的、符合Python导入规则的`canonical_fqn`。

### 评论

这是一个对整个重构和索引引擎的基石性修复。它纠正了系统对代码结构的核心认知，确保了“物理路径”到“逻辑身份”转换的正确性。此修复将使系统能够正确理解复杂的项目布局，是实现可靠重构的先决条件。

### 目标

1.  **移除**在`SemanticGraph.find_usages`中添加的临时诊断日志。
2.  **重构`PythonAdapter`**：
    *   修改其构造函数，使其接受一个`Workspace`对象而非`root_path`。
    *   实现一个内部方法，用于根据给定的文件路径从`Workspace`中解析出正确的源码根目录。
    *   更新FQN的生成逻辑，确保相对路径是基于其源码根计算的。
3.  **更新测试辅助函数`create_populated_index`**：
    *   使其创建并使用一个`Workspace`对象来正确地初始化`PythonAdapter`。

### 基本原理

我们将引入“源码根感知”能力来解决此问题。

1.  `PythonAdapter`将不再是一个无状态的路径处理器，它将持有对整个`Workspace`模型的引用。
2.  在解析每个文件之前，它会调用一个新的私有方法 `_get_source_root_for_file`。该方法遍历`workspace.import_to_source_dirs`，找到包含当前文件的、最具体的源码根目录。
3.  一旦确定了源码根，`canonical_fqn`的计算将基于`file_path.relative_to(source_root)`，从而得到正确的Python模块路径。
4.  测试工具`create_populated_index`也将被修正，以模拟这种真实的应用初始化流程，确保测试环境与实际运行环境的一致性。

这个战略性修复将从源头上保证索引数据的正确性，从而使整个重构流水线恢复正常。

### 标签

#intent/fix #flow/ready #priority/critical #comp/refactor #comp/index #comp/python-adapter #comp/tests #concept/fqn #scope/core #ai/brainstorm #task/domain/refactor #task/object/definition-renaming #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 清理诊断日志

首先，我们移除上一轮添加的、现已不再需要的诊断日志。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def find_usages(self, target_fqn: str) -> List[UsageLocation]:
        """
        Query the Index DB for ALL occurrences of an FQN, including its
        definition and all references. Maps DB records to UsageLocation objects.
        """
        log.debug(f"--- RENAME DEBUG: Finding all usages for FQN: {target_fqn} ---")
        usages = []

        # 1. Find all references (usages)
        db_refs = self.index_store.find_references(target_fqn)
        log.debug(f"Found {len(db_refs)} references from DB:")
        for ref, file_path_str in db_refs:
            abs_path = self.root_path / file_path_str
            try:
                ref_type = ReferenceType(ref.kind)
            except ValueError:
                ref_type = ReferenceType.SYMBOL  # Fallback

            location = UsageLocation(
                file_path=abs_path,
                lineno=ref.lineno,
                col_offset=ref.col_offset,
                end_lineno=ref.end_lineno,
                end_col_offset=ref.end_col_offset,
                ref_type=ref_type,
                target_node_fqn=ref.target_fqn,
            )
            log.debug(f"  - REF: {location}")
            usages.append(location)

        # 2. Find the definition itself and treat it as a usage site
        definition_result = self.index_store.find_symbol_by_fqn(target_fqn)
        log.debug(f"Found definition from DB: {definition_result}")
        if definition_result:
            symbol, file_path_str = definition_result
            abs_path = self.root_path / file_path_str
            location = UsageLocation(
                file_path=abs_path,
                lineno=symbol.lineno,
                col_offset=symbol.col_offset,
                end_lineno=symbol.end_lineno,
                end_col_offset=symbol.end_col_offset,
                ref_type=ReferenceType.SYMBOL,  # A definition is a symbol site
                target_node_fqn=symbol.canonical_fqn or target_fqn,
            )
            log.debug(f"  - DEF: {location}")
            usages.append(location)

        log.debug(f"--- RENAME DEBUG: Total locations for '{target_fqn}': {len(usages)} ---")
        return usages
~~~~~
~~~~~python.new
    def find_usages(self, target_fqn: str) -> List[UsageLocation]:
        """
        Query the Index DB for ALL occurrences of an FQN, including its
        definition and all references. Maps DB records to UsageLocation objects.
        """
        usages = []

        # 1. Find all references (usages)
        db_refs = self.index_store.find_references(target_fqn)
        for ref, file_path_str in db_refs:
            abs_path = self.root_path / file_path_str
            try:
                ref_type = ReferenceType(ref.kind)
            except ValueError:
                ref_type = ReferenceType.SYMBOL  # Fallback

            usages.append(
                UsageLocation(
                    file_path=abs_path,
                    lineno=ref.lineno,
                    col_offset=ref.col_offset,
                    end_lineno=ref.end_lineno,
                    end_col_offset=ref.end_col_offset,
                    ref_type=ref_type,
                    target_node_fqn=ref.target_fqn,
                )
            )

        # 2. Find the definition itself and treat it as a usage site
        definition_result = self.index_store.find_symbol_by_fqn(target_fqn)
        if definition_result:
            symbol, file_path_str = definition_result
            abs_path = self.root_path / file_path_str
            usages.append(
                UsageLocation(
                    file_path=abs_path,
                    lineno=symbol.lineno,
                    col_offset=symbol.col_offset,
                    end_lineno=symbol.end_lineno,
                    end_col_offset=symbol.end_col_offset,
                    ref_type=ReferenceType.SYMBOL,  # A definition is a symbol site
                    target_node_fqn=symbol.canonical_fqn or target_fqn,
                )
            )

        return usages
~~~~~

#### Acts 2: 使 PythonAdapter 感知工作区

我们将重写`index_adapter.py`，注入`Workspace`依赖，并实现正确的FQN生成逻辑。

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
from stitcher.refactor.workspace import Workspace

import libcst as cst
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python.fingerprint import PythonFingerprintStrategy
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry
from stitcher.python.analysis.scope import ScopeAnalyzer
from stitcher.python.analysis.utils import path_to_logical_fqn
from .uri import SURIGenerator


class PythonAdapter(LanguageAdapter):
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.parser = GriffePythonParser()
        self.hasher = PythonFingerprintStrategy()

    def _get_source_root_for_file(self, file_path: Path) -> Path:
        """Finds the deepest matching source root for a given file."""
        longest_match: Optional[Path] = None
        for source_roots in self.workspace.import_to_source_dirs.values():
            for root in source_roots:
                try:
                    if file_path.is_relative_to(root):
                        if longest_match is None or len(root.parts) > len(
                            longest_match.parts
                        ):
                            longest_match = root
                except ValueError:  # For Python < 3.9, is_relative_to may not exist
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
        # Note: ScopeAnalyzer returns a map of {local_name: target_fqn}
        # We don't need to manually use it here because UsageScanVisitor uses it internally?
        # Wait, UsageScanVisitor takes local_symbols as input.
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
            # UsageRegistry structure: { target_fqn: [UsageLocation, ...] }
            for target_fqn, locations in registry.get_all_usages().items():
                for loc in locations:
                    refs.append(
                        ReferenceRecord(
                            target_fqn=target_fqn,  # Store the logical intent directly
                            target_id=None,  # Decoupled: Linker will fill this
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

#### Acts 3: 修复测试辅助函数

最后，我们修复`stitcher-test-utils`中的`create_populated_index`，使其正确初始化`PythonAdapter`。

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

    # The scanner needs a workspace-aware adapter
    workspace = Workspace(root_path)
    scanner = WorkspaceScanner(root_path, store)
    scanner.register_adapter(".py", PythonAdapter(workspace))
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

### 下一步建议

我们已经实施了根本性的修复。请再次运行完整的测试套件。这次，所有与重命名相关的测试都应该通过，因为索引器现在能够正确地识别和存储每个符号的`canonical_fqn`，使得定义和引用都能被重构引擎准确无误地定位。

```bash
pytest
```
