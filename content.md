此计划旨在解决“数据保真度债务”中的首要问题：**不精确的符号位置**。

我们将通过以下步骤实现符号位置的精确捕获：
1.  **扩展规范 (`stitcher-spec`)**: 引入 `SourceLocation` 模型，并将其集成到 `FunctionDef`, `ClassDef` 等核心 IR 对象中。
2.  **增强解析 (`stitcher-python-analysis`)**:
    *   升级 `IRBuildingVisitor` (LibCST)，利用 `PositionProvider` 提取精确的行号和列偏移。
    *   升级 `GriffePythonParser` (Griffe)，尽最大努力提取行号信息（Griffe 对列偏移支持有限，默认为 0）。
3.  **打通适配 (`stitcher-python-adapter`)**: 更新 `PythonAdapter`，将提取到的位置信息从 `ModuleDef` 传递到最终的 `SymbolRecord` 中，取代目前硬编码的 `0`。

注意：本计划暂时将 `lineno` 映射到 `SymbolRecord.location_start`，将 `end_lineno` 映射到 `SymbolRecord.location_end`，以在不涉及大规模数据库 Schema 迁移的前提下最大化利用现有字段。

## [WIP] feat: 增强 ModuleDef 与解析器以捕获精确的符号位置

### 用户需求
目前 `stitcher-index` 中的符号记录 (`SymbolRecord`) 缺乏有效的位置信息（被硬编码为 0），导致无法支持“跳转到定义”等 IDE 核心功能。需要修改解析管道，从源码中提取精确的行号和列偏移，并传递给索引。

### 评论
这是偿还技术债务的关键一步。虽然最终目标可能需要数据库 Schema 支持更完整的 `(line, col) -> (end_line, end_col)` 范围，但目前通过填充行号，我们已经能从“不可用”跨越到“可用（精确到行）”的状态。LibCST 的引入为未来支持基于列的重构打下了坚实基础。

### 目标
1.  在 `stitcher-spec` 中定义 `SourceLocation` 数据结构。
2.  更新 `ModuleDef` 及其子实体以携带 `location` 信息。
3.  修改 `stitcher-python-analysis` 中的 LibCST 和 Griffe 解析器以填充位置信息。
4.  更新 `PythonAdapter` 以使用解析出的位置信息创建 `SymbolRecord`。

### 基本原理
我们采用“富模型”策略，在 IR 层 (`ModuleDef`) 尽可能保留完整的元数据 (`SourceLocation`)。适配层 (`Adapter`) 负责将这些丰富的信息降级或映射到当前的存储模型 (`SymbolRecord`) 中。这样保持了核心分析逻辑的纯粹性，未来如果数据库升级，分析层无需再次修改。

### 标签
#intent/refine #flow/ready #priority/high
#comp/interfaces #comp/analysis #comp/adapters
#concept/history #scope/core
#ai/instruct
#task/domain/analysis #task/object/symbol-location #task/action/enrichment
#task/state/begin

---

### Script

#### Acts 1: 扩展规范模型 (Spec)

首先，我们在 `stitcher-spec` 中定义 `SourceLocation` 并更新核心模型。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

from .docstring import DocstringIR
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

from .docstring import DocstringIR


@dataclass
class SourceLocation:
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
@dataclass
class Attribute:
    name: str
    annotation: Optional[str] = None
    value: Optional[str] = (
        None  # The string representation of the value (for constants)
    )
    docstring: Optional[str] = None


@dataclass
class FunctionDef:
    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod


@dataclass
class ClassDef:
    name: str
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.
~~~~~
~~~~~python.new
@dataclass
class Attribute:
    name: str
    annotation: Optional[str] = None
    value: Optional[str] = (
        None  # The string representation of the value (for constants)
    )
    docstring: Optional[str] = None
    location: Optional[SourceLocation] = None


@dataclass
class FunctionDef:
    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod
    location: Optional[SourceLocation] = None


@dataclass
class ClassDef:
    name: str
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    location: Optional[SourceLocation] = None
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.
~~~~~

#### Acts 2: 增强 LibCST 访问器 (CST Visitor)

更新 `IRBuildingVisitor` 以利用 `PositionProvider` 提取位置信息。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py
~~~~~
~~~~~python.old
from typing import List, Optional, Set

import re
import libcst as cst
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)


class IRBuildingVisitor(cst.CSTVisitor):
    def __init__(self):
        # Module level containers
~~~~~
~~~~~python.new
from typing import List, Optional, Set, cast

import re
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
    SourceLocation,
)


class IRBuildingVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        # Module level containers
~~~~~

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py
~~~~~
~~~~~python.old
    def _add_attribute(self, attr: Attribute):
        if self._class_stack:
            self._class_stack[-1].attributes.append(attr)
        else:
            self.attributes.append(attr)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        # Handle: x: int = 1
        if not isinstance(node.target, cst.Name):
            return False

        name = node.target.value
        value = None
        if node.value:
            value = self._dummy_module.code_for_node(node.value).strip()

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            if value:
                self.dunder_all = value
            return False

        annotation = self._dummy_module.code_for_node(
            node.annotation.annotation
        ).strip()

        self._add_attribute(Attribute(name=name, annotation=annotation, value=value))
        return False

    def visit_Assign(self, node: cst.Assign) -> Optional[bool]:
        # Handle: x = 1
        # Only handle simple assignment to a single name for now
        if len(node.targets) != 1:
            return False

        target = node.targets[0].target
        if not isinstance(target, cst.Name):
            return False

        name = target.value
        value = self._dummy_module.code_for_node(node.value).strip()

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            self.dunder_all = value
            return False

        self._add_attribute(Attribute(name=name, annotation=None, value=value))
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        # 1. Extract Name
        class_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Bases
        bases = []
        dummy_module = cst.Module([])
        for base in node.bases:
            # base.value is the expression (Name, Attribute, Call etc.)
            base_code = dummy_module.code_for_node(base.value).strip()
            bases.append(base_code)

        # 4. Extract Decorators
        decorators = []
        for dec in node.decorators:
            dec_code = dummy_module.code_for_node(dec.decorator).strip()
            decorators.append(dec_code)

        # 5. Create ClassDef object and push to stack
        cls_def = ClassDef(
            name=class_name,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
            methods=[],
            attributes=[],
        )
        self._class_stack.append(cls_def)

        # Continue visiting children (to find methods)
        return True
~~~~~
~~~~~python.new
    def _extract_location(self, node: cst.CSTNode) -> SourceLocation:
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        return SourceLocation(
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
        )

    def _add_attribute(self, attr: Attribute):
        if self._class_stack:
            self._class_stack[-1].attributes.append(attr)
        else:
            self.attributes.append(attr)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        # Handle: x: int = 1
        if not isinstance(node.target, cst.Name):
            return False

        name = node.target.value
        value = None
        if node.value:
            value = self._dummy_module.code_for_node(node.value).strip()

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            if value:
                self.dunder_all = value
            return False

        annotation = self._dummy_module.code_for_node(
            node.annotation.annotation
        ).strip()

        loc = self._extract_location(node)
        self._add_attribute(
            Attribute(
                name=name, annotation=annotation, value=value, location=loc
            )
        )
        return False

    def visit_Assign(self, node: cst.Assign) -> Optional[bool]:
        # Handle: x = 1
        # Only handle simple assignment to a single name for now
        if len(node.targets) != 1:
            return False

        target = node.targets[0].target
        if not isinstance(target, cst.Name):
            return False

        name = target.value
        value = self._dummy_module.code_for_node(node.value).strip()

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            self.dunder_all = value
            return False

        loc = self._extract_location(node)
        self._add_attribute(
            Attribute(name=name, annotation=None, value=value, location=loc)
        )
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        # 1. Extract Name
        class_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Bases
        bases = []
        dummy_module = cst.Module([])
        for base in node.bases:
            # base.value is the expression (Name, Attribute, Call etc.)
            base_code = dummy_module.code_for_node(base.value).strip()
            bases.append(base_code)

        # 4. Extract Decorators
        decorators = []
        for dec in node.decorators:
            dec_code = dummy_module.code_for_node(dec.decorator).strip()
            decorators.append(dec_code)

        # 5. Create ClassDef object and push to stack
        loc = self._extract_location(node)
        cls_def = ClassDef(
            name=class_name,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
            methods=[],
            attributes=[],
            location=loc,
        )
        self._class_stack.append(cls_def)

        # Continue visiting children (to find methods)
        return True
~~~~~

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py
~~~~~
~~~~~python.old
        # 7. Build Object
        func_def = FunctionDef(
            name=func_name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            decorators=decorators,
            is_static=is_static,
            is_class=is_class,
        )

        # 7. Add to appropriate scope
        if self._class_stack:
~~~~~
~~~~~python.new
        # 7. Build Object
        loc = self._extract_location(node)
        func_def = FunctionDef(
            name=func_name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            decorators=decorators,
            is_static=is_static,
            is_class=is_class,
            location=loc,
        )

        # 7. Add to appropriate scope
        if self._class_stack:
~~~~~

最后，更新 `parse_source_code` 以使用 `MetadataWrapper`。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py
~~~~~
~~~~~python.old
def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
    try:
        cst_module = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        # For now, let it bubble up or wrap in a StitcherError
        raise ValueError(f"Syntax error in {file_path}: {e}") from e

    visitor = IRBuildingVisitor()
    cst_module.visit(visitor)

    module_def = ModuleDef(
        file_path=file_path,
~~~~~
~~~~~python.new
def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
    try:
        cst_module = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        # For now, let it bubble up or wrap in a StitcherError
        raise ValueError(f"Syntax error in {file_path}: {e}") from e

    wrapper = cst.MetadataWrapper(cst_module)
    visitor = IRBuildingVisitor()
    wrapper.visit(visitor)

    module_def = ModuleDef(
        file_path=file_path,
~~~~~

#### Acts 3: 增强 Griffe 解析器

更新 `GriffePythonParser` 以提取 Griffe 提供的行号信息。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~
~~~~~python.old
import griffe
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
)
from stitcher.python.analysis.cst.visitors import _enrich_typing_imports
~~~~~
~~~~~python.new
import griffe
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
    SourceLocation,
)
from stitcher.python.analysis.cst.visitors import _enrich_typing_imports
~~~~~

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~
~~~~~python.old
    def _map_class(self, gc: griffe.Class) -> ClassDef:
        methods = []
        attributes = []
        for member in gc.members.values():
            if member.is_function:
                methods.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
        docstring = gc.docstring.value if gc.docstring else None
        bases = [str(b) for b in gc.bases]
        return ClassDef(
            name=gc.name,
            bases=bases,
            decorators=[str(d.value) for d in gc.decorators],
            docstring=docstring,
            attributes=attributes,
            methods=methods,
        )

    def _map_attribute(self, ga: griffe.Attribute) -> Attribute:
        annotation = str(ga.annotation) if ga.annotation else None
        value = str(ga.value) if ga.value else None
        docstring = ga.docstring.value if ga.docstring else None
        return Attribute(
            name=ga.name, annotation=annotation, value=value, docstring=docstring
        )

    def _map_function(self, gf: griffe.Function) -> FunctionDef:
        args = [self._map_argument(p) for p in gf.parameters]
        return_annotation = str(gf.returns) if gf.returns else None
        docstring = gf.docstring.value if gf.docstring else None
        return FunctionDef(
            name=gf.name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async="async" in gf.labels,
            decorators=[str(d.value) for d in gf.decorators],
            is_static="staticmethod" in gf.labels,
            is_class="classmethod" in gf.labels,
        )
~~~~~
~~~~~python.new
    def _extract_location(self, obj: griffe.Object) -> Optional[SourceLocation]:
        if obj.lineno:
            return SourceLocation(
                lineno=obj.lineno,
                col_offset=0,  # Griffe doesn't provide column
                end_lineno=obj.end_lineno or obj.lineno,
                end_col_offset=0,
            )
        return None

    def _map_class(self, gc: griffe.Class) -> ClassDef:
        methods = []
        attributes = []
        for member in gc.members.values():
            if member.is_function:
                methods.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
        docstring = gc.docstring.value if gc.docstring else None
        bases = [str(b) for b in gc.bases]
        return ClassDef(
            name=gc.name,
            bases=bases,
            decorators=[str(d.value) for d in gc.decorators],
            docstring=docstring,
            attributes=attributes,
            methods=methods,
            location=self._extract_location(gc),
        )

    def _map_attribute(self, ga: griffe.Attribute) -> Attribute:
        annotation = str(ga.annotation) if ga.annotation else None
        value = str(ga.value) if ga.value else None
        docstring = ga.docstring.value if ga.docstring else None
        return Attribute(
            name=ga.name,
            annotation=annotation,
            value=value,
            docstring=docstring,
            location=self._extract_location(ga),
        )

    def _map_function(self, gf: griffe.Function) -> FunctionDef:
        args = [self._map_argument(p) for p in gf.parameters]
        return_annotation = str(gf.returns) if gf.returns else None
        docstring = gf.docstring.value if gf.docstring else None
        return FunctionDef(
            name=gf.name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async="async" in gf.labels,
            decorators=[str(d.value) for d in gf.decorators],
            is_static="staticmethod" in gf.labels,
            is_class="classmethod" in gf.labels,
            location=self._extract_location(gf),
        )
~~~~~

#### Acts 4: 打通适配器 (Adapter)

最后，更新 `PythonAdapter`，将 `ModuleDef` 中的 `location` 传递给 `SymbolRecord`。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
            # Location is currently not provided by ModuleDef in a granular way easily
            # (Griffe objects have lineno, but ModuleDef might have lost it or it's deep).
            # For MVP, we use 0, 0 as placeholder or we need to extend ModuleDef to carry location.
            # Extending ModuleDef is the right way, but for now we proceed.
            # TODO: Enhance ModuleDef to carry source location info.

            symbols.append(
                SymbolRecord(
                    id=suri,
                    name=name,
                    kind=kind,
                    location_start=0,  # Placeholder
                    location_end=0,  # Placeholder
                    logical_path=fragment,  # This is relative logical path in file
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
                add(attr.name, "variable", None, parent_fragment=cls_frag)

        # 3. Module-level Attributes
        for attr in module.attributes:
            add(attr.name, "variable", None)
~~~~~
~~~~~python.new
            # Location Handling
            # We assume entity_for_hash also carries the location info if it is a Def object.
            # Attribute locations are passed via entity_for_hash if it's an Attribute obj.
            # But the 'add' signature treats entity_for_hash as Optional[object].
            # We should check if it has a 'location' attribute.
            loc_start = 0
            loc_end = 0

            if hasattr(entity_for_hash, "location") and entity_for_hash.location:
                # Mapping Strategy: Use lineno for location_start and end_lineno for location_end
                # This provides line-level precision for jump-to-definition.
                loc = entity_for_hash.location
                loc_start = loc.lineno
                loc_end = loc.end_lineno

            symbols.append(
                SymbolRecord(
                    id=suri,
                    name=name,
                    kind=kind,
                    location_start=loc_start,
                    location_end=loc_end,
                    logical_path=fragment,  # This is relative logical path in file
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
~~~~~

### 下一步建议

现在位置信息已经打通，我们可以继续解决 **Debt 1.2: 引用分析**。
建议的下一步是：
1.  在 `stitcher-python-analysis` 中完善 `UsageScanVisitor`，使其能够处理更复杂的引用场景。
2.  确保 `PythonAdapter` 中的引用提取逻辑能够利用这个 Visitor 并正确生成 `ReferenceRecord`。
