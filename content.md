好的，我将重新生成计划，移除之前有误导性的、重复的 `patch` 操作，并根据协议将涉及大规模重构的文件操作更改为 `write_file`，使计划更清晰、准确。

[简要回答]
我们将开始执行 Phase 2，核心任务是引入 Griffe 解析器和结构化渲染器，并升级 `DocumentManager` 以支持 Google 风格文档的序列化与存储。

## [WIP] feat: 实现结构化文档支持 (Griffe Parser & Google Renderer)

### 用户需求
根据实施路线图 Phase 2，需要：
1.  **解析能力**: 利用 `griffe` 将 Python 文档字符串解析为 `DocstringIR` (中间表示)。
2.  **渲染能力**: 实现将 `DocstringIR` 渲染回 Google 风格字符串的 Renderers。
3.  **序列化能力**: 升级 `DocumentManager`，使其能根据配置将 IR 序列化为结构化的 YAML (如 `Summary`, `Args`)。
4.  **集成**: 确保 Runner 可以将配置中的 `docstring_style` 传递给底层服务。

### 评论
这是 Stitcher 从单纯的“文档搬运工”向“文档理解者”进化的关键一步。通过结构化存储，我们不仅能支持文档格式化 (`fmt`)，还能在未来实现对参数、返回值等细粒度元素的独立校验和合并。

### 目标
1.  在 `stitcher-python-adapter` 中实现 `GriffeDocstringParser` 和 `GoogleDocstringRenderer`。
2.  重构 `DocumentManager` 以支持多风格解析和序列化。
3.  更新 `InitRunner` 和 `PumpRunner` 以适配新的 API。

### 基本原理
我们将采用策略模式：
*   **Adapter 层**: 提供具体的 `Parser` 和 `Renderer` 实现。
*   **Service 层**: `DocumentManager` 作为调度器，根据传入的 `style` 参数选择正确的策略。
*   **Data 层**: YAML 存储将根据 style 自动在 "Raw String" (默认) 和 "Structured Dict" (Google/Numpy) 之间切换。

### 标签
#intent/build #flow/ready #priority/high #comp/adapter #comp/application #concept/docstring #task/domain/documentation #task/object/structured-docstrings #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 实现文档渲染器 (Renderers)

首先，我们需要一种将 `DocstringIR` 转换回字符串的方法。我们创建 `GoogleDocstringRenderer` 来实现 Google 风格的渲染。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py
~~~~~
~~~~~python
from stitcher.spec import DocstringRendererProtocol, DocstringIR


class GoogleDocstringRenderer(DocstringRendererProtocol):
    """
    Renders DocstringIR into Google-style docstring format.
    """

    def render(self, ir: DocstringIR) -> str:
        lines = []

        # 1. Summary
        if ir.summary:
            lines.append(ir.summary)

        # 2. Extended Description
        if ir.extended:
            if lines:
                lines.append("")  # Blank line separator
            lines.append(ir.extended)

        # 3. Sections
        for section in ir.sections:
            if not lines or lines[-1] != "":
                lines.append("")  # Ensure blank line before section

            if section.kind == "text":
                if isinstance(section.content, str):
                    lines.append(section.content)
                continue

            title = section.title or self._map_kind_to_title(section.kind)
            lines.append(f"{title}:")

            if isinstance(section.content, list):
                for item in section.content:
                    parts = []
                    if item.name:
                        parts.append(item.name)
                    
                    if item.annotation:
                        if item.name:
                            parts.append(f"({item.annotation})")
                        else:
                            parts.append(item.annotation)
                    
                    prefix = " ".join(parts)
                    
                    if item.description:
                        desc_lines = item.description.split('\n')
                        first_line = desc_lines[0] if desc_lines else ""
                        remaining_lines = desc_lines[1:] if len(desc_lines) > 1 else []
                        
                        line_start = f"  {prefix}: {first_line}" if prefix else f"  {first_line}"
                        lines.append(line_start)
                        
                        for rem_line in remaining_lines:
                            lines.append(f"    {rem_line}")
                    else:
                        lines.append(f"  {prefix}")

            elif isinstance(section.content, str):
                for line in section.content.split('\n'):
                    lines.append(f"  {line}")

        return "\n".join(lines)

    def _map_kind_to_title(self, kind: str) -> str:
        mapping = {
            "args": "Args",
            "arguments": "Args",
            "params": "Args",
            "parameters": "Args",
            "returns": "Returns",
            "yields": "Yields",
            "raises": "Raises",
            "exceptions": "Raises",
            "attributes": "Attributes",
            "examples": "Examples",
        }
        return mapping.get(kind.lower(), kind.capitalize())
~~~~~

#### Acts 2: 实现 Griffe 解析器

利用 `griffe` 库将源代码中的文档字符串解析为结构化的 `DocstringIR`。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/griffe_parser.py
~~~~~
~~~~~python
from typing import Any
import griffe.docstrings.google as google_parser
import griffe.docstrings.dataclasses as ds
from stitcher.spec import (
    DocstringParserProtocol,
    DocstringIR,
    DocstringSection,
    DocstringItem,
)


class GriffeDocstringParser(DocstringParserProtocol):
    """
    Parses docstrings using Griffe's Google-style parser.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()

        try:
            parsed = google_parser.parse(docstring_text)
        except Exception:
            return DocstringIR(summary=docstring_text)

        ir = DocstringIR()
        
        for section in parsed:
            if isinstance(section, ds.DocstringSectionText):
                text = section.value
                if not ir.summary:
                    parts = text.split('\n', 1)
                    ir.summary = parts[0]
                    if len(parts) > 1:
                        ir.extended = parts[1].strip()
                else:
                    if ir.extended:
                        ir.extended += "\n\n" + text
                    else:
                        ir.extended = text
            
            elif isinstance(section, ds.DocstringSectionAttributes):
                ir.sections.append(self._convert_param_section(section, "attributes"))
            elif isinstance(section, ds.DocstringSectionParameters):
                ir.sections.append(self._convert_param_section(section, "args"))
            elif isinstance(section, ds.DocstringSectionReturns):
                ir.sections.append(self._convert_return_section(section, "returns"))
            elif isinstance(section, ds.DocstringSectionYields):
                ir.sections.append(self._convert_return_section(section, "yields"))
            elif isinstance(section, ds.DocstringSectionRaises):
                ir.sections.append(self._convert_raises_section(section, "raises"))

        return ir

    def _convert_param_section(self, section: Any, kind: str) -> DocstringSection:
        items = []
        for param in section.value:
            items.append(
                DocstringItem(
                    name=param.name,
                    annotation=str(param.annotation) if param.annotation else None,
                    description=param.description,
                    default=str(param.default) if param.default else None,
                )
            )
        return DocstringSection(kind=kind, title=section.title, content=items)

    def _convert_return_section(self, section: Any, kind: str) -> DocstringSection:
        items = []
        for ret in section.value:
            items.append(
                DocstringItem(
                    name=ret.name,
                    annotation=str(ret.annotation) if ret.annotation else None,
                    description=ret.description,
                )
            )
        return DocstringSection(kind=kind, title=section.title, content=items)

    def _convert_raises_section(self, section: Any, kind: str) -> DocstringSection:
        items = []
        for exc in section.value:
            items.append(
                DocstringItem(
                    annotation=str(exc.annotation),
                    description=exc.description,
                )
            )
        return DocstringSection(kind=kind, title=section.title, content=items)
~~~~~

#### Acts 3: 导出新组件

在 `stitcher-python-adapter` 包的 `__init__.py` 中导出新创建的解析器和渲染器，使其对上层应用可见。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/__init__.py
~~~~~
~~~~~python.old
from .parser import PythonParser
from .transformer import PythonTransformer
from .generator import PythonStubGenerator
from .fingerprint import PythonFingerprintStrategy
from .inspector import parse_plugin_entry, InspectionError
from .griffe_parser import GriffePythonParser
from .docstring.raw_parser import RawDocstringParser

__all__ = [
    "RawDocstringParser",
    "PythonParser",
    "PythonTransformer",
    "PythonStubGenerator",
    "PythonFingerprintStrategy",
    "parse_plugin_entry",
    "InspectionError",
    "GriffePythonParser",
]
~~~~~
~~~~~python.new
from .parser import PythonParser
from .transformer import PythonTransformer
from .generator import PythonStubGenerator
from .fingerprint import PythonFingerprintStrategy
from .inspector import parse_plugin_entry, InspectionError
from .griffe_parser import GriffePythonParser
from .docstring.raw_parser import RawDocstringParser
from .docstring.griffe_parser import GriffeDocstringParser
from .docstring.renderers import GoogleDocstringRenderer

__all__ = [
    "RawDocstringParser",
    "GriffeDocstringParser",
    "GoogleDocstringRenderer",
    "PythonParser",
    "PythonTransformer",
    "PythonStubGenerator",
    "PythonFingerprintStrategy",
    "parse_plugin_entry",
    "InspectionError",
    "GriffePythonParser",
]
~~~~~

#### Acts 4: 升级 DocumentManager

`DocumentManager` 是本次重构的核心。我们将使用 `write_file` 彻底重写它，引入策略模式来根据配置选择不同的解析器和序列化逻辑。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
)
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser, GriffeDocstringParser


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        self.parsers: Dict[str, DocstringParserProtocol] = {
            "raw": RawDocstringParser(),
            "google": GriffeDocstringParser(),
        }

    def _get_parser(self, style: str) -> DocstringParserProtocol:
        return self.parsers.get(style, self.parsers["raw"])

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        if isinstance(data, str):
            return DocstringIR(summary=data)
        
        if isinstance(data, dict):
            ir = DocstringIR()
            ir.addons = {k: v for k, v in data.items() if k.startswith("Addon.")}
            
            if "Raw" in data:
                ir.summary = data["Raw"]
                return ir

            if "Summary" in data:
                ir.summary = data["Summary"]
            if "Extended" in data:
                ir.extended = data["Extended"]
            
            # Note: For now, we don't deserialize structured sections back into IR fully.
            # This is sufficient for check/pump logic that relies on summary comparison.
            # Full deserialization would be needed for 'inject --style=google'.
            return ir
            
        return DocstringIR()

    def _serialize_ir(
        self, ir: DocstringIR, style: str = "raw"
    ) -> Union[str, Dict[str, Any]]:
        if style == "google":
            output: Dict[str, Any] = {}
            if ir.summary:
                output["Summary"] = ir.summary
            if ir.extended:
                output["Extended"] = ir.extended
            
            key_map = {
                "args": "Args",
                "returns": "Returns",
                "raises": "Raises",
                "attributes": "Attributes",
            }
            for section in ir.sections:
                key = key_map.get(section.kind)
                if key and isinstance(section.content, list):
                    section_dict = {}
                    for item in section.content:
                        if item.name:
                            # Per schema, only description is stored directly
                            section_dict[item.name] = item.description or ""
                        elif item.annotation: # e.g. for Returns
                             section_dict[item.annotation] = item.description or ""
                    if section_dict:
                        output[key] = section_dict

            if ir.addons:
                output.update(ir.addons)
            return output

        summary = ir.summary or ""
        if ir.addons:
            output = {"Raw": summary}
            output.update(ir.addons)
            return output
            
        return summary

    def _extract_from_function(
        self, func: FunctionDef, parser: DocstringParserProtocol, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{func.name}"
        if func.docstring:
            docs[full_name] = parser.parse(func.docstring)
        return docs

    def _extract_from_class(
        self, cls: ClassDef, parser: DocstringParserProtocol, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{cls.name}"
        if cls.docstring:
            docs[full_name] = parser.parse(cls.docstring)
        for method in cls.methods:
            docs.update(self._extract_from_function(method, parser, prefix=f"{full_name}."))
        return docs

    def flatten_module_docs(
        self, module: ModuleDef, style: str = "raw"
    ) -> Dict[str, DocstringIR]:
        parser = self._get_parser(style)
        docs: Dict[str, DocstringIR] = {}
        if module.docstring:
            docs["__doc__"] = parser.parse(module.docstring)
        for func in module.functions:
            docs.update(self._extract_from_function(func, parser))
        for cls in module.classes:
            docs.update(self._extract_from_class(cls, parser))
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = parser.parse(attr.docstring)
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = parser.parse(attr.docstring)
        return docs

    def save_docs_for_module(self, module: ModuleDef, style: str = "raw") -> Path:
        ir_map = self.flatten_module_docs(module, style=style)
        if not ir_map:
            return Path("")
        
        yaml_data = {
            fqn: self._serialize_ir(ir, style=style) for fqn, ir in ir_map.items()
        }
        
        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        self.adapter.save(output_path, yaml_data)
        return output_path

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        raw_data = self.adapter.load(doc_path)
        return {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}

    def _apply_to_function(
        self, func: FunctionDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{func.name}"
        if full_name in docs:
            func.docstring_ir = docs[full_name]

    def _apply_to_class(
        self, cls: ClassDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{cls.name}"
        if full_name in docs:
            cls.docstring_ir = docs[full_name]
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
            module.docstring_ir = docs["__doc__"]
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
        style: str = "raw",
    ) -> Dict[str, Any]:
        resolution_map = resolution_map or {}
        source_docs = self.flatten_module_docs(module, style=style)
        if not source_docs:
            return {
                "success": True, "updated_keys": [], "conflicts": [], "reconciled_keys": []
            }
        
        yaml_docs = self.load_docs_for_module(module)
        updated_keys = []
        conflicts = []
        reconciled_keys = []
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
                    action = resolution_map.get(key)
                    should_force = force or (action == "HYDRATE_OVERWRITE")
                    should_reconcile = reconcile or (action == "HYDRATE_KEEP_EXISTING")

                    if should_reconcile:
                        reconciled_keys.append(key)
                        continue
                    elif should_force:
                        source_ir.addons = existing_ir.addons
                        new_yaml_docs_ir[key] = source_ir
                        updated_keys.append(key)
                    else:
                        conflicts.append(key)

        if conflicts:
            return {"success": False, "updated_keys": [], "conflicts": conflicts, "reconciled_keys": []}

        if updated_keys and not dry_run:
            final_data = {
                fqn: self._serialize_ir(ir, style=style)
                for fqn, ir in new_yaml_docs_ir.items()
            }
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, final_data)

        return {"success": True, "updated_keys": updated_keys, "conflicts": [], "reconciled_keys": reconciled_keys}

    def _extract_keys(self, module: ModuleDef, public_only: bool) -> set:
        keys = set()
        if module.docstring:
            keys.add("__doc__")

        def include(name: str) -> bool:
            return not name.startswith("_") if public_only else True

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
        if isinstance(content, str):
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        if isinstance(content, dict):
            canonical_json = json.dumps(content, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
            
        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
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

        raw_data = self.adapter.load(doc_path)
        if not raw_data:
            return False

        # Assuming style from config... for now, let's assume raw reformatting.
        # A full reformat would need style info.
        # This implementation just re-saves with sorting.
        # TODO: Accept style for full reformatting.
        irs = {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}
        formatted_data = {fqn: self._serialize_ir(ir) for fqn, ir in irs.items()}
        
        self.adapter.save(doc_path, formatted_data)
        return True
~~~~~

#### Acts 5: 更新 `InitRunner` 以传递 style

更新 `InitRunner`，使其在 `save_docs_for_module` 时传递从配置中读取的 `docstring_style`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)

                # Use the new unified compute method
~~~~~
~~~~~python.new
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(
                    module, style=config.docstring_style
                )

                # Use the new unified compute method
~~~~~

#### Acts 6: 升级 `PumpRunner` 以支持多风格处理

最后，我们重写 `PumpRunner` 的 `run` 方法，使其能够处理 `docstring_style` 配置，并将该样式传递给 `DocumentManager` 的相关方法，确保在 `pump` 期间能正确地解析和序列化文档。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path, StitcherConfig
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
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
        style: str = "raw",
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager.flatten_module_docs(module, style=style)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                pass
            else:
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

        modules_by_config: Dict[str, List[ModuleDef]] = defaultdict(list)
        all_conflicts: List[InteractionContext] = []

        # --- Phase 1: Analysis ---
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            if not modules:
                continue
            modules_by_config[config.name].extend(modules)

            for module in modules:
                res = self.doc_manager.hydrate_module(
                    module,
                    force=False,
                    reconcile=False,
                    dry_run=True,
                    style=config.docstring_style,
                )
                if not res["success"]:
                    source_docs = self.doc_manager.flatten_module_docs(
                        module, style=config.docstring_style
                    )
                    yaml_docs = self.doc_manager.load_docs_for_module(module)
                    for key in res["conflicts"]:
                        yaml_summary = (
                            yaml_docs[key].summary if key in yaml_docs else ""
                        )
                        src_summary = (
                            source_docs[key].summary if key in source_docs else ""
                        )
                        doc_diff = self.differ.generate_text_diff(
                            yaml_summary or "", src_summary or "", "yaml", "code"
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
        total_updated_keys, total_reconciled_keys, unresolved_conflicts_count = 0, 0, 0

        for config in configs:
            modules = modules_by_config[config.name]
            for module in modules:
                file_plan = self._generate_execution_plan(
                    module, decisions, strip, style=config.docstring_style
                )
                source_docs = self.doc_manager.flatten_module_docs(
                    module, style=config.docstring_style
                )
                current_yaml_docs = self.doc_manager.load_docs_for_module(module)
                stored_hashes = self.sig_manager.load_composite_hashes(module)
                current_fingerprints = self.sig_manager.compute_fingerprints(module)

                new_yaml_docs = current_yaml_docs.copy()
                new_hashes = copy.deepcopy(stored_hashes)
                file_had_updates, file_has_errors, file_has_redundancy = False, False, False
                updated_keys_in_file, reconciled_keys_in_file = [], []

                for fqn, plan in file_plan.items():
                    if decisions.get(fqn) == ResolutionAction.SKIP:
                        unresolved_conflicts_count += 1
                        file_has_errors = True
                        bus.error(
                            L.pump.error.conflict, path=module.file_path, key=fqn
                        )
                        continue

                    if plan.hydrate_yaml and fqn in source_docs:
                        merged_ir = self.merger.merge(
                            new_yaml_docs.get(fqn), source_docs[fqn]
                        )
                        if new_yaml_docs.get(fqn) != merged_ir:
                            new_yaml_docs[fqn] = merged_ir
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

                    if plan.update_doc_fingerprint:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            serialized = self.doc_manager._serialize_ir(
                                ir_to_save, style=config.docstring_style
                            )
                            doc_hash = self.doc_manager.compute_yaml_content_hash(serialized)
                            fp["baseline_yaml_content_hash"] = doc_hash
                            fqn_was_updated = True
                    
                    if fqn_was_updated:
                        new_hashes[fqn] = fp
                    
                    if decisions.get(fqn) == ResolutionAction.HYDRATE_KEEP_EXISTING:
                        reconciled_keys_in_file.append(fqn)

                    if plan.strip_source_docstring:
                        strip_jobs[module.file_path].append(fqn)
                    
                    if fqn in source_docs and not plan.strip_source_docstring:
                        file_has_redundancy = True

                if not file_has_errors:
                    if file_had_updates:
                        final_data = {
                            k: self.doc_manager._serialize_ir(v, style=config.docstring_style)
                            for k, v in new_yaml_docs.items()
                        }
                        module_path = self.root_path / module.file_path
                        doc_path = module_path.with_suffix(".stitcher.yaml")
                        self.doc_manager.adapter.save(doc_path, final_data)

                    if new_hashes != stored_hashes:
                        self.sig_manager.save_composite_hashes(module, new_hashes)

                    if file_has_redundancy:
                        redundant_files_list.append(self.root_path / module.file_path)

                if updated_keys_in_file:
                    total_updated_keys += len(updated_keys_in_file)
                    bus.success(
                        L.pump.file.success,
                        path=module.file_path,
                        count=len(updated_keys_in_file),
                    )

                if reconciled_keys_in_file:
                    total_reconciled_keys += len(reconciled_keys_in_file)
                    bus.info(
                        L.pump.info.reconciled,
                        path=module.file_path,
                        count=len(reconciled_keys_in_file),
                    )

        # --- Phase 5: Stripping ---
        if strip_jobs:
            total_stripped_files = 0
            for file_path, whitelist in strip_jobs.items():
                source_path = self.root_path / file_path
                if not whitelist:
                    continue
                try:
                    original_content = source_path.read_text("utf-8")
                    stripped_content = self.transformer.strip(
                        original_content, whitelist=whitelist
                    )
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, "utf-8")
                        bus.success(
                            L.strip.file.success,
                            path=source_path.relative_to(self.root_path),
                        )
                        total_stripped_files += 1
                except Exception as e:
                    bus.error(L.error.generic, error=e)

            if total_stripped_files > 0:
                bus.success(L.strip.run.complete, count=total_stripped_files)

        # Final Reporting
        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)

        has_activity = (total_updated_keys > 0) or strip_jobs

        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)

        return PumpResult(success=True, redundant_files=redundant_files_list)
~~~~~

### 下一步建议
我们已经完成了核心逻辑的实现。下一步建议：
1.  **添加测试**: 为 `GriffeDocstringParser` 和 `GoogleDocstringRenderer` 添加单元测试，验证其解析和渲染的正确性。
2.  **集成测试**: 创建一个集成测试场景，配置 `docstring_style = "google"`，运行 `init` 和 `pump`，验证生成的 YAML 是否符合预期的字典结构。
3.  **完善反序列化**: 目前 `_deserialize_ir` 对于结构化数据的加载还比较简陋。如果需要支持 `stitcher inject` 将结构化文档注回代码，我们需要完善这一部分。
