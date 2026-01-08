## [WIP] 测试失败的原因是由于我们在 **Acts 1** 中修改了 `DocstringRendererProtocol` 接口，增加了 `context` 参数，并在 **Acts 3** 中让生成器开始传递该参数。然而，我遗漏了更新 `RawDocstringRenderer` 的实现，导致在使用默认的 `raw` 模式进行渲染时，由于不匹配的参数列表抛出了 `TypeError`。

这是一个典型的“协议不一致”导致的回归错误。

### 用户需求
修复 `RawDocstringRenderer.render` 方法，使其符合最新的 `DocstringRendererProtocol` 协议规范。

### 评论
在进行架构级的协议修改时，必须确保该协议的所有实现类（包括内置的默认实现）都同步更新。

### 目标
1.  更新 `RawDocstringRenderer` 的 `render` 方法签名，添加 `context` 参数。

### 标签
#intent/fix #flow/ready #priority/critical #comp/adapter #concept/docstring #scope/core #task/domain/docstring #task/object/rendering-pipeline #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 RawDocstringRenderer 协议符合性

我们将更新 `factory.py` 中的 `RawDocstringRenderer` 类，使其支持 `context` 参数。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/factory.py
~~~~~
~~~~~python.old
class RawDocstringRenderer(DocstringRendererProtocol):
    """
    A simple renderer that just dumps the summary.
    Used for 'raw' mode consistency.
    """

    def render(self, docstring_ir) -> str:
        # For raw mode, we just return the summary as the full docstring.
        # Addons and other fields are ignored in raw render.
        return docstring_ir.summary or ""
~~~~~
~~~~~python.new
class RawDocstringRenderer(DocstringRendererProtocol):
    """
    A simple renderer that just dumps the summary.
    Used for 'raw' mode consistency.
    """

    def render(self, docstring_ir, context=None) -> str:
        # For raw mode, we just return the summary as the full docstring.
        # Addons and other fields are ignored in raw render.
        return docstring_ir.summary or ""
~~~~~

### 下一步建议
修复此问题后，请重新运行测试 `test_generate_does_not_update_signatures`。如果该测试通过，则证明渲染管线的底层连接已经打通，我们可以继续验证 `Google` 和 `Numpy` 风格下的具体渲染效果。
