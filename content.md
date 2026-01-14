## [WIP] feat: 注册 Sidecar 索引器并接入 DocumentManager

### 用户需求
将 Sidecar 提升为一等索引公民。上一阶段已创建适配器，本阶段需完成注册和消费逻辑，实现从索引读取 Sidecar 数据，替代文件系统读取。

### 评论
本计划执行核心的“连线”工作。
1.  **简化适配器**: 决定将 Sidecar 数据以“View Data (JSON)”形式直接存储在索引中，避免在索引阶段进行提前序列化（因为此时不知道针对该文件的具体 docstring_style 配置）。
2.  **重构 DocumentManager**: 增加 `load_docs_from_index` 逻辑，优先查库。
3.  **重组 StitcherApp**: 调整初始化顺序，确保 IndexStore 在 DocumentManager 之前就绪，并注册新的 Adapter。

### 目标
1.  修改 `SidecarIndexerAdapter`，移除对 `serializer` 的依赖，直接存储 JSON 化的 YAML 值。
2.  修改 `DocumentManager`，注入 `IndexStore`，并实现从索引符号反序列化文档的逻辑。
3.  在 `StitcherApp` 中注册 `.stitcher.yaml` 的索引适配器。

### 基本原理
**View Data Storage Strategy**:
Sidecar 文件本质上是结构化数据（YAML）。由于不同的文件可能对应不同的 Docstring Style (Google/Numpy/Raw)，且该配置是在 Runtime 通过 `pyproject.toml` 决定的，而索引是全局且预先构建的。因此，索引器不应尝试解析 IR，而应原样存储 YAML 数据结构（View Data）。
`DocumentManager` 在读取时，已知晓当前的 Style 配置，此时再将 View Data 反序列化为 IR 是最安全、灵活的做法。

### 标签
#intent/refine #intent/architect #flow/draft #priority/high #comp/indexer #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/indexing #task/object/sidecar #task/action/integrate

---

### Script

#### Acts 1: 简化 `SidecarIndexerAdapter`
移除序列化逻辑，改为直接存储 View Data。

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/indexer.py
~~~~~
~~~~~python
import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Any, Optional

from ruamel.yaml import YAML

from stitcher.spec import URIGeneratorProtocol, DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_doc_references
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarIndexerAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
    ):
        self.root_path = root_path
        self.uri_generator = uri_generator
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        # Only process .stitcher.yaml files
        if not file_path.name.endswith(".stitcher.yaml"):
            return symbols, references

        # 1. Parse YAML to get data structure
        try:
            data = self._yaml.load(content)
        except Exception:
            return symbols, references

        if not isinstance(data, dict):
            return symbols, references

        # 2. Determine paths
        # file_path passed here is relative to project root (physical path)
        # We need to determine the companion Python file path for references
        py_name = file_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = file_path.with_name(py_name)
        
        # 3. Parse references with location info using the helper
        loc_map = {frag: (line, col) for frag, line, col in parse_doc_references(content)}

        for fragment, value in data.items():
            # Skip if it's not a valid key
            if not isinstance(fragment, str):
                continue
            
            # --- Build Symbol ---
            suri = self.uri_generator.generate_symbol_uri(str(file_path), fragment)
            lineno, col_offset = loc_map.get(fragment, (0, 0))
            
            # STORE STRATEGY: Store raw View Data as JSON.
            # We don't convert to IR here because we don't know the docstring style yet.
            try:
                # Value is the ruamel object (str or dict/map), json dump it to store
                docstring_content_json = json.dumps(value, default=str, sort_keys=True)
                docstring_hash = hashlib.sha256(docstring_content_json.encode("utf-8")).hexdigest()
            except Exception:
                docstring_content_json = "{}"
                docstring_hash = "0" * 64

            symbol = SymbolRecord(
                id=suri,
                name=fragment,
                kind="doc_fragment",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset,
                logical_path=fragment,
                canonical_fqn=fragment, 
                docstring_content=docstring_content_json,
                docstring_hash=docstring_hash,
                signature_hash=None,
                signature_text=None,
                alias_target_fqn=None,
                alias_target_id=None
            )
            symbols.append(symbol)

            # --- Build Reference (Binding to Python) ---
            python_suri = f"py://{py_path_rel}#{fragment}"
            if fragment == "__doc__":
                python_suri = f"py://{py_path_rel}"
            
            ref = ReferenceRecord(
                source_file_id=None,
                target_fqn=None,
                target_id=python_suri,
                kind="doc_binding",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset + len(fragment)
            )
            references.append(ref)

        return symbols, references
~~~~~

#### Acts 2: 更新 `DocumentManager`
使其依赖 `IndexStore` 并实现从索引读取逻辑。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~
~~~~~python.old
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from stitcher.spec.index import SymbolRecord

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
from .adapter import SidecarAdapter


class DocumentManager:
    def __init__(self, root_path: Path, uri_generator: URIGeneratorProtocol):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)
        self._sidecar_adapter = SidecarAdapter(root_path, uri_generator)
        # Defaults to Raw mode for backward compatibility
        self.parser: DocstringParserProtocol = RawDocstringParser()
        self.serializer: DocstringSerializerProtocol = RawSerializer()
~~~~~
~~~~~python.new
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from stitcher.spec.index import SymbolRecord

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
    URIGeneratorProtocol,
    IndexStoreProtocol,
)
from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from .adapter import SidecarAdapter


class DocumentManager:
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
        index_store: Optional[IndexStoreProtocol] = None,
    ):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)
        self._sidecar_adapter = SidecarAdapter(root_path, uri_generator)
        self.index_store = index_store
        # Defaults to Raw mode for backward compatibility
        self.parser: DocstringParserProtocol = RawDocstringParser()
        self.serializer: DocstringSerializerProtocol = RawSerializer()
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~
~~~~~python.old
    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)
        return self._sidecar_adapter.load_doc_irs(doc_path, self.serializer)
~~~~~
~~~~~python.new
    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)

        # 1. Try loading from Index (Unified Data Model)
        if self.index_store:
            try:
                rel_doc_path = doc_path.relative_to(self.root_path).as_posix()
                symbols = self.index_store.get_symbols_by_file_path(rel_doc_path)
                # If we have symbols (even if empty list, meaning file tracked but empty), we trust index.
                # However, if the file is not in index (get_symbols returns []), it might be untracked or new.
                # For robustness, if symbols is empty list, we double check if file exists on disk?
                # Actually, StitcherApp ensures index freshness.
                if symbols:
                    return self._hydrate_from_symbols(symbols)
            except ValueError:
                # Path issue (e.g. peripheral), fallback to IO
                pass

        # 2. Fallback to File IO (Legacy/No-Index mode)
        return self._sidecar_adapter.load_doc_irs(doc_path, self.serializer)

    def _hydrate_from_symbols(
        self, symbols: List["SymbolRecord"]
    ) -> Dict[str, DocstringIR]:
        docs = {}
        for sym in symbols:
            # We only care about doc fragments here
            if sym.kind != "doc_fragment" or not sym.docstring_content:
                continue

            try:
                # The content in DB is JSON-serialized View Data (from SidecarIndexerAdapter)
                view_data = json.loads(sym.docstring_content)
                # Convert View Data -> IR using the current configured strategy
                ir = self.serializer.from_view_data(view_data)
                docs[sym.name] = ir
            except Exception:
                # If data is corrupt, skip
                continue
        return docs
~~~~~

#### Acts 3: 重组 `StitcherApp` 初始化逻辑
调整 `packages/stitcher-application/src/stitcher/app/core.py`，改变初始化顺序并注册 Adapter。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python import PythonURIGenerator


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        self.fingerprint_strategy = fingerprint_strategy
        self.uri_generator: URIGeneratorProtocol = PythonURIGenerator()
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path, self.uri_generator)
        self.lock_manager = LockFileManager()
        self.uri_generator: URIGeneratorProtocol = PythonURIGenerator()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 2. Indexing Subsystem (Must be initialized before runners that use it)
        index_db_path = root_path / ".stitcher" / "index" / "index.db"
        self.db_manager = DatabaseManager(index_db_path)
        self.index_store = IndexStore(self.db_manager)
        self.file_indexer = FileIndexer(root_path, self.index_store)

        # Register Adapters
        search_paths = self.workspace.get_search_paths()
        python_adapter = PythonAdapter(
            root_path, search_paths, uri_generator=self.uri_generator
        )
        self.file_indexer.register_adapter(".py", python_adapter)

        # 3. Runners (Command Handlers)
~~~~~
~~~~~python.new
from stitcher.lang.sidecar import LockFileManager, SidecarIndexerAdapter, SidecarURIGenerator
from stitcher.lang.python import PythonURIGenerator


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        self.fingerprint_strategy = fingerprint_strategy
        self.uri_generator: URIGeneratorProtocol = PythonURIGenerator()

        # 1. Indexing Subsystem (Promoted to Priority 1 initialization)
        index_db_path = root_path / ".stitcher" / "index" / "index.db"
        self.db_manager = DatabaseManager(index_db_path)
        self.index_store = IndexStore(self.db_manager)
        self.file_indexer = FileIndexer(root_path, self.index_store)

        # 2. Core Services
        # DocumentManager now depends on IndexStore
        self.doc_manager = DocumentManager(root_path, self.uri_generator, self.index_store)
        self.lock_manager = LockFileManager()
        # self.uri_generator instantiated above
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 3. Register Adapters
        search_paths = self.workspace.get_search_paths()
        
        # Python Adapter
        python_adapter = PythonAdapter(
            root_path, search_paths, uri_generator=self.uri_generator
        )
        self.file_indexer.register_adapter(".py", python_adapter)

        # Sidecar Adapter (NEW)
        sidecar_uri_generator = SidecarURIGenerator()
        sidecar_adapter = SidecarIndexerAdapter(root_path, sidecar_uri_generator)
        self.file_indexer.register_adapter(".stitcher.yaml", sidecar_adapter)

        # 4. Runners (Command Handlers)
~~~~~

### 下一步建议
我们已经完成了 Sidecar 到索引的集成。为了验证架构的正确性，我们需要添加一个端到端测试，模拟一个包含 `.stitcher.yaml` 的项目，运行 `check` 命令，并验证 `DocumentManager` 能够正确地从索引中读取文档数据。
