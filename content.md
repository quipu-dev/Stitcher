[简要回答]
好的，我将重构 `DocumentManager`，解除其对 `ModuleDef` AST 的强依赖，并添加基于文件路径和索引符号的文档一致性检查方法。

## [WIP] refactor: 解耦 DocumentManager 并支持 Index-First 检查

### 用户需求
为了实现 Stitcher 2.0 的 Index-First 架构，`DocumentManager` 需要能够独立于昂贵的 AST 解析（`ModuleDef`）运行。它需要能够直接通过文件路径加载 YAML 文档，并使用来自 `stitcher-index` 的 `SymbolRecord` 列表来进行结构一致性检查（Missing/Extra）。

### 评论
这是架构转型的关键一步。通过解除对 `ModuleDef` 的依赖，我们将能够构建出无需读取和解析所有 Python 源代码即可运行的 `CheckRunner`，从而大幅提升性能。

### 目标
1.  在 `DocumentManager` 中添加 `load_docs_for_path` 方法。
2.  在 `DocumentManager` 中添加 `compute_yaml_hashes_for_path` 方法。
3.  在 `DocumentManager` 中添加 `check_consistency_with_symbols` 方法，利用 `SymbolRecord` 列表替代 `ModuleDef` 进行结构检查。

### 基本原理
目前的 `DocumentManager` API 均要求传入 `ModuleDef` 对象，这迫使调用者（如 `CheckRunner`）必须先进行源码解析。通过重构，我们将允许通过更轻量的 `file_path` 和数据库记录来进行操作。这符合 Index-First 的 "Query-First" 设计原则。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/doc-manager #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 DocumentManager

我们将修改 `doc_manager.py`，添加支持路径和符号列表的新方法，并让旧方法复用新逻辑以保持兼容性。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
from typing import Dict, Optional, Any, Union

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
)
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
~~~~~
~~~~~python.new
from typing import Dict, Optional, Any, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from stitcher.index.types import SymbolRecord

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
)
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = self.resolver.get_doc_path(module_path)

        raw_data = self.adapter.load(doc_path)  # returns Dict[str, Any] now ideally

        # Adapter.load is typed to return Dict[str, str], but YamlAdapter actually returns parsed YAML.
        # We assume YamlAdapter can return Dict[str, Union[str, Dict]]

        return {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}

    def _apply_to_function(
~~~~~
~~~~~python.new
    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)

        raw_data = self.adapter.load(doc_path)
        return {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        return self.load_docs_for_path(module.file_path)

    def _apply_to_function(
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
        return {
            "extra": extra,
            "missing": missing_doc,
            "pending": pending_hydration,
            "redundant": redundant_doc,
            "conflict": doc_conflict,
        }

    def hydrate_module(
~~~~~
~~~~~python.new
        return {
            "extra": extra,
            "missing": missing_doc,
            "pending": pending_hydration,
            "redundant": redundant_doc,
            "conflict": doc_conflict,
        }

    def check_consistency_with_symbols(
        self, file_path: str, actual_symbols: List["SymbolRecord"]
    ) -> Dict[str, set]:
        """
        Performs structural consistency check using Index Symbols instead of AST.
        Note: This does NOT check for content conflicts (doc_conflict) or redundancy,
        as that requires source content. It focuses on Missing and Extra keys.
        """
        # 1. Extract keys from symbols
        all_keys = set()
        public_keys = set()

        for sym in actual_symbols:
            key = None
            if sym.kind == "module":
                key = "__doc__"
            elif sym.logical_path:
                key = sym.logical_path

            if key:
                all_keys.add(key)
                # Check for visibility (simple underscore check on components)
                # logical_path 'A.B._c' -> parts ['A', 'B', '_c']
                parts = key.split(".")
                if not any(p.startswith("_") and p != "__doc__" for p in parts):
                    public_keys.add(key)

        # 2. Load YAML keys
        yaml_docs = self.load_docs_for_path(file_path)
        yaml_keys = set(yaml_docs.keys())

        # 3. Compare
        extra = yaml_keys - all_keys
        extra.discard("__doc__")  # __doc__ in yaml is fine even if not explicitly tracked sometimes?
        # Actually, if it's in yaml but not in code (e.g. empty file?), it is extra.
        # But 'module' symbol usually exists.

        missing_doc = set()

        for key in all_keys:
            if key in public_keys and key not in yaml_keys:
                missing_doc.add(key)

        return {
            "extra": extra,
            "missing": missing_doc,
            # Pending/Redundant/Conflict require source content comparison, skipped here.
            "pending": set(),
            "redundant": set(),
            "conflict": set(),
        }

    def hydrate_module(
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        # We need raw data here to compute the hash exactly as it is stored
        # But load_docs_for_module returns IRs.
        # We should load raw data directly from adapter for hashing.

        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = self.resolver.get_doc_path(module_path)

        # Load raw dict from YAML
        raw_data = self.adapter.load(doc_path)

        return {
            fqn: self.compute_yaml_content_hash(val) for fqn, val in raw_data.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
~~~~~
~~~~~python.new
        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_hashes_for_path(self, file_path: str) -> Dict[str, str]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)

        raw_data = self.adapter.load(doc_path)

        return {
            fqn: self.compute_yaml_content_hash(val) for fqn, val in raw_data.items()
        }

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        return self.compute_yaml_hashes_for_path(module.file_path)

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
~~~~~

### 下一步建议
现在 `DocumentManager` 已经具备了独立工作的能力。下一步，我们将重写 `CheckRunner`，使其不再扫描 AST，而是从 `stitcher-index` 获取数据，并调用这些新方法执行检查。
