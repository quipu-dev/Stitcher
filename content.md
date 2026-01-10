常用的别名解析是构建高保真语义图谱的关键基石。我将为您生成计划，首先在 IR 层引入别名概念，然后在 Parser 层捕获它们。

这将包括：
1.  **IR 升级**：在 `stitcher-spec` 中扩展 `Attribute` 模型。
2.  **Parser 升级**：修改 `GriffePythonParser` 以捕获 Alias 并映射为 `Attribute`。
3.  **验证**：添加针对 `import` 和 `from ... import` 场景的单元测试。

## [WIP] feat: 在 IR 和 Parser 中引入 Alias 支持以增强引用分析

### 用户需求
为了解决“缺失的别名解析 (Missing Alias Resolution)”这一技术债务，需要在 Stitcher 的中间表示 (IR) 和解析器中显式支持 Python 的别名 (Alias) 机制（主要通过 `import` 语句产生）。

### 评论
这是修复数据保真度债务的**第一步**。通过不再丢弃别名，我们为后续的“引用解析”和“跨模块跳转”提供了必要的锚点。目前的实现中，`import` 语句在符号表中是不可见的，这导致所有基于此的分析都断链了。

### 目标
1.  修改 `stitcher-spec` 的 `Attribute` 模型，增加 `alias_target` 字段，用于存储别名指向的逻辑 FQN。
2.  修改 `stitcher-python-adapter` 中的 `GriffePythonParser`，移除过滤 `is_alias` 的逻辑，并将 Griffe 的 Alias 对象映射为带有 `alias_target` 的 `Attribute`。
3.  在 `test_griffe_parser.py` 中添加测试用例，验证 `import` 和 `from ... import` 语句能够正确生成 `Attribute` 记录。

### 基本原理
Griffe 解析器实际上已经识别了 Alias，但之前的代码主动将其过滤掉了。我们需要：
1.  **数据模型**：由于 Alias 本质上是一个绑定了名称的实体，使用现有的 `Attribute` 模型承载它是最合理的（类似于变量），只需增加一个字段指明它指向何处。
2.  **映射逻辑**：Griffe 的 `Alias` 对象包含 `target_path`，这正是我们需要的逻辑 FQN。我们将利用它填充新字段。

### 标签
#intent/architect #intent/build #flow/ready #priority/high
#comp/interfaces #comp/analysis #scope/core
#ai/instruct
#task/domain/analysis #task/object/alias-resolution #task/action/implementation
#task/state/begin #task/status/active

---

### Script

#### Acts 1: 更新 IR 模型

首先在 `stitcher-spec` 中为 `Attribute` 增加 `alias_target` 字段。

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
    location: Optional[SourceLocation] = None
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
    alias_target: Optional[str] = None  # The logical FQN this alias points to
~~~~~

#### Acts 2: 更新 Griffe 解析器逻辑

修改 `GriffePythonParser`，增加 `_map_alias` 方法，并在模块和类的成员遍历中启用它。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~
~~~~~python.old
    def _map_module(
        self, gm: griffe.Module, file_path: str, imports: List[str]
    ) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            if member.is_alias:
                continue
            if member.is_function:
                functions.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_class:
                classes.append(self._map_class(cast(griffe.Class, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))

        docstring = gm.docstring.value if gm.docstring else None
~~~~~
~~~~~python.new
    def _map_module(
        self, gm: griffe.Module, file_path: str, imports: List[str]
    ) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            if member.is_alias:
                attributes.append(self._map_alias(cast(griffe.Alias, member)))
            elif member.is_function:
                functions.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_class:
                classes.append(self._map_class(cast(griffe.Class, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))

        docstring = gm.docstring.value if gm.docstring else None
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
~~~~~
~~~~~python.new
    def _map_class(self, gc: griffe.Class) -> ClassDef:
        methods = []
        attributes = []
        for member in gc.members.values():
            if member.is_alias:
                attributes.append(self._map_alias(cast(griffe.Alias, member)))
            elif member.is_function:
                methods.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
        docstring = gc.docstring.value if gc.docstring else None
        bases = [str(b) for b in gc.bases]
~~~~~

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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

    def _map_alias(self, ga: griffe.Alias) -> Attribute:
        # Alias doesn't have a value or annotation typically, but it has a target path.
        return Attribute(
            name=ga.name,
            alias_target=ga.target_path,
            location=self._extract_location(ga),
        )

    def _map_function(self, gf: griffe.Function) -> FunctionDef:
~~~~~

#### Acts 3: 添加单元测试

在 `test_griffe_parser.py` 中添加针对 Alias 的测试用例。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/test_griffe_parser.py
~~~~~
~~~~~python.old
    def test_enrich_typing_imports(self, parser):
        # Code explicitly missing 'from typing import List'
        code = """
def process_list(items: List[int]) -> None:
    pass
"""
        module = parser.parse(code)

        # Check that the import was added automatically
        assert "from typing import List" in module.imports
~~~~~
~~~~~python.new
    def test_enrich_typing_imports(parser):
        # Code explicitly missing 'from typing import List'
        code = """
def process_list(items: List[int]) -> None:
    pass
"""
        module = parser.parse(code)

        # Check that the import was added automatically
        assert "from typing import List" in module.imports

    def test_parse_aliases(self, parser):
        code = """
import os
from typing import List
from . import sibling
import sys as system
"""
        # Griffe treats imports as Aliases if they are members of the module
        module = parser.parse(code)

        # We expect attributes for these imports now
        # Note: 'import os' creates an alias 'os' pointing to 'os'
        # 'from typing import List' creates an alias 'List' pointing to 'typing.List'
        # 'from . import sibling' creates 'sibling' pointing to '....sibling' (resolved path)
        # 'import sys as system' creates 'system' pointing to 'sys'

        # Filter attributes that have alias_target
        aliases = [a for a in module.attributes if a.alias_target]

        # 1. os
        attr_os = next((a for a in aliases if a.name == "os"), None)
        assert attr_os is not None
        assert attr_os.alias_target == "os"

        # 2. List
        attr_list = next((a for a in aliases if a.name == "List"), None)
        assert attr_list is not None
        assert attr_list.alias_target == "typing.List"

        # 3. system
        attr_sys = next((a for a in aliases if a.name == "system"), None)
        assert attr_sys is not None
        assert attr_sys.alias_target == "sys"
~~~~~

### 下一步建议
1.  **Atomic Task 3**: 修改 `stitcher-python-adapter` 的 `PythonAdapter`，使其能处理带有 `alias_target` 的 `Attribute`，并在生成 `SymbolRecord` 时计算并填充 `alias_target_id`（SURI）。
2.  **Atomic Task 4**: 更新引用分析逻辑 (`index_adapter.py`)，将新识别出的 Alias 符号加入到本地符号表 (`local_symbols`) 中，从而打通引用链。
