这是一个关于实现“自动处理类型注解所需的 import 语句”的详细计划。

## [WIP] feat: 增强 Scanner 以自动收集 Import 并智能补全 Typing

### 用户需求
目前的 `.pyi` 生成器生成的存根文件常常因为缺少 `import` 语句而导致类型检查失败。
用户希望 `stitcher` 能够：
1.  **保留源码中的 Imports**: 自动从源码中提取 `import` 和 `from ... import ...` 语句，并将其迁移到 `.pyi` 文件中。
2.  **智能补全 Typing**: 分析函数签名和属性注解，自动检测是否使用了 `List`, `Optional`, `Any` 等标准 `typing` 类型，并在缺失时自动添加 `from typing import ...`。
3.  **支持 TYPE_CHECKING**: 能够提取 `if TYPE_CHECKING:` 块内的 import 语句，并将其提升到 `.pyi` 的顶层。

### 评论
这是一个提升 `.pyi` 文件“合规性”和“可用性”的关键功能。
参考脚本采用了硬编码常用 import 的方式，Stitcher 将采用更智能的“按需收集 + 自动补全”策略。
利用 LibCST，我们可以轻松访问 Import 节点。对于 `if TYPE_CHECKING:` 块内的 import，LibCST 的访问者模式会自动遍历到它们，我们只需收集并去除缩进即可，这自然地实现了“提升到顶层”的效果。

### 目标
1.  更新 `stitcher-scanner` 中的 `parser.py`：
    *   修改 `IRBuildingVisitor` 以收集 `Import` 和 `ImportFrom` 节点。
    *   实现 `_enrich_typing_imports` 逻辑，基于正则分析注解并注入缺失的 `typing` 引用。
2.  添加针对 Import 收集和 Typing 补全的单元测试。

### 基本原理
-   **源码搬运**: `.pyi` 文件需要源码中定义的符号引用。最安全的方式是保留源码中的所有 import。
-   **正则探测**: 虽然无法在 parser 阶段完全解析类型（需要语义分析），但通过正则匹配注解字符串中的 `\bList\b` 等关键词，是一种高效且足够准确的启发式方法。
-   **去重**: 在添加自动补全的 import 时，需要检查是否已经存在于收集到的源码 import 中，避免重复。

### 标签
#intent/build #flow/ready #priority/high
#comp/scanner #comp/io #concept/parser #scope/core
#ai/instruct
#task/domain/dev-tools #task/object/stub-generation #task/action/implementation
#task/state/continue

---

### Script

#### Acts 1: 创建 Import 收集与 Typing 补全的测试用例

我们先定义预期行为。

~~~~~act
write_file
packages/stitcher-scanner/tests/test_parser_imports.py
~~~~~
~~~~~python
import pytest
from textwrap import dedent
from stitcher.scanner import parse_source_code


def test_collect_top_level_imports():
    source = dedent("""
    import os
    from pathlib import Path
    import sys as system
    
    def func(): pass
    """)
    
    module = parse_source_code(source)
    
    # Imports should be preserved in order
    assert len(module.imports) == 3
    assert "import os" in module.imports
    assert "from pathlib import Path" in module.imports
    assert "import sys as system" in module.imports


def test_collect_nested_imports_in_type_checking():
    """Imports inside if TYPE_CHECKING should be flattened to top-level."""
    source = dedent("""
    from typing import TYPE_CHECKING
    
    if TYPE_CHECKING:
        from my_lib import User
        import json
        
    def get_user() -> "User": ...
    """)
    
    module = parse_source_code(source)
    
    # "from typing import TYPE_CHECKING" + 2 inside block
    assert len(module.imports) >= 3
    assert "from my_lib import User" in module.imports
    assert "import json" in module.imports


def test_auto_inject_typing_imports():
    """Should automatically add missing typing imports used in annotations."""
    source = dedent("""
    def process(items: List[int]) -> Optional[str]:
        return None
    """)
    
    module = parse_source_code(source)
    
    # Should detect List and Optional usage
    combined_imports = "\n".join(module.imports)
    assert "from typing import List" in combined_imports
    assert "from typing import Optional" in combined_imports


def test_do_not_duplicate_existing_typing():
    """Should not add typing imports if they are already present."""
    source = dedent("""
    from typing import List
    
    def process(items: List[int]): ...
    """)
    
    module = parse_source_code(source)
    
    # Should only have the source import, no duplicates
    # We check that we don't have multiple lines importing List
    imports_list = [imp for imp in module.imports if "List" in imp]
    assert len(imports_list) == 1
    assert imports_list[0] == "from typing import List"


def test_detect_typing_in_attributes_and_returns():
    source = dedent("""
    VERSION: Final[str] = "1.0"
    
    class MyClass:
        data: Dict[str, Any]
        
        def method(self) -> Union[int, float]: ...
    """)
    
    module = parse_source_code(source)
    combined = "\n".join(module.imports)
    
    assert "from typing import Final" in combined
    assert "from typing import Dict" in combined
    assert "from typing import Any" in combined
    assert "from typing import Union" in combined
~~~~~

#### Acts 2: 修改 `parser.py` 实现功能

修改 `IRBuildingVisitor` 和 `parse_source_code`。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.py
~~~~~
~~~~~python.old
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
        self.functions: List[FunctionDef] = []
        self.classes: List[ClassDef] = []
        self.attributes: List[Attribute] = []

        # Scope management: A stack of currently active ClassDefs being built.
        # If stack is empty, we are at module level.
        self._class_stack: List[ClassDef] = []
        self._dummy_module = cst.Module([])  # Helper for code generation

    def _add_attribute(self, attr: Attribute):
        if self._class_stack:
~~~~~
~~~~~python.new
import re
import libcst as cst
from typing import Set
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
        self.functions: List[FunctionDef] = []
        self.classes: List[ClassDef] = []
        self.attributes: List[Attribute] = []
        self.imports: List[str] = []

        # Scope management: A stack of currently active ClassDefs being built.
        # If stack is empty, we are at module level.
        self._class_stack: List[ClassDef] = []
        self._dummy_module = cst.Module([])  # Helper for code generation

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        # Collect 'import x' statements
        # strip() removes indentation if inside a block (e.g., if TYPE_CHECKING)
        code = self._dummy_module.code_for_node(node).strip()
        self.imports.append(code)
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        # Collect 'from x import y' statements
        code = self._dummy_module.code_for_node(node).strip()
        self.imports.append(code)
        return False

    def _add_attribute(self, attr: Attribute):
        if self._class_stack:
~~~~~

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.py
~~~~~
~~~~~python.old
def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
    """
    Parses Python source code into Stitcher IR.
    """
    try:
        cst_module = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        # For now, let it bubble up or wrap in a StitcherError
        raise ValueError(f"Syntax error in {file_path}: {e}") from e

    visitor = IRBuildingVisitor()
    cst_module.visit(visitor)

    return ModuleDef(
        file_path=file_path,
        docstring=cst_module.get_docstring()
        if isinstance(cst_module.get_docstring(), str)
        else None,
        functions=visitor.functions,
        classes=visitor.classes,
        attributes=visitor.attributes,
    )
~~~~~
~~~~~python.new
def _collect_annotations(module: ModuleDef) -> Set[str]:
    """Recursively collects all type annotation strings from the module IR."""
    annotations = set()

    def add_if_exists(ann: Optional[str]):
        if ann:
            annotations.add(ann)

    # 1. Module attributes
    for attr in module.attributes:
        add_if_exists(attr.annotation)

    # 2. Functions (args + return)
    def collect_from_func(func: FunctionDef):
        add_if_exists(func.return_annotation)
        for arg in func.args:
            add_if_exists(arg.annotation)

    for func in module.functions:
        collect_from_func(func)

    # 3. Classes (attributes + methods)
    for cls in module.classes:
        for attr in cls.attributes:
            add_if_exists(attr.annotation)
        for method in cls.methods:
            collect_from_func(method)

    return annotations


def _enrich_typing_imports(module: ModuleDef):
    """
    Scans used annotations and injects missing 'typing' imports.
    """
    # Common symbols from 'typing' that are often used without quotes
    # We deliberately exclude generic 'List'/'Dict' if the user imports
    # standard collections, but for safety in .pyi (which often supports older Pythons),
    # adding them from typing is usually safe if missing.
    TYPING_SYMBOLS = {
        "List",
        "Dict",
        "Tuple",
        "Set",
        "Optional",
        "Union",
        "Any",
        "Callable",
        "Sequence",
        "Iterable",
        "Type",
        "Final",
        "ClassVar",
        "Mapping",
    }

    annotations = _collect_annotations(module)
    if not annotations:
        return

    # A simple combined string of all current imports for quick check
    existing_imports_text = "\n".join(module.imports)

    missing_symbols = set()

    for ann in annotations:
        # Check for each symbol
        for symbol in TYPING_SYMBOLS:
            # We use regex word boundary to avoid partial matches (e.g. matching 'List' in 'MyList')
            if re.search(rf"\b{symbol}\b", ann):
                # Check if it's already imported
                # This is a heuristic: if "List" appears in imports text, assume it's covered.
                # It handles "from typing import List" and "import typing" (if user wrote typing.List)
                # But wait, if user wrote "typing.List", then 'List' matches \bList\b.
                # If existing imports has "import typing", we shouldn't add "from typing import List"?
                # Actually, if they wrote "typing.List", the annotation string is "typing.List".
                # If we just add "from typing import List", it doesn't hurt.
                # But if they wrote "List" and have NO import, we MUST add it.
                
                if not re.search(rf"\b{symbol}\b", existing_imports_text):
                     missing_symbols.add(symbol)

    for symbol in sorted(missing_symbols):
        module.imports.append(f"from typing import {symbol}")


def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
    """
    Parses Python source code into Stitcher IR.
    """
    try:
        cst_module = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        # For now, let it bubble up or wrap in a StitcherError
        raise ValueError(f"Syntax error in {file_path}: {e}") from e

    visitor = IRBuildingVisitor()
    cst_module.visit(visitor)

    module_def = ModuleDef(
        file_path=file_path,
        docstring=cst_module.get_docstring()
        if isinstance(cst_module.get_docstring(), str)
        else None,
        functions=visitor.functions,
        classes=visitor.classes,
        attributes=visitor.attributes,
        imports=visitor.imports,
    )
    
    _enrich_typing_imports(module_def)
    
    return module_def
~~~~~

### 下一步建议
执行此计划后，运行测试 `packages/stitcher-scanner/tests/test_parser_imports.py` 以验证 Import 收集和自动补全功能是否按预期工作。
如果测试通过，这将显著提高生成的 `.pyi` 文件的质量，减少用户手动修复 imports 的工作量。
