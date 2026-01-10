## [WIP] fix: 修复 Griffe 解析器中的 Alias 解析崩溃与测试错误

### 错误分析

1.  **`AliasResolutionError` 崩溃**:
    *   **原因**: `GriffePythonParser._extract_location` 试图访问 `obj.lineno`。对于 `Alias` 对象，Griffe 的实现会尝试解析其指向的目标（`resolve_target`）以获取目标的行号。在单文件解析模式下，外部依赖（如 `os`, `typing`）无法解析，导致抛出 `AliasResolutionError`。
    *   **影响**: 所有包含外部导入的代码解析都会失败。

2.  **`BuiltinModuleError` 崩溃**:
    *   **原因**: 在单元测试中调用 `parser.parse(code)` 时未提供 `file_path`。Griffe 内部在处理特定节点时依赖文件路径来判断模块属性，空路径导致了错误。

3.  **`AttributeError` 测试错误**:
    *   **原因**: `test_enrich_typing_imports` 定义在测试类中，但缺少 `self` 参数，导致 Pytest 注入 fixture 失败或方法绑定错误。

### 用户需求
修复当前的构建和测试失败，确保 Alias 解析功能的鲁棒性，即使在无法解析外部目标的情况下也能正常工作（降级为无位置信息，而不是崩溃）。

### 评论
Griffe 的设计意图是构建完整的语义树，因此它积极地尝试解析别名。但在 Stitcher 的场景中，我们需要的是“文件内的定义”，而非“最终的定义”。由于 Griffe 的 Alias 对象似乎不直接存储定义位置（而是代理给目标），我们目前只能先通过异常捕获来防止崩溃。未来可能需要通过 AST 增强来获取准确的 Import 语句位置。

### 目标
1.  修改 `_extract_location`，增加对获取 `lineno` 时可能抛出的异常的捕获处理。
2.  修复 `test_griffe_parser.py` 中的测试方法签名和参数传递问题。

### 基本原理
通过 `try...except` 块包裹 `obj.lineno` 的访问，我们可以安全地处理那些指向外部且无法解析的别名。虽然这会导致这些别名暂时失去位置信息（Location 为 None），但这比整个解析过程崩溃要好得多，且不影响“别名存在性”这一核心价值。

### 标签
#intent/fix #flow/ready #priority/high
#comp/analysis #scope/core #ai/instruct
#task/domain/analysis #task/object/alias-resolution #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 增强 _extract_location 的鲁棒性

我们将在访问 `lineno` 时捕获潜在的解析错误。由于 Griffe 的异常定义在私有模块或难以直接导入，我们将捕获通用的 `Exception` 但仅限于 `lineno` 访问这一行，并添加注释说明原因。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~
~~~~~python.old
    def _extract_location(self, obj: griffe.Object) -> Optional[SourceLocation]:
        if obj.lineno:
            # Safely access end_lineno as it might not be present on base Object type
            end_lineno = getattr(obj, "end_lineno", None) or obj.lineno
            return SourceLocation(
                lineno=obj.lineno,
                col_offset=0,  # Griffe doesn't provide column
                end_lineno=end_lineno,
                end_col_offset=0,
            )
        return None
~~~~~
~~~~~python.new
    def _extract_location(self, obj: griffe.Object) -> Optional[SourceLocation]:
        try:
            # Accessing lineno on an Alias triggers target resolution.
            # If the target is external/unresolvable, this raises AliasResolutionError (or KeyError).
            # We catch generic Exception here to be safe against Griffe internals,
            # accepting that unresolvable aliases will have no location for now.
            if obj.lineno:
                # Safely access end_lineno as it might not be present on base Object type
                end_lineno = getattr(obj, "end_lineno", None) or obj.lineno
                return SourceLocation(
                    lineno=obj.lineno,
                    col_offset=0,  # Griffe doesn't provide column
                    end_lineno=end_lineno,
                    end_col_offset=0,
                )
        except Exception:
            pass
        return None
~~~~~

#### Acts 2: 修复测试用例错误

修复 `test_griffe_parser.py` 中的签名错误，并在调用 `parse` 时传入虚拟文件路径。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/test_griffe_parser.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    def test_enrich_typing_imports(self, parser):
        # Code explicitly missing 'from typing import List'
        code = """
def process_list(items: List[int]) -> None:
    pass
"""
        module = parser.parse(code, file_path="test_typing.py")

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
        # We must provide a file path so Griffe doesn't treat it as a builtin module error
        module = parser.parse(code, file_path="test_aliases.py")

        # We expect attributes for these imports now
~~~~~

#### Acts 3: 修复 TestGriffeParserStructure.test_parse_imports 

这个测试同样需要传入 `file_path`。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/test_griffe_parser.py
~~~~~
~~~~~python.old
    def test_parse_imports(self, parser):
        code = """
import os
from typing import List, Optional
import sys as system
"""
        module = parser.parse(code)

        # ast.unparse normalizes output
~~~~~
~~~~~python.new
    def test_parse_imports(self, parser):
        code = """
import os
from typing import List, Optional
import sys as system
"""
        module = parser.parse(code, file_path="test_imports.py")

        # ast.unparse normalizes output
~~~~~

### 下一步建议
运行测试确认修复后，继续执行 **Atomic Task 3**（Adapter 层处理 Alias SURI）和 **Atomic Task 4**（Local Resolution）。
