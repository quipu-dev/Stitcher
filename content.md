我分析了你提供的 16 个静态分析错误，这些错误分布在多个包中，涵盖了类型不兼容、属性访问错误和模块解析失败等问题。我将生成一个计划来逐一修复它们。

## [WIP] fix: 修复静态分析报告的 16 个类型错误

### 用户需求

修复 `pyright` 报告的所有静态分析错误，确保类型系统的健全性，并解决模块导入问题。

### 评论

这是一次重要的健全性修复。修复这些类型错误可以提高代码的健壮性，防止运行时出现意外的 `AttributeError`，并使代码库对开发者更加友好。创建缺失的 `__init__.py` 文件是解决 `stitcher-lang-sidecar` 包中模块解析问题的关键。

### 目标

1.  **`stitcher-index`**: 修正测试中 `MockAdapter` 的方法签名，使其与 `LanguageAdapter` 协议匹配。
2.  **`stitcher-lang-python`**: 在测试代码中添加类型守卫（`isinstance` 检查），以向类型检查器证明 `DocstringSection.content` 是一个列表而非字符串。
3.  **`stitcher-lang-sidecar`**:
    *   通过创建必要的 `__init__.py` 文件来正确建立 `stitcher.lang.sidecar` 命名空间包，解决模块导入失败的问题。
    *   重构 `parser.py` 以安全地访问 `ruamel.yaml` 的 `lc` 属性，避免类型错误。
4.  **`stitcher-refactor`**:
    *   更新 `rename_namespace.py` 以使用 `SemanticGraph` 正确的 `find_usages` 方法。
    *   修正测试夹具 `mock_context` 的返回类型注解，以准确反映其 `Mock` 对象的本质。

### 基本原理

我将采用一系列精确的 `patch_file` 操作来修正现有代码中的类型错误和方法调用错误。对于 `stitcher-lang-sidecar` 包中的模块解析问题，根本原因在于其目录没有被正确识别为 Python 包。我将通过 `write_file` 创建符合 monorepo 规范的 `__init__.py` 文件来解决这个问题，使其成为一个命名空间包。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/cli #concept/parser #scope/dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `stitcher-index` 中的测试 Mock 适配器

我们将修正 `MockAdapter` 的 `parse` 方法签名，将参数 `path` 重命名为 `file_path`，以匹配 `LanguageAdapter` 协议，解决类型不兼容问题。

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
class MockAdapter:
    def parse(self, path, content):
        logical = path.stem
        sym = SymbolRecord(
            id=f"py://{path.name}#Main",
            name="Main",
            kind="class",
            lineno=1,
            col_offset=0,
            end_lineno=1,
            end_col_offset=10,
            logical_path=logical,
        )
        return [sym], []
~~~~~
~~~~~python.new
from pathlib import Path


class MockAdapter:
    def parse(self, file_path: Path, content: str):
        logical = file_path.stem
        sym = SymbolRecord(
            id=f"py://{file_path.name}#Main",
            name="Main",
            kind="class",
            lineno=1,
            col_offset=0,
            end_lineno=1,
            end_col_offset=10,
            logical_path=logical,
        )
        return [sym], []
~~~~~

#### Acts 2: 修复 `stitcher-lang-python` 中的 docstring 解析器测试

通过添加 `isinstance(..., list)` 类型守卫，我们向类型检查器明确指出 `section.content` 在此上下文中是一个列表，从而安全地访问其元素属性。

~~~~~act
patch_file
packages/stitcher-lang-python/tests/adapter/unit/docstring/test_parsers.py
~~~~~
~~~~~python.old
        args_section = next(s for s in ir.sections if s.kind == "parameters")
        # Griffe parses standard headers into kind, leaving title as None
        assert args_section.title is None
        assert len(args_section.content) == 2
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."

        returns_section = next(s for s in ir.sections if s.kind == "returns")
        assert len(returns_section.content) == 1
        assert returns_section.content[0].annotation == "bool"
        assert returns_section.content[0].description == "True if success."
~~~~~
~~~~~python.new
        args_section = next(s for s in ir.sections if s.kind == "parameters")
        # Griffe parses standard headers into kind, leaving title as None
        assert args_section.title is None
        assert isinstance(args_section.content, list)
        assert len(args_section.content) == 2
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."

        returns_section = next(s for s in ir.sections if s.kind == "returns")
        assert isinstance(returns_section.content, list)
        assert len(returns_section.content) == 1
        assert returns_section.content[0].annotation == "bool"
        assert returns_section.content[0].description == "True if success."
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/tests/adapter/unit/docstring/test_parsers.py
~~~~~
~~~~~python.old
        args_section = next(s for s in ir.sections if s.kind == "parameters")
        # Griffe parses standard headers into kind, leaving title as None
        assert args_section.title is None
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."
~~~~~
~~~~~python.new
        args_section = next(s for s in ir.sections if s.kind == "parameters")
        # Griffe parses standard headers into kind, leaving title as None
        assert args_section.title is None
        assert isinstance(args_section.content, list)
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."
~~~~~

#### Acts 3: 修复 `stitcher-lang-sidecar` 包结构和代码

首先，我们将创建 `__init__.py` 文件，将 `stitcher-lang-sidecar` 的目录结构定义为命名空间包，以解决模块导入错误。

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

接下来，我们将修改 `parser.py` 以安全地访问 `ruamel.yaml` 的特殊属性，避免类型检查器报错。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/parser.py
~~~~~
~~~~~python.old
        if hasattr(data, "lc") and hasattr(data.lc, "item"):
            # lc.item(key) returns [line, col, pre_key_comment_line, key_comment_line]
            # line is 0-based.
            pos = data.lc.item(key)
            if pos:
                lineno = pos[0] + 1  # Convert to 1-based
                col_offset = pos[1]
                references.append((str(key), lineno, col_offset))
        else:
            # Fallback if no line info (shouldn't happen with round-trip loader)
            pass
~~~~~
~~~~~python.new
        lc = getattr(data, "lc", None)
        if lc and hasattr(lc, "item"):
            # lc.item(key) returns [line, col, pre_key_comment_line, key_comment_line]
            # line is 0-based.
            pos = lc.item(key)
            if pos:
                lineno = pos[0] + 1  # Convert to 1-based
                col_offset = pos[1]
                references.append((str(key), lineno, col_offset))
        else:
            # Fallback if no line info (shouldn't happen with round-trip loader)
            pass
~~~~~

#### Acts 4: 修复 `stitcher-refactor` 中的代码和测试

我们将修正 `rename_namespace.py` 中对 `SemanticGraph` 的错误方法调用。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_namespace.py
~~~~~
~~~~~python.old
        usages = ctx.graph.registry.get_usages(self.old_prefix)
~~~~~
~~~~~python.new
        usages = ctx.graph.find_usages(self.old_prefix)
~~~~~

最后，我们将更新 `test_planner_merging.py` 中的夹具返回类型提示，以正确反映其 Mock 本质。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python.old
@pytest.fixture
def mock_context(tmp_path: Path) -> RefactorContext:
    """Creates a mock RefactorContext with a mock graph."""
~~~~~
~~~~~python.new
@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Creates a mock RefactorContext with a mock graph."""
~~~~~

### 下一步建议

所有已报告的静态分析错误都已在此计划中修复。在应用这些变更后，建议重新运行 `pyright` 以确认所有问题均已解决。接下来，可以继续处理项目积压任务中的其他功能开发或重构工作。
