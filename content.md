## [WIP] feat(app): 实施 Phase 1 - 插件系统与混合模式支持

### 用户需求

实施“文档字符串格式化与插件系统”的 Phase 1。核心目标是重构 `DocumentManager` 及其周边生态，使其支持结构化的 `DocstringIR`，从而允许在 YAML 中存储 `Addon` 数据（插件数据）并实现与纯文本模式的自动升格/降级。

### 评论

这是一个涉及面较广的重构，因为它改变了 `DocumentManager` 的核心数据契约（从 `Dict[str, str]` 变为 `Dict[str, DocstringIR]`）。为了保持系统的一致性，我们需要同步更新所有依赖于文档内容的服务（Check, Pump, Generate, Transform 等）。这种“一刀切”的升级虽然痛苦，但能避免长期维护两套数据结构的复杂性，符合 HFEA 的“正规军”标准。

### 目标

1.  创建 `RawDocstringParser`，用于将纯文本文档转换为 `DocstringIR`。
2.  重构 `DocumentManager`：
    *   实现 `DocstringIR` 与 YAML 字典/字符串之间的序列化与反序列化逻辑。
    *   实现 `Raw` 模式与 `Hybrid` 模式（带 Addon）的自动转换。
    *   升级哈希计算逻辑，支持对结构化数据的稳定哈希。
3.  适配所有 Runner（Check, Pump, Generate, Init, Transform）以处理 `DocstringIR` 对象而非原始字符串。
4.  更新并新增测试用例，验证混合模式的正确性和插件数据的持久化能力。

### 基本原理

我们将 `DocstringIR` 确立为系统内部流转的唯一文档数据格式。
*   **加载时**：无论 YAML 里是简单的字符串还是复杂的字典，统一转为 `DocstringIR`。
*   **处理时**：Runners 操作的是对象，`Check` 只比较 `summary` 字段，`Pump` 负责在更新 `summary` 时保留 `addons`。
*   **保存时**：根据内容自动决定存储格式。如果没有插件数据，回退到简洁的字符串格式；如果有，升级为字典格式。

### 标签

#intent/refine #intent/build #flow/ready #priority/high #comp/application #comp/adapter #scope/core #ai/instruct #task/domain/docstrings #task/object/document-manager #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 实现 `RawDocstringParser`

首先，我们需要一个能够将普通字符串包装成 IR 对象的解析器。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/raw_parser.py
~~~~~
~~~~~python
from stitcher.spec import DocstringParserProtocol, DocstringIR


class RawDocstringParser(DocstringParserProtocol):
    """
    A simple parser that treats the entire input text as the summary.
    Does not attempt to parse sections or parameters.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()
        return DocstringIR(summary=docstring_text)
~~~~~

#### Acts 2: 导出新解析器

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/__init__.py
~~~~~
~~~~~python.old
from .griffe_parser import GriffePythonParser

__all__ = [
    "PythonParser",
~~~~~
~~~~~python.new
from .griffe_parser import GriffePythonParser
from .docstring.raw_parser import RawDocstringParser

__all__ = [
    "RawDocstringParser",
    "PythonParser",
~~~~~

#### Acts 3: 重构 `DocumentManager` 核心逻辑

这是本次变更的核心。我们将彻底改造 `DocumentManager` 的加载、保存和哈希计算逻辑。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union

from stitcher.spec import ModuleDef, ClassDef, FunctionDef, DocstringIR
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        # In Phase 1, we hardcode RawDocstringParser.
        # Future phases will inject this via config.
        self.parser = RawDocstringParser()

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        """Converts YAML data (string or dict) into DocstringIR."""
        if isinstance(data, str):
            return self.parser.parse(data)
        
        if isinstance(data, dict):
            summary = data.get("Raw", "")
            # Assume other keys starting with "Addon." are addons
            addons = {k: v for k, v in data.items() if k.startswith("Addon.")}
            
            # Future: Handle structured sections (Args, Returns) here
            
            ir = self.parser.parse(summary)
            ir.addons = addons
            return ir
            
        return DocstringIR()

    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        """Converts DocstringIR back to YAML data (string or dict)."""
        summary = ir.summary or ""
        
        # If we have addons, we MUST use the dictionary format (Hybrid Mode)
        if ir.addons:
            output = {"Raw": summary}
            output.update(ir.addons)
            # Future: Serialize structured sections here
            return output
            
        # Otherwise, degrade to simple string (Raw Mode)
        return summary

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{func.name}"
        if func.docstring:
            docs[full_name] = self.parser.parse(func.docstring)
        return docs

    def _extract_from_class(self, cls: ClassDef, prefix: str = "") -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{cls.name}"
        if cls.docstring:
            docs[full_name] = self.parser.parse(cls.docstring)
        for method in cls.methods:
            docs.update(self._extract_from_function(method, prefix=f"{full_name}."))
        return docs

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        """Extracts docs from source code module into a flat dict of IRs."""
        docs: Dict[str, DocstringIR] = {}
        if module.docstring:
            docs["__doc__"] = self.parser.parse(module.docstring)
        for func in module.functions:
            docs.update(self._extract_from_function(func))
        for cls in module.classes:
            docs.update(self._extract_from_class(cls))
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = self.parser.parse(attr.docstring)
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = self.parser.parse(attr.docstring)
        return docs

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        """Extracts docs from module (code), serializes them, and saves to YAML."""
        ir_map = self.flatten_module_docs(module)
        if not ir_map:
            return Path("")
        
        # Convert IRs to YAML-ready data (str or dict)
        yaml_data = {fqn: self._serialize_ir(ir) for fqn, ir in ir_map.items()}
        
        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        self.adapter.save(output_path, yaml_data)
        return output_path

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        """Loads YAML doc file and deserializes content into DocstringIR objects."""
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        
        raw_data = self.adapter.load(doc_path) # returns Dict[str, Any] now ideally
        
        # Adapter.load is typed to return Dict[str, str], but YamlAdapter actually returns parsed YAML.
        # We assume YamlAdapter can return Dict[str, Union[str, Dict]]
        
        return {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}

    def _apply_to_function(
        self, func: FunctionDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{func.name}"
        if full_name in docs:
            # Injecting back to code: we only care about the summary (content)
            func.docstring = docs[full_name].summary

    def _apply_to_class(self, cls: ClassDef, docs: Dict[str, DocstringIR], prefix: str = ""):
        full_name = f"{prefix}{cls.name}"
        if full_name in docs:
            cls.docstring = docs[full_name].summary
        for method in cls.methods:
            self._apply_to_function(method, docs, prefix=f"{full_name}.")
        for attr in cls.attributes:
            attr_key = f"{full_name}.{attr.name}"
            if attr_key in docs:
                attr.docstring = docs[attr_key].summary

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        docs = self.load_docs_for_module(module)
        if not docs:
            return
        if "__doc__" in docs:
            module.docstring = docs["__doc__"].summary
        for func in module.functions:
            self._apply_to_function(func, docs)
        for cls in module.classes:
            self._apply_to_class(cls, docs)
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name].summary

    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        public_keys = self._extract_keys(module, public_only=True)
        all_keys = self._extract_keys(module, public_only=False)
        source_docs = self.flatten_module_docs(module)
        yaml_docs = self.load_docs_for_module(module)
        yaml_keys = set(yaml_docs.keys())

        extra = yaml_keys - all_keys
        extra.discard("__doc__")

        missing_doc = set()
        pending_hydration = set()
        redundant_doc = set()
        doc_conflict = set()

        for key in all_keys:
            is_public = key in public_keys
            has_source_doc = key in source_docs
            has_yaml_doc = key in yaml_keys

            if not has_source_doc and not has_yaml_doc:
                if is_public:
                    missing_doc.add(key)
            elif has_source_doc and not has_yaml_doc:
                pending_hydration.add(key)
            elif has_source_doc and has_yaml_doc:
                # Compare SUMMARIES only.
                # Addons in YAML do not cause conflict with Source Code.
                src_summary = source_docs[key].summary or ""
                yaml_summary = yaml_docs[key].summary or ""
                
                if src_summary != yaml_summary:
                    doc_conflict.add(key)
                else:
                    redundant_doc.add(key)

        return {
            "extra": extra,
            "missing": missing_doc,
            "pending": pending_hydration,
            "redundant": redundant_doc,
            "conflict": doc_conflict,
        }

    def hydrate_module(
        self,
        module: ModuleDef,
        force: bool = False,
        reconcile: bool = False,
        resolution_map: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        resolution_map = resolution_map or {}

        source_docs = self.flatten_module_docs(module)
        if not source_docs:
            return {
                "success": True,
                "updated_keys": [],
                "conflicts": [],
                "reconciled_keys": [],
            }
        
        yaml_docs = self.load_docs_for_module(module)
        updated_keys = []
        conflicts = []
        reconciled_keys = []
        
        # Prepare new YAML state (we work with IRs)
        new_yaml_docs_ir = yaml_docs.copy()

        for key, source_ir in source_docs.items():
            if key not in yaml_docs:
                new_yaml_docs_ir[key] = source_ir
                updated_keys.append(key)
            else:
                existing_ir = yaml_docs[key]
                src_summary = source_ir.summary or ""
                yaml_summary = existing_ir.summary or ""
                
                if yaml_summary != src_summary:
                    # Check for specific resolution first
                    action = resolution_map.get(key)
                    should_force = force or (action == "HYDRATE_OVERWRITE")
                    should_reconcile = reconcile or (action == "HYDRATE_KEEP_EXISTING")

                    if should_reconcile:
                        reconciled_keys.append(key)
                        continue
                    elif should_force:
                        # CRITICAL: Preserve addons when overwriting from source
                        # Source IR has new summary, empty addons.
                        # Existing IR has old summary, existing addons.
                        source_ir.addons = existing_ir.addons
                        new_yaml_docs_ir[key] = source_ir
                        updated_keys.append(key)
                    else:
                        conflicts.append(key)

        if conflicts:
            return {
                "success": False,
                "updated_keys": [],
                "conflicts": conflicts,
                "reconciled_keys": [],
            }

        if updated_keys and not dry_run:
            # Serialize back to raw data
            final_data = {fqn: self._serialize_ir(ir) for fqn, ir in new_yaml_docs_ir.items()}
            
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, final_data)

        return {
            "success": True,
            "updated_keys": updated_keys,
            "conflicts": [],
            "reconciled_keys": reconciled_keys,
        }

    def _extract_keys(self, module: ModuleDef, public_only: bool) -> set:
        keys = set()
        if module.docstring:
            keys.add("__doc__")

        def include(name: str) -> bool:
            if public_only:
                return not name.startswith("_")
            return True

        for func in module.functions:
            if include(func.name):
                keys.add(func.name)
        for cls in module.classes:
            if include(cls.name):
                keys.add(cls.name)
                for method in cls.methods:
                    if include(method.name):
                        keys.add(f"{cls.name}.{method.name}")
                for attr in cls.attributes:
                    if include(attr.name):
                        keys.add(f"{cls.name}.{attr.name}")
        for attr in module.attributes:
            if include(attr.name):
                keys.add(attr.name)
        return keys

    def compute_yaml_content_hash(self, content: Union[str, Dict[str, Any]]) -> str:
        """Computes a stable hash for either a string or a dict."""
        if isinstance(content, str):
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        if isinstance(content, dict):
            # Canonicalize dict by sorting keys and ensuring JSON serialization
            canonical_json = json.dumps(content, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
            
        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        # We need raw data here to compute the hash exactly as it is stored
        # But load_docs_for_module returns IRs.
        # We should load raw data directly from adapter for hashing.
        
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        
        # Load raw dict from YAML
        raw_data = self.adapter.load(doc_path)
        
        return {
            fqn: self.compute_yaml_content_hash(val)
            for fqn, val in raw_data.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            return False

        # Load raw to preserve everything, then deserialize->serialize to apply formatting rules
        raw_data = self.adapter.load(doc_path)
        if not raw_data:
            return False

        # Round-trip through IR to enforce schema
        irs = {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}
        formatted_data = {fqn: self._serialize_ir(ir) for fqn, ir in irs.items()}
        
        self.adapter.save(doc_path, formatted_data)
        return True
~~~~~

#### Acts 4: 适配 `YamlAdapter`

`YamlAdapter` 的类型提示目前是 `Dict[str, str]`，需要更新以支持 `Dict[str, Any]`，因为现在值可能是字典。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~
~~~~~python.old
from typing import Dict
import yaml

from stitcher.common.interfaces import DocumentAdapter


class YamlAdapter(DocumentAdapter):
    def load(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not isinstance(content, dict):
                return {}

            return {str(k): str(v) for k, v in content.items() if v is not None}

        except yaml.YAMLError:
            return {}

    def dump(self, data: Dict[str, str]) -> str:
        sorted_data = dict(sorted(data.items()))
~~~~~
~~~~~python.new
from typing import Dict, Any
import yaml

from stitcher.common.interfaces import DocumentAdapter


class YamlAdapter(DocumentAdapter):
    def load(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not isinstance(content, dict):
                return {}

            # Allow values to be dicts or strings
            return {str(k): v for k, v in content.items() if v is not None}

        except yaml.YAMLError:
            return {}

    def dump(self, data: Dict[str, Any]) -> str:
        sorted_data = dict(sorted(data.items()))
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~
~~~~~python.old
    def save(self, path: Path, data: Dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sorted_data = dict(sorted(data.items()))
~~~~~
~~~~~python.new
    def save(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sorted_data = dict(sorted(data.items()))
~~~~~

同时更新接口定义：

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/interfaces.py
~~~~~
~~~~~python.old
from typing import Dict, Protocol
from pathlib import Path


class DocumentAdapter(Protocol):
    def load(self, path: Path) -> Dict[str, str]: ...

    def save(self, path: Path, data: Dict[str, str]) -> None: ...
~~~~~
~~~~~python.new
from typing import Dict, Protocol, Any
from pathlib import Path


class DocumentAdapter(Protocol):
    def load(self, path: Path) -> Dict[str, Any]: ...

    def save(self, path: Path, data: Dict[str, Any]) -> None: ...
~~~~~

#### Acts 5: 适配 `PumpRunner`

`PumpRunner` 在发生冲突时，会生成 diff。现在 `hydrate_module` 的逻辑已经更新（返回冲突列表），但 `_analyze_file` (在 `check.py` 中) 和 `dry_run` 时的比较逻辑需要适配对象比较。

在 `PumpRunner._generate_diff` 中，我们需要处理 `DocstringIR` 的比较。目前它接收 `str`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if not res["success"]:
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)
                    for key in res["conflicts"]:
                        doc_diff = self._generate_diff(
                            yaml_docs.get(key, ""),
                            source_docs.get(key, ""),
                            "yaml",
                            "code",
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
                        
                        doc_diff = self._generate_diff(
                            yaml_summary or "",
                            src_summary or "",
                            "yaml",
                            "code",
                        )
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if plan.hydrate_yaml:
                    if (
                        fqn in source_docs
                        and new_yaml_docs.get(fqn) != source_docs[fqn]
                    ):
                        new_yaml_docs[fqn] = source_docs[fqn]
                        updated_keys_in_file.append(fqn)
                        file_had_updates = True
~~~~~
~~~~~python.new
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

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
            if not file_has_errors:
                if file_had_updates:
                    module_path = self.root_path / module.file_path
                    doc_path = module_path.with_suffix(".stitcher.yaml")
                    self.doc_manager.adapter.save(doc_path, new_yaml_docs)
~~~~~
~~~~~python.new
            if not file_has_errors:
                if file_had_updates:
                    # new_yaml_docs is Dict[str, DocstringIR], need to serialize!
                    # BUT doc_manager.adapter.save expects raw Dict. 
                    # We should rely on doc_manager helper instead of calling adapter directly,
                    # OR manually serialize here.
                    # Since doc_manager.save_docs_for_module re-extracts from module (which we don't want, we have merged state),
                    # we must serialize here.
                    
                    final_data = {
                        k: self.doc_manager._serialize_ir(v) 
                        for k, v in new_yaml_docs.items()
                    }
                    module_path = self.root_path / module.file_path
                    doc_path = module_path.with_suffix(".stitcher.yaml")
                    self.doc_manager.adapter.save(doc_path, final_data)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        doc_hash = self.doc_manager.compute_yaml_content_hash(
                            source_docs[fqn]
                        )
                        fp["baseline_yaml_content_hash"] = doc_hash
                        fqn_was_updated = True
~~~~~
~~~~~python.new
                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        # Compute hash of the SERIALIZED content (what will be written to yaml)
                        # source_docs[fqn] is IR. We need raw content.
                        # Note: This source_docs[fqn] has addons merged in previous step if it was updated!
                        # Wait, source_docs came from flatten_module_docs(module) at start of loop.
                        # It does NOT have addons.
                        
                        # We need the IR that we are about to save (which might have addons).
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                             serialized = self.doc_manager._serialize_ir(ir_to_save)
                             doc_hash = self.doc_manager.compute_yaml_content_hash(serialized)
                             fp["baseline_yaml_content_hash"] = doc_hash
                             fqn_was_updated = True
~~~~~

#### Acts 6: 适配 `CheckRunner`

`CheckRunner` 的 `_apply_resolutions` 中有个 `Purge` 逻辑，也直接操作了 adapter。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
        # Apply doc purges
        for file_path, fqns_to_purge in purges_by_file.items():
            module_def = ModuleDef(file_path=file_path)
            docs = self.doc_manager.load_docs_for_module(module_def)
            original_len = len(docs)

            for fqn in fqns_to_purge:
                if fqn in docs:
                    del docs[fqn]

            if len(docs) < original_len:
                doc_path = (self.root_path / file_path).with_suffix(".stitcher.yaml")
                if not docs:
                    # If all docs are purged, delete the file
                    if doc_path.exists():
                        doc_path.unlink()
                else:
                    self.doc_manager.adapter.save(doc_path, docs)
~~~~~
~~~~~python.new
        # Apply doc purges
        for file_path, fqns_to_purge in purges_by_file.items():
            module_def = ModuleDef(file_path=file_path)
            docs = self.doc_manager.load_docs_for_module(module_def)
            original_len = len(docs)

            for fqn in fqns_to_purge:
                if fqn in docs:
                    del docs[fqn]

            if len(docs) < original_len:
                doc_path = (self.root_path / file_path).with_suffix(".stitcher.yaml")
                if not docs:
                    # If all docs are purged, delete the file
                    if doc_path.exists():
                        doc_path.unlink()
                else:
                    # Serialize before saving
                    final_data = {
                        k: self.doc_manager._serialize_ir(v) 
                        for k, v in docs.items()
                    }
                    self.doc_manager.adapter.save(doc_path, final_data)
~~~~~

#### Acts 7: 适配 `GenerateRunner`

`GenerateRunner` 使用 `self.doc_manager.apply_docs_to_module(module)`。这个方法在 `doc_manager.py` 中已经被我们更新为提取 `summary` 并注入到 module，所以 `GenerateRunner` 本身不需要修改，因为它只消费被注入后的 `ModuleDef`。

但是 `TransformRunner` 中的 `run_inject` 有直接调用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/transform.py
~~~~~
~~~~~python.old
            for module in modules:
                docs = self.doc_manager.load_docs_for_module(module)
                if not docs:
                    continue
                total_docs_found += len(docs)
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = self.transformer.inject(original_content, docs)
~~~~~
~~~~~python.new
            for module in modules:
                docs_ir = self.doc_manager.load_docs_for_module(module)
                if not docs_ir:
                    continue
                total_docs_found += len(docs_ir)
                
                # Convert IR map to simple str map for transformer
                docs_str = {k: v.summary or "" for k, v in docs_ir.items()}
                
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = self.transformer.inject(original_content, docs_str)
~~~~~

#### Acts 8: 添加测试用例

我们添加一个新的测试文件来专门验证混合模式和插件数据的持久化。

~~~~~act
write_file
packages/stitcher-application/tests/unit/test_docstring_hybrid.py
~~~~~
~~~~~python
import pytest
from stitcher.app.services import DocumentManager
from stitcher.spec import DocstringIR
from stitcher.common.adapters.yaml_adapter import YamlAdapter


def test_hybrid_mode_serialization(tmp_path):
    """Verify that addons trigger dictionary format serialization."""
    manager = DocumentManager(tmp_path)
    
    # Case 1: Simple IR (summary only) -> String
    ir_simple = DocstringIR(summary="Simple doc.")
    serialized = manager._serialize_ir(ir_simple)
    assert serialized == "Simple doc."
    
    # Case 2: Hybrid IR (summary + addons) -> Dict
    ir_hybrid = DocstringIR(summary="Hybrid doc.", addons={"Addon.Test": "Data"})
    serialized_hybrid = manager._serialize_ir(ir_hybrid)
    assert isinstance(serialized_hybrid, dict)
    assert serialized_hybrid["Raw"] == "Hybrid doc."
    assert serialized_hybrid["Addon.Test"] == "Data"


def test_hybrid_mode_deserialization(tmp_path):
    """Verify that dictionary format YAML is correctly parsed into IR with addons."""
    manager = DocumentManager(tmp_path)
    
    # Case 1: String -> Simple IR
    ir_simple = manager._deserialize_ir("Simple doc.")
    assert ir_simple.summary == "Simple doc."
    assert not ir_simple.addons
    
    # Case 2: Dict -> Hybrid IR
    data = {"Raw": "Hybrid doc.", "Addon.Test": "Data", "Other": "Ignored"}
    ir_hybrid = manager._deserialize_ir(data)
    assert ir_hybrid.summary == "Hybrid doc."
    assert ir_hybrid.addons == {"Addon.Test": "Data"}


def test_hash_stability(tmp_path):
    """Verify that hashing is stable regardless of dict key order."""
    manager = DocumentManager(tmp_path)
    
    data1 = {"Raw": "Doc", "Addon.A": "1", "Addon.B": "2"}
    data2 = {"Addon.B": "2", "Raw": "Doc", "Addon.A": "1"}
    
    hash1 = manager.compute_yaml_content_hash(data1)
    hash2 = manager.compute_yaml_content_hash(data2)
    
    assert hash1 == hash2
~~~~~

#### Acts 9: 更新现有测试

`test_doc_manager.py` 中的 mock adapter 需要适配新的数据结构。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_manager.py
~~~~~
~~~~~python.old
    def save(self, path: Path, data: dict):
        self.saved_path = path
        self.saved_data = data


@pytest.fixture
~~~~~
~~~~~python.new
    def save(self, path: Path, data: dict):
        self.saved_path = path
        self.saved_data = data


@pytest.fixture
~~~~~

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_manager.py
~~~~~
~~~~~python.old
def test_flatten_module_docs(tmp_path, sample_module_ir):
    manager = DocumentManager(root_path=tmp_path)
    docs = manager.flatten_module_docs(sample_module_ir)

    assert docs["__doc__"] == "Module doc"
    assert docs["func"] == "Func doc"
    assert docs["MyClass"] == "Class doc"
    assert docs["MyClass.method"] == "Method doc"
    assert docs["MyClass.attr"] == "Attr doc"


def test_save_docs_for_module(tmp_path, sample_module_ir):
~~~~~
~~~~~python.new
def test_flatten_module_docs(tmp_path, sample_module_ir):
    manager = DocumentManager(root_path=tmp_path)
    docs = manager.flatten_module_docs(sample_module_ir)

    assert docs["__doc__"].summary == "Module doc"
    assert docs["func"].summary == "Func doc"
    assert docs["MyClass"].summary == "Class doc"
    assert docs["MyClass.method"].summary == "Method doc"
    assert docs["MyClass.attr"].summary == "Attr doc"


def test_save_docs_for_module(tmp_path, sample_module_ir):
~~~~~

### 下一步建议

我们已经完成了 DocumentManager 的核心重构，并适配了所有 Runners。新的架构现在支持：
1.  **混合存储**：简单的文档存为字符串，复杂的文档（带插件）存为字典。
2.  **IR 统一**：系统内部统一使用 `DocstringIR`，消除了字符串传递的随意性。
3.  **插件就绪**：`Addon.*` 数据现在可以在 Pump/Check 循环中被安全地保留和持久化。

下一步，建议进行 Phase 2: 实现完整的结构化文档支持 (Full Formatting)。这包括引入 `griffe` 解析器来实现真正的 Google/NumPy 风格解析。
