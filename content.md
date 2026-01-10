You've correctly identified the issue. The error `Could not resolve alias ... Optional pointing at typing.Optional` is caused by a limitation in our parsing dependency, `griffe`, which struggles to resolve type aliases when the `typing` import is not at the module's top level. Our own codebase in `rename_symbol.py` unfortunately contained this pattern, causing the `generate` command to fail when scanning itself.

My plan addresses this on two fronts:
1.  **Immediate Fix:** I will correct the problematic code in `rename_symbol.py` by moving the import to the top level, which will resolve the build error.
2.  **Regression Test:** I will create a new test file that specifically reproduces and captures this parsing failure. This test will serve as a regression guard and formally document this limitation in our dependency, ensuring we are aware of it and can track its resolution.

## [WIP] test(refactor): Add regression test for parser bug and fix local import

### 用户需求
1.  修复 `stitcher-refactor` 包中 `rename_symbol.py` 存在的局部导入 `typing.Optional` 的问题，该问题导致 `stitcher generate` 命令失败。
2.  创建一个新的测试用例，用于捕获（reproduce）由局部 `typing` 导入引起的 `griffe` 解析器别名解析失败的 bug。

### 评论
这是一个重要的修复和补充。修复自身的代码以规避依赖项的 bug 是解决当前构建失败的直接方法。同时，添加一个专门捕获此 bug 的回归测试，不仅可以防止未来团队成员无意中再次引入同样的问题，也正式地记录了我们对 `griffe` 这个依赖项的已知限制，这对于项目的长期维护至关重要。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py` 文件，将 `from typing import Optional` 移动到文件顶部。
2.  在 `packages/stitcher-python-adapter/tests/integration/` 目录下创建一个新的测试文件 `test_griffe_parsing_bugs.py`。
3.  在新测试文件中，编写一个测试用例，该用例尝试解析一个包含类内部 `typing` 导入的代码片段，并断言它会抛出 `griffe.exceptions.AliasResolutionError` 异常，从而“捕获”这个 bug。

### 基本原理
我们采取“规避并记录”的策略：
1.  **规避 (Workaround)**: 通过将 `rename_symbol.py` 中的 `import` 语句提升到全局作用域，我们改变了代码风格以适应 `griffe` 解析器的当前能力，从而立即修复了 CI/CD 流程中的阻塞性错误。
2.  **记录 (Documentation via Test)**: 新增的测试用例将作为一种可执行的文档。它清晰地定义了 `griffe` 解析器的一个边界条件。如果未来的 `griffe`版本修复了此问题，该测试将开始失败，这将成为我们移除相关代码限制并更新依赖项的明确信号。在 `stitcher-python-adapter` 中添加此测试是合适的，因为它直接验证了我们语言适配器层（及其依赖）的行为。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/refactor #comp/tests #concept/parser #scope/dx #ai/instruct #task/domain/testing #task/object/regression-test #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建回归测试以捕获解析 Bug

我们首先创建新的测试文件。这个测试会直接调用 `GriffePythonParser` 来解析一个包含局部 `typing` 导入的字符串，并断言 `griffe` 抛出 `AliasResolutionError`。这完全符合“捕获错误”的要求。

~~~~~act
write_file
packages/stitcher-python-adapter/tests/integration/test_griffe_parsing_bugs.py
~~~~~
~~~~~python
from textwrap import dedent
import pytest
from griffe.exceptions import AliasResolutionError

from stitcher.adapter.python import GriffePythonParser


def test_parser_fails_on_local_typing_import():
    """
    Captures a known bug where Griffe fails to resolve a type alias
    if the import from 'typing' is not at the top level of the module.
    """
    # 1. Setup
    parser = GriffePythonParser()
    source_code = dedent(
        """
        class MyService:
            from typing import Optional

            def get_data(self) -> Optional[str]:
                return "data"
        """
    )

    # 2. Verification
    # This should raise AliasResolutionError until the bug in Griffe is fixed.
    # This test serves to document this dependency limitation.
    with pytest.raises(AliasResolutionError):
        parser.parse(source_code, "buggy_module.py")
~~~~~

#### Acts 2: 修复 `rename_symbol.py` 中的局部导入问题

现在，我们将 `rename_symbol.py` 中的 `import` 语句移动到文件顶部，以解决导致 CI 失败的直接原因。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
class RenameSymbolOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    from typing import Optional

    def _find_definition_node(self, ctx: RefactorContext) -> Optional[SymbolNode]:
        return ctx.graph.find_symbol(self.old_fqn)

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
~~~~~
~~~~~python.new
from typing import Optional


class RenameSymbolOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def _find_definition_node(self, ctx: RefactorContext) -> Optional[SymbolNode]:
        return ctx.graph.find_symbol(self.old_fqn)

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
~~~~~

### 下一步建议
我们已经添加了测试并修复了代码。现在，我建议提交这些更改。如果你同意，我将生成一个包含 `git add` 和 `git commit` 的 `[COMMIT]` 计划。
