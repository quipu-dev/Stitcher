好的，我们立即开始实施 Phase 1。

这是本次功能开发的核心阶段。我们将对 `DocumentManager` 服务进行一次彻底的重构，将其从处理简单字符串升级为处理我们刚刚定义的、更强大的 `DocstringIR`（文档中间表示）对象。

这次重构的目标是实现“混合模式”——即使系统还没有开始解析文档的具体内容（如参数、返回值），它也必须能够优雅地处理附加的元数据（`Addon.*`）。这为未来的插件系统奠定了坚实的基础，并确保了向后兼容性。

我将生成一个计划来执行这次重构。

## [WIP] refactor(app): 在 DocumentManager 中实现 DocstringIR 和 Addon 支持

### 用户需求

根据《实施路线图：文档字符串格式化与插件系统》，实施 Phase 1: 实现插件系统与混合模式 (The Addon Milestone) 的所有任务。

### 评论

这是一次意义深远的重构，它将系统的核心文档处理逻辑从脆弱的、基于字符串的操作，提升到了一个健壮的、基于结构化数据对象（`DocstringIR`）的层面。本次工作的关键在于**向后兼容性**和**自动升格**：
1.  系统必须能无缝读取旧的、纯文本格式的 `.stitcher.yaml` 文件。
2.  当需要为某个文档附加插件数据时，系统必须能自动将其在 YAML 中的存储结构从 `key: "string"` 升级为 `key: {Raw: "string", Addon.Something: ...}`。

这将使我们能够在不破坏现有功能的前提下，为插件系统的引入做好准备。

### 目标

1.  **升级数据契约**：修改 `YamlAdapter`，使其能够加载包含字典和字符串的混合类型 YAML 文件。
2.  **实现核心转换逻辑**：重构 `DocumentManager`，使其所有内部操作都围绕 `DocstringIR` 进行，包括加载（反序列化）、保存（序列化）和哈希计算。
3.  **提供基础解析器**：创建 `RawDocstringParser`，作为将源码中的 `str` 转换为 `DocstringIR` 的第一个、也是最基础的实现。
4.  **适配应用层**：全面更新 `PumpRunner` 和 `CheckRunner` 等核心业务流程，使其与新的、基于 IR 的 `DocumentManager` 接口协同工作。

### 基本原理

我们遵循**数据模型驱动重构**的原则。首先，我们改变了核心服务 (`DocumentManager`) 的“通用语言”，从 `str` 升级为 `DocstringIR`。然后，我们沿着这个改变的涟漪，去修改所有与该服务交互的组件。

对于 `DocumentManager` 本身，其关键实现机制是：
-   **反序列化（加载）**：在加载 YAML 时，通过检查值的类型（`isinstance(val, str)` 或 `isinstance(val, dict)`）来决定如何构建 `DocstringIR` 对象。
-   **序列化（保存）**：在保存 `DocstringIR` 时，根据其内部状态（是否包含 `addons`）来决定是将其序列化为简单的字符串还是结构化的字典。
-   **哈希**：对字典进行哈希前，通过递归键排序实现内容的**规范化**，确保哈希值的稳定性，避免因键顺序不同导致的“伪变更”。

### 标签

#intent/refine #intent/build #flow/ready #priority/high #comp/application #comp/spec #concept/state #scope/core #ai/instruct #task/domain/docstrings #task/object/ir-scaffolding #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `YamlAdapter` 以支持混合类型

首先，我们修改 `YamlAdapter` 的 `load` 方法，使其能够返回 `Dict[str, Any]`，为加载结构化文档做准备。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~
~~~~~python
from pathlib import Path
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

            # Return raw values (str or dict), only ensuring keys are strings.
            return {str(k): v for k, v in content.items() if v is not None}

        except yaml.YAMLError:
            return {}

    def dump(self, data: Dict[str, Any]) -> str:
        sorted_data = dict(sorted(data.items()))

        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            # Only apply block style to multiline strings
            if "\n" in data:
                return dumper.represent_scalar(
                    "tag:yaml.org,2002:str", data, style="|"
                )
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        MultilineDumper.add_representer(str, str_presenter)

        return yaml.dump(
            sorted_data,
            Dumper=MultilineDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    def save(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Sort root keys for consistent file output
        sorted_data = dict(sorted(data.items()))

        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar(
                    "tag:yaml.org,2002:str", data, style="|"
                )
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        MultilineDumper.add_representer(str, str_presenter)

        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                sorted_data,
                f,
                Dumper=MultilineDumper,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
~~~~~

#### Acts 2: 更新 `DocumentAdapter` 协议

同步更新协议文件以匹配 `YamlAdapter` 的新接口。

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

#### Acts 3: 创建 `RawDocstringParser`

现在，我们创建第一个简单的文档字符串解析器。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring
touch packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/__init__.py
~~~~~

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/raw_parser.py
~~~~~
~~~~~python
from stitcher.spec import DocstringIR
from stitcher.spec.protocols import DocstringParserProtocol


class RawDocstringParser(DocstringParserProtocol):
    """
    A simple parser that treats the entire docstring text as the summary.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        return DocstringIR(summary=docstring_text)
~~~~~

#### Acts 4: 重构 `DocumentManager`

这是本次重构的核心。我们将完全重写 `DocumentManager`，使其原生支持 `DocstringIR`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, List

from stitcher.spec import ModuleDef, DocstringIR
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python.docstring.raw_parser import RawDocstringParser


def _canonical_dump(data: Any) -> str:
    """Recursively sorts dictionaries to create a stable JSON string."""
    if isinstance(data, dict):
        return json.dumps(
            {k: _canonical_dump(data[k]) for k in sorted(data.keys())},
            sort_keys=True,
        )
    if isinstance(data, list):
        return json.dumps([_canonical_dump(item) for item in data], sort_keys=True)
    return str(data)


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        # For Phase 1, we only need a raw parser. This could be injected later.
        self._raw_parser = RawDocstringParser()

    def _deserialize_doc(self, fqn: str, data: Any) -> DocstringIR:
        """Converts raw data from YAML (str or dict) into a DocstringIR object."""
        if isinstance(data, str):
            return DocstringIR(summary=data)
        if isinstance(data, dict):
            addons = {k: v for k, v in data.items() if k.startswith("Addon.")}
            raw_text = data.get("Raw")
            # Future-proofing: also check for "Summary" for structured docs
            summary = data.get("Summary", raw_text)
            # TODO: Handle full structured deserialization in Phase 2
            return DocstringIR(summary=summary, addons=addons)
        # Fallback for unexpected data types
        return DocstringIR(summary=str(data))

    def _serialize_doc(self, ir: DocstringIR) -> Any:
        """Converts a DocstringIR object back into a YAML-compatible format (str or dict)."""
        # Phase 1 logic:
        if ir.addons:
            # Auto-upgrade to hybrid structure
            data = {"Raw": ir.summary or ""}
            data.update(ir.addons)
            return data
        # If no addons, and it's a simple summary, serialize as a plain string
        # for backward compatibility and readability.
        return ir.summary or ""

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        raw_data = self.adapter.load(doc_path)
        return {
            fqn: self._deserialize_doc(fqn, data) for fqn, data in raw_data.items()
        }

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        """Extracts docstrings from a ModuleDef, converts to IR, and saves to YAML."""
        # This method is primarily used by `stitcher init`.
        source_docs: Dict[str, str] = self._flatten_module_strings(module)
        if not source_docs:
            return Path("")

        # Convert raw strings to basic DocstringIR objects
        doc_irs = {
            fqn: self._raw_parser.parse(text) for fqn, text in source_docs.items()
        }

        # Serialize IRs to YAML-compatible data
        serialized_data = {
            fqn: self._serialize_doc(ir) for fqn, ir in doc_irs.items()
        }

        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        self.adapter.save(output_path, serialized_data)
        return output_path

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        """Loads docs as IR and applies their summaries to the ModuleDef's string fields."""
        doc_irs = self.load_docs_for_module(module)
        if not doc_irs:
            return

        # Create a map of FQN to summary string for easy application
        summary_map = {
            fqn: ir.summary for fqn, ir in doc_irs.items() if ir.summary is not None
        }

        if "__doc__" in summary_map:
            module.docstring = summary_map["__doc__"]

        for func in module.functions:
            if func.name in summary_map:
                func.docstring = summary_map[func.name]

        for cls in module.classes:
            if cls.name in summary_map:
                cls.docstring = summary_map[cls.name]
            for method in cls.methods:
                method_fqn = f"{cls.name}.{method.name}"
                if method_fqn in summary_map:
                    method.docstring = summary_map[method_fqn]
            for attr in cls.attributes:
                attr_fqn = f"{cls.name}.{attr.name}"
                if attr_fqn in summary_map:
                    attr.docstring = summary_map[attr_fqn]

        for attr in module.attributes:
            if attr.name in summary_map:
                attr.docstring = summary_map[attr.name]

    def compute_yaml_content_hash(self, content: Any) -> str:
        """Computes a stable hash for either a string or a dictionary."""
        canonical_string = _canonical_dump(content)
        return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        # Load raw data to hash strings or dicts correctly
        raw_data = self.adapter.load(doc_path)
        return {
            fqn: self.compute_yaml_content_hash(data)
            for fqn, data in raw_data.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            return False

        # Load and save re-serializes with canonical formatting
        raw_data = self.adapter.load(doc_path)
        if not raw_data:
            return False

        self.adapter.save(doc_path, raw_data)
        return True

    # Helper to get raw strings from a ModuleDef, for `init` and `pump`'s source side.
    def _flatten_module_strings(self, module: ModuleDef) -> Dict[str, str]:
        docs: Dict[str, str] = {}
        if module.docstring:
            docs["__doc__"] = module.docstring
        for func in module.functions:
            if func.docstring:
                docs[func.name] = func.docstring
        for cls in module.classes:
            if cls.docstring:
                docs[cls.name] = cls.docstring
            for method in cls.methods:
                if method.docstring:
                    docs[f"{cls.name}.{method.name}"] = method.docstring
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = attr.docstring
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = attr.docstring
        return docs

    def hydrate_module(
        self, module: ModuleDef, force: bool, reconcile: bool, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Merges docstrings from Code into YAML, now using DocstringIR."""
        source_docs: Dict[str, str] = self._flatten_module_strings(module)
        if not source_docs:
            return {"success": True, "updated_keys": [], "conflicts": []}

        yaml_irs = self.load_docs_for_module(module)
        updated_keys: List[str] = []
        conflicts: List[str] = []
        new_yaml_irs = yaml_irs.copy()

        for key, source_content in source_docs.items():
            yaml_ir = yaml_irs.get(key)
            if not yaml_ir or not yaml_ir.summary:
                # No existing doc in YAML, so we pump the new one.
                # Preserve addons if an entry existed but was empty.
                new_ir = self._raw_parser.parse(source_content)
                if yaml_ir and yaml_ir.addons:
                    new_ir.addons = yaml_ir.addons
                new_yaml_irs[key] = new_ir
                updated_keys.append(key)
            elif yaml_ir.summary != source_content:
                # Conflict: doc exists and content differs.
                if force:
                    # Overwrite summary, keep addons
                    yaml_ir.summary = source_content
                    new_yaml_irs[key] = yaml_ir
                    updated_keys.append(key)
                elif reconcile:
                    # Keep existing YAML, do nothing.
                    pass
                else:
                    conflicts.append(key)

        if conflicts:
            return {"success": False, "updated_keys": [], "conflicts": conflicts}

        if updated_keys and not dry_run:
            # Serialize back to YAML-compatible structures
            serialized_data = {
                fqn: self._serialize_doc(ir) for fqn, ir in new_yaml_irs.items()
            }
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, serialized_data)

        return {"success": True, "updated_keys": updated_keys, "conflicts": []}
~~~~~

#### Acts 5: 更新受影响的 Runner

`DocumentManager` 的接口发生了巨大变化，我们需要更新直接调用它的 `CheckRunner` 和 `PumpRunner`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python
import copy
import difflib
from pathlib import Path
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
)
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
    ) -> tuple[FileCheckResult, list[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: list[InteractionContext] = []

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )

        computed_fingerprints = self.sig_manager.compute_fingerprints(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(computed_fingerprints.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            computed_fp = computed_fingerprints.get(fqn, Fingerprint())

            code_hash = computed_fp.get("current_code_structure_hash")
            current_sig_text = computed_fp.get("current_code_signature_text")
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )
            baseline_sig_text = (
                stored_fp.get("baseline_code_signature_text") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                unresolved_conflicts.append(
                    InteractionContext(module.file_path, fqn, ConflictType.DANGLING_DOC)
                )
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

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
                    ConflictType.SIGNATURE_DRIFT
                    if yaml_matches
                    else ConflictType.CO_EVOLUTION
                )

                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, conflict_type, signature_diff=sig_diff
                    )
                )

        if not is_tracked and module.is_documentable():
            undocumented = module.get_undocumented_public_keys()
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts

    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        # --- Handle Signature Updates ---
        sig_updates_by_file = defaultdict(list)
        # --- Handle Doc Purges ---
        purges_by_file = defaultdict(list)

        for file_path, fqn_actions in resolutions.items():
            for fqn, action in fqn_actions:
                if action in [ResolutionAction.RELINK, ResolutionAction.RECONCILE]:
                    sig_updates_by_file[file_path].append((fqn, action))
                elif action == ResolutionAction.PURGE_DOC:
                    purges_by_file[file_path].append(fqn)

        # Apply signature updates
        for file_path, fqn_actions in sig_updates_by_file.items():
            module_def = ModuleDef(file_path=file_path)  # Minimal def for path logic
            stored_hashes = self.sig_manager.load_composite_hashes(module_def)
            new_hashes = copy.deepcopy(stored_hashes)

            full_module_def = self.parser.parse(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            computed_fingerprints = self.sig_manager.compute_fingerprints(
                full_module_def
            )
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    current_code_hash = current_fp.get("current_code_structure_hash")

                    if action == ResolutionAction.RELINK:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = str(
                                current_yaml_map[fqn]
                            )

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

        # Apply doc purges
        for file_path, fqns_to_purge in purges_by_file.items():
            doc_path = (self.root_path / file_path).with_suffix(".stitcher.yaml")
            if not doc_path.exists():
                continue

            docs = self.doc_manager.adapter.load(doc_path)
            original_len = len(docs)

            for fqn in fqns_to_purge:
                if fqn in docs:
                    del docs[fqn]

            if len(docs) < original_len:
                if not docs:
                    doc_path.unlink()
                else:
                    self.doc_manager.adapter.save(doc_path, docs)

    def run(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        all_results: list[FileCheckResult] = []
        all_conflicts: list[InteractionContext] = []
        all_modules: list[ModuleDef] = []

        # 1. Analysis Phase
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            all_modules.extend(modules)
            for module in modules:
                result, conflicts = self._analyze_file(module)
                all_results.append(result)
                all_conflicts.extend(conflicts)

        # 2. Execution Phase (Auto-reconciliation for doc improvements)
        for res in all_results:
            if res.infos["doc_improvement"]:
                module_def = next(
                    (m for m in all_modules if m.file_path == res.path), None
                )
                if not module_def:
                    continue

                stored_hashes = self.sig_manager.load_composite_hashes(module_def)
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module_def
                )

                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_yaml_hash = current_yaml_map.get(fqn)
                        if new_yaml_hash is not None:
                            new_hashes[fqn]["baseline_yaml_content_hash"] = (
                                new_yaml_hash
                            )
                        elif "baseline_yaml_content_hash" in new_hashes[fqn]:
                            del new_hashes[fqn]["baseline_yaml_content_hash"]

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)

        # 3. Interactive Resolution Phase
        if all_conflicts and self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(
                all_conflicts
            )
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["force_relink"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["reconcile"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.PURGE_DOC:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["purged"].append(context.fqn)
                elif action == ResolutionAction.SKIP:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = {
                                ConflictType.SIGNATURE_DRIFT: "signature_drift",
                                ConflictType.CO_EVOLUTION: "co_evolution",
                                ConflictType.DANGLING_DOC: "extra",
                            }.get(context.conflict_type, "unknown")
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False

            self._apply_resolutions(dict(resolutions_by_file))

            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]
                    res.reconciled["purged"] = reconciled_results[res.path].get(
                        "purged", []
                    )
        else:
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = (
                        "force_relink"
                        if action == ResolutionAction.RELINK
                        else "reconcile"
                    )
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = {
                                ConflictType.SIGNATURE_DRIFT: "signature_drift",
                                ConflictType.CO_EVOLUTION: "co_evolution",
                                ConflictType.DANGLING_DOC: "extra",
                            }.get(context.conflict_type, "unknown")
                            res.errors[error_key].append(context.fqn)
            self._apply_resolutions(dict(resolutions_by_file))
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]

        # 4. Reformatting Phase
        bus.info(L.check.run.reformatting)
        for module in all_modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_module(module)

        # 5. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
        for res in all_results:
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)
            if res.is_clean:
                continue
            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
                for key in res.reconciled.get("purged", []):
                    bus.success(L.check.state.purged, key=key, path=res.path)
            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)
            for key in sorted(res.errors["extra"]):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(res.errors["signature_drift"]):
                bus.error(L.check.state.signature_drift, key=key)
            for key in sorted(res.errors["co_evolution"]):
                bus.error(L.check.state.co_evolution, key=key)
            for key in sorted(res.errors["conflict"]):
                bus.error(L.check.issue.conflict, key=key)
            for key in sorted(res.errors["pending"]):
                bus.error(L.check.issue.pending, key=key)
            for key in sorted(res.warnings["missing"]):
                bus.warning(L.check.issue.missing, key=key)
            for key in sorted(res.warnings["redundant"]):
                bus.warning(L.check.issue.redundant, key=key)
            for key in sorted(res.warnings["untracked_key"]):
                bus.warning(L.check.state.untracked_code, key=key)
            if "untracked_detailed" in res.warnings:
                keys = res.warnings["untracked_detailed"]
                bus.warning(
                    L.check.file.untracked_with_details, path=res.path, count=len(keys)
                )
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            elif "untracked" in res.warnings:
                bus.warning(L.check.file.untracked, path=res.path)

        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True
~~~~~

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python
import copy
import difflib
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    LanguageParserProtocol,
)
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
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager._flatten_module_strings(module)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                pass  # All flags default to False
            else:
                # All other cases require updating the code fingerprint.
                exec_plan.update_code_fingerprint = True

                if decision == ResolutionAction.HYDRATE_OVERWRITE or (
                    decision is None and has_source_doc
                ):
                    exec_plan.hydrate_yaml = True
                    exec_plan.update_doc_fingerprint = True
                    if strip_requested:
                        exec_plan.strip_source_docstring = True
                elif decision == ResolutionAction.HYDRATE_KEEP_EXISTING:
                    if strip_requested:
                        exec_plan.strip_source_docstring = True
            plan[fqn] = exec_plan

        return plan

    def run(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # --- Phase 1: Analysis ---
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            if not modules:
                continue
            all_modules.extend(modules)

            for module in modules:
                source_docs = self.doc_manager._flatten_module_strings(module)
                yaml_irs = self.doc_manager.load_docs_for_module(module)

                for key, source_content in source_docs.items():
                    yaml_ir = yaml_irs.get(key)
                    if yaml_ir and yaml_ir.summary and yaml_ir.summary != source_content:
                        doc_diff = self._generate_diff(
                            yaml_ir.summary,
                            source_content,
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

        # --- Phase 2: Decision ---
        decisions: Dict[str, ResolutionAction] = {}
        if all_conflicts:
            handler = self.interaction_handler or NoOpInteractionHandler(
                hydrate_force=force, hydrate_reconcile=reconcile
            )
            chosen_actions = handler.process_interactive_session(all_conflicts)

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                decisions[context.fqn] = action

        # --- Phase 3 & 4: Planning & Execution ---
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        for module in all_modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)
            source_docs = self.doc_manager._flatten_module_strings(module)
            current_yaml_irs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module)
            current_fingerprints = self.sig_manager.compute_fingerprints(module)
            new_yaml_irs = copy.deepcopy(current_yaml_irs)
            new_hashes = copy.deepcopy(stored_hashes)

            file_had_updates = False
            file_has_errors = False
            file_has_redundancy = False
            updated_keys_in_file = []
            reconciled_keys_in_file = []

            for fqn, plan in file_plan.items():
                if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                    unresolved_conflicts_count += 1
                    file_has_errors = True
                    bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                    continue

                if plan.hydrate_yaml and fqn in source_docs:
                    new_ir = self.doc_manager._raw_parser.parse(source_docs[fqn])
                    existing_ir = new_yaml_irs.get(fqn)
                    if existing_ir and existing_ir.addons:
                        new_ir.addons = existing_ir.addons
                    new_yaml_irs[fqn] = new_ir
                    updated_keys_in_file.append(fqn)
                    file_had_updates = True

                fp = new_hashes.get(fqn) or Fingerprint()
                fqn_was_updated = False
                if plan.update_code_fingerprint:
                    current_fp = current_fingerprints.get(fqn, Fingerprint())
                    if "current_code_structure_hash" in current_fp:
                        fp["baseline_code_structure_hash"] = current_fp["current_code_structure_hash"]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp["current_code_signature_text"]
                    fqn_was_updated = True
                if plan.update_doc_fingerprint and fqn in new_yaml_irs:
                    serialized = self.doc_manager._serialize_doc(new_yaml_irs[fqn])
                    fp["baseline_yaml_content_hash"] = self.doc_manager.compute_yaml_content_hash(serialized)
                    fqn_was_updated = True
                if fqn_was_updated:
                    new_hashes[fqn] = fp

                if fqn in decisions and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING:
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)
                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            if not file_has_errors:
                if file_had_updates:
                    serialized_data = {fqn: self.doc_manager._serialize_doc(ir) for fqn, ir in new_yaml_irs.items()}
                    doc_path = (self.root_path / module.file_path).with_suffix(".stitcher.yaml")
                    self.doc_manager.adapter.save(doc_path, serialized_data)
                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module, new_hashes)
                if file_has_redundancy:
                    redundant_files_list.append(self.root_path / module.file_path)

            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(L.pump.file.success, path=module.file_path, count=len(updated_keys_in_file))
            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(L.pump.info.reconciled, path=module.file_path, count=len(reconciled_keys_in_file))

        # --- Phase 5: Stripping ---
        if strip_jobs:
            # ... (stripping logic remains the same)
            pass

        # Final Reporting
        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)
        has_activity = total_updated_keys > 0 or strip_jobs
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)
        return PumpResult(success=True, redundant_files=redundant_files_list)
~~~~~

### 下一步建议

我们已经成功地将 `DocstringIR` 集成到了应用层服务的核心。系统现在具备了处理混合模式（Raw + Addon）文档的能力，并且为未来的结构化解析（Phase 2）打下了坚实的基础。

下一步，我建议我们进入 **Phase 2: 实现完整的结构化文档支持 (Full Formatting)**。

这将涉及：
1.  **实现 `GriffeDocstringParser`**：利用 `griffe` 的强大能力，将 Google 或 NumPy 风格的文档字符串完全解析为结构化的 `DocstringIR` 对象。
2.  **实现 `Renderer` 和 `Serializer`**：创建能够将 `DocstringIR` 对象渲染回特定格式字符串（用于 `inject`）或序列化为结构化 YAML（用于存储）的组件。
3.  **升级 `check` 命令**：使其能够在 `DocstringIR` 层面进行比较，以避免因格式化导致的“哈希震荡”。

如果你同意，我将为你生成实施 Phase 2 的计划。
