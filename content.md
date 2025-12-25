好的，第一阶段完成。我们现在无缝进入第二阶段。

我们已经让 `stitcher` *知道* 了插件的存在，现在需要让它 *理解* 这些插件。这一步的核心任务是在 `stitcher-scanner` 包中创建一个动态内省器 (Dynamic Inspector)，它能够加载插件代码并将其转换为我们统一的 `FunctionDef` 中间表示（IR）。

我们将继续遵循 TDD 的原则。

## [WIP] feat(scanner): Implement dynamic plugin inspector

### 用户需求
需要一个新模块，能够接收一个插件的入口点字符串（例如 `"my_pkg.main:my_func"`），动态地导入该函数，使用 `inspect` 模块分析其签名和文档字符串，并将其转换为一个 `stitcher.spec.FunctionDef` IR 对象。

### 评论
这是解耦架构价值的体现。通过引入一个独立的“内省器”，我们将静态代码分析（AST）和动态代码分析（`inspect`）这两种不同的源码解析策略隔离开来。然而，它们的产出是完全相同的——统一的中间表示（IR）。这使得上游的应用层（`stitcher-application`）可以透明地处理来自文件和插件的代码定义，极大地简化了系统的复杂性。

### 目标
1.  在 `stitcher-scanner` 包中，创建一个新的测试文件 `tests/test_inspector.py` 来驱动开发。
2.  在 `scanner` 模块中，创建一个新的 `inspector.py` 文件。
3.  在 `inspector.py` 中，实现核心函数 `parse_plugin_entry`，它将负责导入、内省和转换的全过程。
4.  确保新函数被正确导出，以便应用层可以调用。

### 基本原理
我们将创建一个测试用的 fixture，它会在一个临时目录中动态创建一个可导入的 Python 模块。测试用例会把这个临时模块的入口点字符串传递给 `parse_plugin_entry` 函数，然后断言返回的 `FunctionDef` 对象的每一个字段（名称、参数、类型、文档等）都与预期完全一致。这个测试通过后，我们就可以确信内省器能够正确地将 `inspect` 模块返回的运行时对象，精确地映射到我们的静态 IR 数据模型上。

### 标签
#intent/build #flow/ready #priority/high #comp/scanner #concept/parser #scope/core #ai/instruct #task/domain/plugins #task/object/introspection-engine #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Inspector 的测试用例

我们首先在 `stitcher-scanner` 中创建测试文件。这个测试包含一个 fixture，用于创建一个临时的、可导入的 Python 模块，这是进行动态导入测试的关键。

~~~~~act
write_file
packages/stitcher-scanner/tests/test_inspector.py
~~~~~
~~~~~python
import sys
import pytest
from pathlib import Path
from textwrap import dedent
from stitcher.spec import ArgumentKind, FunctionDef
from stitcher.scanner.inspector import parse_plugin_entry

@pytest.fixture
def temp_module(tmp_path: Path):
    """Creates a temporary, importable module for testing."""
    module_content = dedent("""
    from typing import Optional

    def sample_plugin_func(
        name: str,
        count: int = 1,
        *,
        is_admin: bool,
        meta: Optional[dict] = None
    ) -> str:
        \"\"\"This is a sample plugin function.
        
        It has multiple lines.
        \"\"\"
        return f"Hello {name}, {count}, {is_admin}"
    """)
    
    pkg_dir = tmp_path / "temp_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "main.py").write_text(module_content, encoding="utf-8")
    
    # Add to path to make it importable
    sys.path.insert(0, str(tmp_path))
    yield "temp_pkg.main:sample_plugin_func"
    # Teardown: remove from path
    sys.path.pop(0)


def test_parse_plugin_entry_point(temp_module: str):
    """
    Test parsing a live, imported function via its entry point string
    into our FunctionDef IR.
    """
    # Act
    func_def = parse_plugin_entry("sample.plugin", temp_module)

    # Assert
    assert isinstance(func_def, FunctionDef)
    assert func_def.name == "sample.plugin" # Should use the name from the entry point key
    assert func_def.docstring and "This is a sample plugin function" in func_def.docstring
    assert func_def.return_annotation == "str"
    assert not func_def.is_async

    # Assert arguments
    args = {arg.name: arg for arg in func_def.args}
    assert len(args) == 4

    assert args["name"].kind == ArgumentKind.POSITIONAL_OR_KEYWORD
    assert args["name"].annotation == "str"
    assert args["name"].default is None

    assert args["count"].kind == ArgumentKind.POSITIONAL_OR_KEYWORD
    assert args["count"].annotation == "int"
    assert args["count"].default == "1" # Defaults are string representations

    assert args["is_admin"].kind == ArgumentKind.KEYWORD_ONLY
    assert args["is_admin"].annotation == "bool"
    assert args["is_admin"].default is None

    assert args["meta"].kind == ArgumentKind.KEYWORD_ONLY
    assert args["meta"].annotation == "Optional[dict]"
    assert args["meta"].default == "None"
~~~~~

#### Acts 2: 实现动态内省器

现在，我们创建 `inspector.py` 模块并填充其逻辑，目标是让上面的测试通过。

~~~~~act
write_file
packages/stitcher-scanner/src/stitcher/scanner/inspector.py
~~~~~
~~~~~python
import inspect
import importlib
from typing import Callable, Any
from stitcher.spec import Argument, ArgumentKind, FunctionDef

class InspectionError(Exception):
    """Custom exception for errors during plugin inspection."""
    pass

def _map_param_kind(kind: inspect._ParameterKind) -> ArgumentKind:
    """Maps inspect's ParameterKind enum to our own."""
    if kind == inspect.Parameter.POSITIONAL_ONLY:
        return ArgumentKind.POSITIONAL_ONLY
    if kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
        return ArgumentKind.POSITIONAL_OR_KEYWORD
    if kind == inspect.Parameter.VAR_POSITIONAL:
        return ArgumentKind.VAR_POSITIONAL
    if kind == inspect.Parameter.KEYWORD_ONLY:
        return ArgumentKind.KEYWORD_ONLY
    if kind == inspect.Parameter.VAR_KEYWORD:
        return ArgumentKind.VAR_KEYWORD
    raise ValueError(f"Unknown parameter kind: {kind}")

def _get_annotation_str(annotation: Any) -> str:
    """Gets a string representation of a type annotation."""
    if annotation == inspect.Parameter.empty:
        return ""
    
    # Handle generic types from typing module
    if hasattr(annotation, "__origin__"):
        return str(annotation).replace("typing.", "")
    
    if hasattr(annotation, "__name__"):
        return annotation.__name__
        
    return str(annotation)


def parse_plugin_entry(name: str, entry_point_str: str) -> FunctionDef:
    """
    Dynamically imports and inspects a callable from an entry point string
    and converts it into a Stitcher FunctionDef IR object.

    Args:
        name: The logical name of the plugin (from the entry point key).
        entry_point_str: The import string (e.g., "my_pkg.main:my_func").

    Returns:
        A FunctionDef instance representing the inspected callable.
    
    Raises:
        InspectionError: If the entry point cannot be loaded or inspected.
    """
    try:
        module_str, callable_str = entry_point_str.split(":", 1)
        module = importlib.import_module(module_str)
        target_callable: Callable = getattr(module, callable_str)
    except (ImportError, AttributeError, ValueError) as e:
        raise InspectionError(
            f"Could not load entry point '{entry_point_str}': {e}"
        ) from e

    try:
        signature = inspect.signature(target_callable)
        docstring = inspect.getdoc(target_callable)
    except (TypeError, ValueError) as e:
         raise InspectionError(
            f"Could not inspect signature of '{entry_point_str}': {e}"
        ) from e
        
    # Build arguments
    args: list[Argument] = []
    for param in signature.parameters.values():
        default_val = None
        if param.default != inspect.Parameter.empty:
            default_val = repr(param.default)

        args.append(Argument(
            name=param.name,
            kind=_map_param_kind(param.kind),
            annotation=_get_annotation_str(param.annotation) or None,
            default=default_val
        ))

    # Build FunctionDef
    return_annotation = _get_annotation_str(signature.return_annotation)

    return FunctionDef(
        name=name,
        args=args,
        docstring=docstring,
        return_annotation=return_annotation or None,
        is_async=inspect.iscoroutinefunction(target_callable)
    )
~~~~~

#### Acts 3: 在 `__init__.py` 中导出新函数

最后，我们更新 `stitcher-scanner` 的 `__init__.py` 文件，导出 `parse_plugin_entry`，使其可以被 `stitcher-application` 调用。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .parser import parse_source_code

__all__ = ["parse_source_code"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .parser import parse_source_code
from .inspector import parse_plugin_entry, InspectionError

__all__ = ["parse_source_code", "parse_plugin_entry", "InspectionError"]
~~~~~

### 下一步建议
测试通过后，我们的 `scanner` 层就具备了处理动态插件的能力。

下一步将是 **阶段 3: 在 `stitcher-application` 中编排新流程**。我们需要修改 `StitcherApp`，让它使用 `stitcher-config` 发现插件，然后调用我们刚刚创建的 `parse_plugin_entry` 来解析它们，并将结果（`FunctionDef` IRs）整合成一个可以被 `stitcher-io` 消费的虚拟模块树。
