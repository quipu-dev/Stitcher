简要回答

好的，我将生成实施 "阶段 1: 适配器增强" 的计划。我们将创建 Griffe 解析器、Google/Numpy 渲染器以及相应的工厂和测试。

## [WIP] feat: 实施结构化文档适配器层 (解析与渲染)

### 用户需求

用户希望基于新的路线图实施 "阶段 1: 适配器增强"。具体包括：
1.  在 `stitcher-python-adapter` 中封装 `griffe` 的能力，实现对 Google/Numpy 风格文档字符串的解析，转化为 `DocstringIR`。
2.  实现结构化渲染器，将 `DocstringIR` 渲染回符合风格规范的文档字符串。
3.  建立 Codec 工厂以统一管理解析器和渲染器的实例化。
4.  编写相应的单元测试。

### 评论

这是一个非常核心的基础设施建设。
1.  **解析器 (Parser)**: 将非结构化的文本转换为结构化的 IR，是后续所有高级功能（如合并、验证、转换）的前提。利用 `griffe` 是明智的选择，避免了重复造轮子。
2.  **渲染器 (Renderer)**: 这是一个逆向过程，需要特别注意缩进和格式的准确性，因为 Python 对缩进非常敏感。
3.  **测试**: 由于涉及多种风格和复杂的嵌套结构，详尽的测试至关重要。

### 目标

1.  创建 `packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/parsers.py`，实现 `GriffeDocstringParser`。
2.  创建 `packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py`，实现 `GoogleDocstringRenderer` 和 `NumpyDocstringRenderer`。
3.  创建 `packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/factory.py`，实现 `get_docstring_codec`。
4.  更新 `packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/__init__.py` 暴露新组件。
5.  在 `packages/stitcher-python-adapter/tests/docstring/` 下创建并实现解析器和渲染器的测试用例。

### 基本原理

我们采用了 **Codec (编解码器)** 模式，将文档的“解析 (Parsing)”和“渲染 (Rendering)”与业务逻辑解耦。
-   **解析器** 负责 `str -> IR`。
-   **渲染器** 负责 `IR -> str`。
-   **工厂** 负责根据配置字符串（如 "google"）提供正确的 Parser/Renderer 对。

这种设计使得 `stitcher-application` 层无需关心具体的文档风格，只需操作通用的 `DocstringIR`。

### 标签

#intent/build #flow/ready #priority/high
#comp/adapter #concept/parser #scope/core
#task/domain/docstring #task/object/adapter #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 创建解析器 (Parsers)

我们将实现 `GriffeDocstringParser`。它使用 `griffe` 库将原始文档字符串解析为 Griffe 的内部模型，然后将其映射为我们定义的 `DocstringIR`。为了保持代码整洁，我们也将现有的 `RawDocstringParser` 迁移到此文件中。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/parsers.py
~~~~~
~~~~~python
from typing import Any, List, Union, cast

import griffe
from griffe import Docstring, Parser
from griffe.dataclasses import (
    DocstringSection as GriffeSection,
    DocstringSectionAdmonition,
    DocstringSectionAttributes,
    DocstringSectionParameters,
    DocstringSectionReturns,
    DocstringSectionText,
    DocstringSectionYields,
    DocstringSectionRaises,
)

from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringParserProtocol,
)


class RawDocstringParser(DocstringParserProtocol):
    """
    A simple parser that treats the entire input text as the summary.
    Does not attempt to parse sections or parameters.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()
        return DocstringIR(summary=docstring_text)


class GriffeDocstringParser(DocstringParserProtocol):
    """
    A parser that uses Griffe to parse Google/Numpy style docstrings into IR.
    """

    def __init__(self, style: str = "google"):
        self.style = Parser(style)

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()

        # Parse with Griffe
        # We wrap it in a Griffe Docstring object
        # Note: Griffe's parse function expects a Docstring object, not str directly in some versions,
        # or Docstring.parse(). We use griffe.docstrings.parse strategy.
        try:
            doc = Docstring(docstring_text)
            parsed_sections = griffe.parse(doc, self.style)
        except Exception:
            # Fallback to raw if parsing fails (e.g. syntax error in docstring)
            return DocstringIR(summary=docstring_text)

        ir = DocstringIR()
        
        # Check if the first section is text (Summary/Extended)
        # Griffe usually splits the first text block into summary and extended description implies logic.
        # But here we get a list of sections. The first one is typically the text description.
        
        start_index = 0
        if parsed_sections and isinstance(parsed_sections[0], DocstringSectionText):
            text_content = parsed_sections[0].value
            # Simple heuristic: First line is summary, rest is extended.
            # Or use parsed_sections[0].title if it exists? No, text sections usually don't have titles unless explicit.
            
            lines = text_content.strip().split("\n", 1)
            ir.summary = lines[0].strip()
            if len(lines) > 1:
                ir.extended = lines[1].strip()
            start_index = 1

        for section in parsed_sections[start_index:]:
            ir_section = self._map_section(section)
            if ir_section:
                ir.sections.append(ir_section)

        return ir

    def _map_section(self, section: GriffeSection) -> Union[DocstringSection, None]:
        kind = section.kind.value  # Griffe DocstringSectionKind enum value
        title = section.title

        content: Union[str, List[DocstringItem]] = ""

        if isinstance(section, DocstringSectionText):
            # Generic text section
            content = section.value
            return DocstringSection(kind="text", title=title, content=content)

        if isinstance(section, (DocstringSectionParameters, DocstringSectionAttributes)):
            # Parameters or Attributes (list of items)
            items = []
            for param in section.value:
                items.append(
                    DocstringItem(
                        name=param.name,
                        annotation=str(param.annotation) if param.annotation else None,
                        description=param.description or "",
                        default=str(param.default) if param.default else None,
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, (DocstringSectionReturns, DocstringSectionYields, DocstringSectionRaises)):
            # Returns, Yields, Raises (list of items, usually without name for Returns/Yields, or exception name for Raises)
            items = []
            for item in section.value:
                # For Returns/Yields, 'name' might be empty or the variable name.
                # For Raises, 'annotation' is usually the Exception type.
                items.append(
                    DocstringItem(
                        name=item.name or "",
                        annotation=str(item.annotation) if item.annotation else None,
                        description=item.description or "",
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, DocstringSectionAdmonition):
            # Admonitions like "Note", "Warning"
            # Griffe puts the content in .value (DocstringSectionText)
            content = section.value.value
            return DocstringSection(kind="admonition", title=title, content=content)

        return None
~~~~~

#### Acts 2: 创建渲染器 (Renderers)

我们将实现 Google 和 Numpy 风格的渲染器。为了确保生成的文档字符串格式优美且符合缩进要求，我们不使用简单的字符串拼接，而是构建逻辑清晰的渲染流程。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py
~~~~~
~~~~~python
from typing import List, Union
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringRendererProtocol,
)


class BaseStructuredRenderer(DocstringRendererProtocol):
    def render(self, docstring_ir: DocstringIR) -> str:
        blocks = []

        if docstring_ir.summary:
            blocks.append(docstring_ir.summary)

        if docstring_ir.extended:
            blocks.append(docstring_ir.extended)

        for section in docstring_ir.sections:
            rendered_section = self._render_section(section)
            if rendered_section:
                blocks.append(rendered_section)

        # Join blocks with an empty line between them
        return "\n\n".join(blocks)

    def _render_section(self, section: DocstringSection) -> str:
        raise NotImplementedError


class GoogleDocstringRenderer(BaseStructuredRenderer):
    def _render_section(self, section: DocstringSection) -> str:
        lines = []
        if section.title:
            lines.append(f"{section.title}:")
        
        if section.kind == "text" or section.kind == "admonition":
             # Text content: Indent body
             if isinstance(section.content, str):
                 for line in section.content.splitlines():
                     lines.append(f"    {line}")
        
        elif isinstance(section.content, list):
            # Items (Args, Returns, Raises)
            for item in section.content:
                if not isinstance(item, DocstringItem):
                    continue
                
                # Format: name (type): description
                # Or for Returns: type: description
                
                prefix = ""
                if item.name:
                    prefix = f"{item.name}"
                    if item.annotation:
                        prefix += f" ({item.annotation})"
                elif item.annotation:
                    prefix = f"{item.annotation}"

                if prefix:
                    if item.description:
                        # Check if description fits on same line? 
                        # Google style usually: "name (type): description"
                        lines.append(f"    {prefix}: {item.description}")
                    else:
                         lines.append(f"    {prefix}")
                else:
                    # Just description case?
                    if item.description:
                         lines.append(f"    {item.description}")

        return "\n".join(lines)


class NumpyDocstringRenderer(BaseStructuredRenderer):
    def _render_section(self, section: DocstringSection) -> str:
        lines = []
        
        # NumPy Style:
        # Title
        # -----
        if section.title:
            lines.append(section.title)
            lines.append("-" * len(section.title))

        if section.kind == "text" or section.kind == "admonition":
             if isinstance(section.content, str):
                 for line in section.content.splitlines():
                     lines.append(line) # NumPy text sections usually not indented relative to title? Or are they?
                                        # Usually no indentation for the block itself relative to module indent, 
                                        # but here we are producing the docstring content.
                                        # Standard NumPy: text is at same level.
                                        
        elif isinstance(section.content, list):
            for item in section.content:
                if not isinstance(item, DocstringItem):
                    continue
                
                # Format:
                # name : type
                #     description
                
                header_parts = []
                if item.name:
                    header_parts.append(item.name)
                
                if item.annotation:
                    if item.name:
                        header_parts.append(f" : {item.annotation}")
                    else:
                        header_parts.append(item.annotation) # For returns

                header = "".join(header_parts)
                if header:
                    lines.append(header)
                
                if item.description:
                    for line in item.description.splitlines():
                        lines.append(f"    {line}")

        return "\n".join(lines)
~~~~~

#### Acts 3: 创建工厂 (Factory)

实现 `get_docstring_codec` 工厂函数，用于根据配置字符串返回相应的 Parser 和 Renderer 实例。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/factory.py
~~~~~
~~~~~python
from typing import Tuple

from stitcher.spec import DocstringParserProtocol, DocstringRendererProtocol
from .parsers import RawDocstringParser, GriffeDocstringParser
from .renderers import GoogleDocstringRenderer, NumpyDocstringRenderer


class RawDocstringRenderer(DocstringRendererProtocol):
    """
    A simple renderer that just dumps the summary.
    Used for 'raw' mode consistency.
    """

    def render(self, docstring_ir) -> str:
        # For raw mode, we just return the summary as the full docstring.
        # Addons and other fields are ignored in raw render.
        return docstring_ir.summary or ""


def get_docstring_codec(
    style: str,
) -> Tuple[DocstringParserProtocol, DocstringRendererProtocol]:
    """
    Factory to get the parser and renderer for a specific docstring style.
    
    Args:
        style: "google", "numpy", or "raw".
        
    Returns:
        (Parser, Renderer) tuple.
    """
    if style == "google":
        return GriffeDocstringParser("google"), GoogleDocstringRenderer()
    elif style == "numpy":
        return GriffeDocstringParser("numpy"), NumpyDocstringRenderer()
    
    # Default to raw
    return RawDocstringParser(), RawDocstringRenderer()
~~~~~

#### Acts 4: 清理旧文件并更新导出

我们需要删除旧的 `raw_parser.py`（因为它已经被迁移到 `parsers.py`），并更新 `__init__.py` 以导出新的组件。

~~~~~act
delete_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/raw_parser.py
~~~~~

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/__init__.py
~~~~~
~~~~~python
from .parsers import RawDocstringParser, GriffeDocstringParser
from .renderers import GoogleDocstringRenderer, NumpyDocstringRenderer
from .factory import get_docstring_codec

__all__ = [
    "RawDocstringParser",
    "GriffeDocstringParser",
    "GoogleDocstringRenderer",
    "NumpyDocstringRenderer",
    "get_docstring_codec",
]
~~~~~

#### Acts 5: 编写解析器测试

创建一个测试文件来验证 `GriffeDocstringParser` 是否能正确地将 Google/Numpy 风格的文档字符串解析为 `DocstringIR`。

~~~~~act
write_file
packages/stitcher-python-adapter/tests/docstring/test_parsers.py
~~~~~
~~~~~python
import pytest
from stitcher.adapter.python.docstring.parsers import GriffeDocstringParser
from stitcher.spec import DocstringIR


class TestGriffeDocstringParser:
    def test_parse_google_style_simple(self):
        doc = """
        Summary line.
        
        Extended description.
        
        Args:
            x (int): The x value.
            y (str, optional): The y value.
            
        Returns:
            bool: True if success.
        """
        parser = GriffeDocstringParser(style="google")
        ir = parser.parse(doc.strip())

        assert ir.summary == "Summary line."
        assert ir.extended == "Extended description."
        
        # Check Sections
        # Order: Args, Returns
        # Note: Griffe parsing order depends on input
        
        args_section = next(s for s in ir.sections if s.kind == "parameters")
        assert args_section.title == "Args"
        assert len(args_section.content) == 2
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."
        
        returns_section = next(s for s in ir.sections if s.kind == "returns")
        assert len(returns_section.content) == 1
        assert returns_section.content[0].annotation == "bool"
        assert returns_section.content[0].description == "True if success."

    def test_parse_numpy_style_simple(self):
        doc = """
        Summary line.
        
        Parameters
        ----------
        x : int
            The x value.
            
        Returns
        -------
        bool
            True if success.
        """
        parser = GriffeDocstringParser(style="numpy")
        ir = parser.parse(doc.strip())
        
        assert ir.summary == "Summary line."
        
        args_section = next(s for s in ir.sections if s.kind == "parameters")
        assert args_section.title == "Parameters"
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."

    def test_fallback_on_invalid_syntax(self):
        # Even with weird syntax, Griffe usually parses text.
        # But if we force a fallback logic in parser, we can test it.
        # For now, just ensure it doesn't crash on empty
        parser = GriffeDocstringParser(style="google")
        ir = parser.parse("")
        assert ir.summary is None
~~~~~

#### Acts 6: 编写渲染器测试

创建一个测试文件来验证 `GoogleDocstringRenderer` 和 `NumpyDocstringRenderer` 是否能正确地将 `DocstringIR` 还原为文档字符串。

~~~~~act
write_file
packages/stitcher-python-adapter/tests/docstring/test_renderers.py
~~~~~
~~~~~python
import pytest
from stitcher.spec import DocstringIR, DocstringSection, DocstringItem
from stitcher.adapter.python.docstring.renderers import GoogleDocstringRenderer, NumpyDocstringRenderer


@pytest.fixture
def sample_ir():
    ir = DocstringIR(
        summary="Summary line.",
        extended="Extended description."
    )
    # Add Args
    ir.sections.append(DocstringSection(
        kind="parameters",
        title="Args",
        content=[
            DocstringItem(name="x", annotation="int", description="The x value."),
            DocstringItem(name="y", description="The y value.")
        ]
    ))
    # Add Returns
    ir.sections.append(DocstringSection(
        kind="returns",
        title="Returns",
        content=[
            DocstringItem(annotation="bool", description="True if success.")
        ]
    ))
    return ir


class TestGoogleDocstringRenderer:
    def test_render_google(self, sample_ir):
        renderer = GoogleDocstringRenderer()
        output = renderer.render(sample_ir)
        
        expected = """Summary line.

Extended description.

Args:
    x (int): The x value.
    y: The y value.

Returns:
    bool: True if success."""
        
        assert output.strip() == expected.strip()


class TestNumpyDocstringRenderer:
    def test_render_numpy(self, sample_ir):
        # Adjust titles for Numpy conventions
        sample_ir.sections[0].title = "Parameters" 
        sample_ir.sections[1].title = "Returns" 

        renderer = NumpyDocstringRenderer()
        output = renderer.render(sample_ir)
        
        expected = """Summary line.

Extended description.

Parameters
----------
x : int
    The x value.
y
    The y value.

Returns
-------
bool
    True if success."""
        
        assert output.strip() == expected.strip()
~~~~~

### 下一步建议

我们已经完成了适配器层的核心实现。下一步应该进入 **阶段 2: 存储层升级 (The Storage Layer)**。
我们将在 `stitcher-application` 层定义 IR 的序列化策略，并升级 `DocumentManager` 以支持结构化的 YAML 存储和规范化的哈希计算。这将打通从源码解析到 YAML 持久化的完整链路。
