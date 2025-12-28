让我们仔细分析当前的测试覆盖率报告，特别是那些我们刚刚进行了重大修改的模块。

1.  **`stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py` (49% 覆盖率)**
    *   **问题**: 这是一个核心组件，但覆盖率严重不足（49%）。特别是 `_generate_args` (行 94-139) 和 `_generate_class` (行 163-204) 等复杂逻辑分支可能未被充分测试。虽然 `StubGenerator` 是从 `stitcher-io` 迁移过来的，但我们必须确保在新架构下它仍然健壮。
    *   **原因**: 之前的测试可能主要集中在集成层面（通过 `run_generate`），而缺乏对生成器各种边缘情况（如复杂参数、装饰器、嵌套类）的细粒度单元测试。

2.  **`stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py` (72% 覆盖率)**
    *   **问题**: 解析器也有不少未覆盖的代码，特别是对于一些不常见的 AST 节点处理（如 `AnnAssign` 的某些情况，行的 51-70）。
    *   **原因**: 同样，集成测试可能没有覆盖所有语法特性。

3.  **`stitcher-python-adapter/src/stitcher/adapter/python/inspector.py` (53% 覆盖率)**
    *   **问题**: 插件检查器的覆盖率也很低。特别是异常处理路径（行 44-45, 52-53, 60-64）。
    *   **原因**: 我们可能缺乏测试插件加载失败或签名不兼容的测试用例。

4.  **`stitcher-python-adapter/src/stitcher/adapter/python/fingerprint.py` (93% 覆盖率)**
    *   **状态**: 覆盖率良好。我们之前修复的 `test_fingerprint_stability` 有效地覆盖了这部分。

尽管整体覆盖率（82%）尚可，但 `stub_generator.py` 的低覆盖率是一个明显的风险点，因为它直接决定了生成的 `.pyi` 文件的正确性。`inspector.py` 的低覆盖率则影响了插件系统的健壮性。

**决定**: 是的，我们需要创建新的单元测试，专门针对 `stitcher-python-adapter` 及其内部组件。由于 Adapter 现在是一个独立的包，它应该有自己的一套单元测试，而不是仅仅依赖 `stitcher-application` 的集成测试。

## [WIP] test: 为 stitcher-python-adapter 补充单元测试

### 用户需求
提高 `stitcher-python-adapter` 核心组件（StubGenerator, Inspector, Parser）的测试覆盖率，特别是针对边缘情况和错误处理路径。

### 评论
架构重构将这些组件隔离了出来，这使得为它们编写纯粹的单元测试变得非常容易。这是一个提高代码质量和信心的绝佳机会。我们将填补 `StubGenerator` 和 `Inspector` 的测试空白。

### 目标
1.  创建 `packages/stitcher-python-adapter/tests/unit/test_stub_generator.py`，覆盖复杂参数签名、装饰器、类继承等场景。
2.  创建 `packages/stitcher-python-adapter/tests/unit/test_inspector.py`，覆盖插件加载失败、签名解析错误等异常路径。
3.  创建 `packages/stitcher-python-adapter/tests/unit/test_parser.py`，覆盖特定的 AST 解析场景（如 `AnnAssign`）。

### 基本原理
每个包都应该对自己的逻辑负责。Adapter 层不仅仅是传递调用，它包含了解析、生成和转换的复杂逻辑，必须有独立的测试套件来保证其行为符合协议契约。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #comp/runtime #scope/core #ai/instruct #task/domain/testing #task/object/adapter-tests #task/action/increase-coverage #task/state/end

---

### Script

#### Acts 1: 创建 StubGenerator 单元测试
重点覆盖参数生成的复杂情况（*args, **kwargs, defaults, annotations）。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-python-adapter/tests/unit
~~~~~

~~~~~act
write_file
packages/stitcher-python-adapter/tests/unit/test_stub_generator.py
~~~~~
~~~~~python
import pytest
from stitcher.spec import (
    ModuleDef, FunctionDef, ClassDef, Argument, ArgumentKind, Attribute
)
from stitcher.adapter.python.internal.stub_generator import StubGenerator


class TestStubGenerator:
    @pytest.fixture
    def generator(self):
        return StubGenerator()

    def test_generate_complex_args(self, generator):
        # def func(a: int, b: str = "default", *args, kw_only: bool, **kwargs) -> None:
        func = FunctionDef(
            name="complex_func",
            args=[
                Argument(name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int"),
                Argument(name="b", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="str", default='"default"'),
                Argument(name="args", kind=ArgumentKind.VAR_POSITIONAL),
                Argument(name="kw_only", kind=ArgumentKind.KEYWORD_ONLY, annotation="bool"),
                Argument(name="kwargs", kind=ArgumentKind.VAR_KEYWORD),
            ],
            return_annotation="None"
        )
        module = ModuleDef(file_path="test.py", functions=[func])
        
        output = generator.generate(module)
        
        expected_sig = 'def complex_func(a: int, b: str = "default", *args, kw_only: bool, **kwargs) -> None: ...'
        assert expected_sig in output

    def test_generate_positional_only_args(self, generator):
        # def func(a, /, b):
        func = FunctionDef(
            name="pos_only",
            args=[
                Argument(name="a", kind=ArgumentKind.POSITIONAL_ONLY),
                Argument(name="b", kind=ArgumentKind.POSITIONAL_OR_KEYWORD),
            ],
            return_annotation="None"
        )
        module = ModuleDef(file_path="test.py", functions=[func])
        
        output = generator.generate(module)
        assert 'def pos_only(a, /, b) -> None: ...' in output

    def test_generate_bare_star(self, generator):
        # def func(*, a):
        func = FunctionDef(
            name="bare_star",
            args=[
                Argument(name="a", kind=ArgumentKind.KEYWORD_ONLY),
            ],
            return_annotation="None"
        )
        module = ModuleDef(file_path="test.py", functions=[func])
        
        output = generator.generate(module)
        assert 'def bare_star(*, a) -> None: ...' in output

    def test_generate_class_with_decorators_and_bases(self, generator):
        # @decorator
        # class MyClass(Base1, Base2):
        cls = ClassDef(
            name="MyClass",
            bases=["Base1", "Base2"],
            decorators=["decorator"],
            attributes=[
                Attribute(name="x", annotation="int", value="1")
            ],
            methods=[
                FunctionDef(name="method", args=[Argument(name="self", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)])
            ]
        )
        module = ModuleDef(file_path="test.py", classes=[cls])
        
        output = generator.generate(module)
        
        assert "@decorator" in output
        assert "class MyClass(Base1, Base2):" in output
        assert "    x: int = 1" in output
        assert "    def method(self): ..." in output
~~~~~

#### Acts 2: 创建 Inspector 单元测试
覆盖异常路径。

~~~~~act
write_file
packages/stitcher-python-adapter/tests/unit/test_inspector.py
~~~~~
~~~~~python
import pytest
from stitcher.adapter.python.inspector import parse_plugin_entry, InspectionError

# Mock module for testing
import sys
from types import ModuleType

def setup_mock_module(monkeypatch):
    mock_mod = ModuleType("my_plugin")
    
    def valid_func(a: int) -> str:
        """My Docstring"""
        return str(a)
    
    async def async_func():
        pass

    mock_mod.valid_func = valid_func
    mock_mod.async_func = async_func
    mock_mod.not_callable = "I am a string"
    
    monkeypatch.setitem(sys.modules, "my_plugin", mock_mod)

class TestInspector:
    def test_parse_valid_entry(self, monkeypatch):
        setup_mock_module(monkeypatch)
        func_def = parse_plugin_entry("my_plugin:valid_func")
        
        assert func_def.name == "valid_func"
        assert func_def.docstring == "My Docstring"
        assert func_def.return_annotation == "str"
        assert len(func_def.args) == 1
        assert func_def.args[0].name == "a"
        assert func_def.args[0].annotation == "int"

    def test_parse_async_entry(self, monkeypatch):
        setup_mock_module(monkeypatch)
        func_def = parse_plugin_entry("my_plugin:async_func")
        assert func_def.is_async

    def test_module_not_found(self):
        with pytest.raises(InspectionError, match="Could not load entry point"):
            parse_plugin_entry("non_existent_module:func")

    def test_attribute_not_found(self, monkeypatch):
        setup_mock_module(monkeypatch)
        with pytest.raises(InspectionError, match="Could not load entry point"):
            parse_plugin_entry("my_plugin:non_existent_func")

    def test_target_not_callable(self, monkeypatch):
        setup_mock_module(monkeypatch)
        # inspect.signature raises TypeError if not callable
        with pytest.raises(InspectionError, match="Could not inspect signature"):
            parse_plugin_entry("my_plugin:not_callable")
~~~~~

#### Acts 3: 创建 Parser 单元测试
覆盖 `AnnAssign` 和 `Assign`。

~~~~~act
write_file
packages/stitcher-python-adapter/tests/unit/test_parser.py
~~~~~
~~~~~python
import pytest
from stitcher.adapter.python.internal.parser import parse_source_code

class TestParser:
    def test_parse_ann_assign(self):
        code = """
x: int = 1
y: str
__all__: list = ["x"]
        """
        module = parse_source_code(code)
        
        assert len(module.attributes) == 2
        
        attr_x = next(a for a in module.attributes if a.name == "x")
        assert attr_x.annotation == "int"
        assert attr_x.value == "1"
        
        attr_y = next(a for a in module.attributes if a.name == "y")
        assert attr_y.annotation == "str"
        assert attr_y.value is None

        assert module.dunder_all == '["x"]'

    def test_parse_assign(self):
        code = """
x = 1
__all__ = ["x"]
        """
        module = parse_source_code(code)
        
        attr_x = next(a for a in module.attributes if a.name == "x")
        assert attr_x.value == "1"
        assert attr_x.annotation is None
        
        assert module.dunder_all == '["x"]'

    def test_parse_imports(self):
        code = """
import os
from sys import path
        """
        module = parse_source_code(code)
        assert "import os" in module.imports
        assert "from sys import path" in module.imports
~~~~~

### 下一步建议
运行新添加的测试用例，并观察覆盖率是否有所提升。如果一切顺利，我们就可以提交这次的代码。这将显著提高我们对底层适配器逻辑的信心。
