简要回答：
明白。我们将遵循**高内聚原则**，将单元测试放置在 `packages/stitcher-scanner/tests/` 目录下。

现在正式进入 **TDD 循环的 RED 阶段**。我们将编写第一个测试用例，它断言 Scanner 能够解析最基本的函数定义。由于 Scanner 的实现代码尚不存在，这个测试将会（且必须）失败。

## [WIP] test: 添加 Scanner 基础单元测试 (Red Phase)

### 用户需求
用户要求开始 `stitcher-scanner` 的 TDD 开发流程，并将测试文件放置在子包内部以保持内聚性。

### 评论
这是 TDD 的第一步。我们通过编写“使用代码”的代码（即测试），来定义 `stitcher-scanner` 的公共 API 接口和预期行为。

我们预期的 API 是：`from stitcher.scanner import parse_source_code`，它接收源代码字符串，返回 `ModuleDef` 对象。

### 目标
1.  在 `packages/stitcher-scanner/tests/` 下创建测试目录。
2.  编写 `test_parser_basic.py`，测试一个简单的“Hello World”函数的解析。
3.  更新根目录配置，确保 `pytest` 能发现这些分散的测试。

### 基本原理
测试将使用 `stitcher-spec` 中定义的模型来验证解析结果。这将确保 `Scanner` 产生的 IR 符合我们的契约。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/tests #comp/scanner #scope/core #ai/instruct
#task/domain/testing #task/object/scanner-tests #task/action/create-case
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 创建子包测试目录
~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-scanner/tests
~~~~~

#### Acts 2: 编写第一个失败的测试 (RED)
这个测试定义了我们期望 `Scanner` 如何工作。注意我们需要处理 `ArgumentKind` 和 `FunctionDef` 的比对。

~~~~~act
write_file
packages/stitcher-scanner/tests/test_parser_basic.py
~~~~~
~~~~~python
import pytest
from stitcher.spec import ArgumentKind, FunctionDef, ModuleDef
# 注意：这个模块还不存在，这是 TDD 的一部分
from stitcher.scanner import parse_source_code

def test_parse_simple_function():
    source_code = """
def hello(name: str = "world") -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello {name}"
"""
    
    # Action
    module: ModuleDef = parse_source_code(source_code)
    
    # Assert
    assert isinstance(module, ModuleDef)
    assert len(module.functions) == 1
    
    func = module.functions[0]
    assert isinstance(func, FunctionDef)
    assert func.name == "hello"
    assert func.docstring == "Say hello."
    assert func.return_annotation == "str"
    assert func.is_async is False
    
    # Check arguments
    assert len(func.args) == 1
    arg = func.args[0]
    assert arg.name == "name"
    assert arg.annotation == "str"
    # AST 解析出的默认值通常是其源码表示，即 '"world"' (包含引号)
    assert arg.default == '"world"' 
    assert arg.kind == ArgumentKind.POSITIONAL_OR_KEYWORD
~~~~~

#### Acts 3: 更新 Pytest 配置
为了让根目录运行 `pytest` 时能找到这些测试，我们需要扩展 `testpaths`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
[tool.pytest.ini_options]
addopts = "-ra -q"
testpaths = ["tests"]
pythonpath = ["packages/stitcher-spec/src", "packages/stitcher-common/src", "packages/stitcher-scanner/src", "packages/stitcher-io/src", "packages/stitcher-config/src", "packages/stitcher-application/src", "packages/stitcher-cli/src"]
~~~~~
~~~~~new
[tool.pytest.ini_options]
addopts = "-ra -q"
testpaths = ["tests", "packages"]
pythonpath = ["packages/stitcher-spec/src", "packages/stitcher-common/src", "packages/stitcher-scanner/src", "packages/stitcher-io/src", "packages/stitcher-config/src", "packages/stitcher-application/src", "packages/stitcher-cli/src"]
~~~~~

### 下一步建议
现在我们已经有了测试，下一步自然是**运行测试并确认它失败**（如果因为它导入错误而报错，也算是符合预期的失败）。
然后，我们将进入 **GREEN 阶段**：实现 `stitcher.scanner.parse_source_code` 函数的核心逻辑，使其能够通过这个测试。这意味着我们要开始处理 Python 的 `ast` 模块了。
