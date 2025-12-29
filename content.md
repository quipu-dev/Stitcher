简要回答
测试 `test_parse_simple_function` 失败的原因是 `Griffe`（及其底层的 `ast.unparse`）在将默认值表达式转换为字符串时，默认优先使用单引号 `'`，而源代码和测试断言中使用的是双引号 `"`。这是基于 AST 解析器的预期行为（标准化格式），而非错误。

我们将更新测试用例，使其预期结果与 Griffe 的标准输出（单引号）保持一致。

## [WIP] test(adapter): 修正单元测试以匹配 Griffe 的 AST 字符串标准化行为

### 用户需求
修复 `packages/stitcher-python-adapter/tests/unit/test_griffe_parser.py` 中的断言错误。

### 评论
Griffe 通过 `ast` 模块解析代码，在将默认值节点转换回字符串时，Python 的 `ast.unparse` 会标准化引号样式（通常优先使用单引号）。测试应该验证语义等价性，接受这种标准化行为。

### 目标
修改 `tests/unit/test_griffe_parser.py`，将预期值从 `"default"` (双引号) 调整为 `'default'` (单引号)。

### 基本原理
AST 解析会丢失原始的引号风格信息。除非使用 CST（如 LibCST），否则无法保留原始引用风格。我们在适配器层接受这种标准化是合理的。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/parser #scope/core #ai/instruct
#task/domain/testing #task/object/unit-test #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正测试断言

我们将更新测试文件，使其期望默认值参数被格式化为单引号字符串。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/test_griffe_parser.py
~~~~~
~~~~~python.old
        arg2 = func.args[1]
        assert arg2.name == "b"
        assert arg2.default == '"default"'

    def test_parse_async_function(self, parser):
~~~~~
~~~~~python.new
        arg2 = func.args[1]
        assert arg2.name == "b"
        # Griffe (via ast.unparse) normalizes string literals to single quotes
        assert arg2.default == "'default'"

    def test_parse_async_function(self, parser):
~~~~~

### 下一步建议

测试修正后，我们应当确信核心函数解析逻辑是工作的。接下来可以继续扩展 `GriffePythonParser` 以支持类（Class）和属性（Attribute）的解析，这是实现完整功能的关键步骤。
