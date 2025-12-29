简要回答
测试再次失败，虽然崩溃原因从 `BuiltinModuleError` 变为了 `Could not resolve alias`，这说明我们迈进了一步（Griffe 现在尝试解析导入了），但因为它是在独立的上下文（isolate context）中解析该文件，找不到 `typing` 模块的定义，所以抛出了异常。

对于 MVP，我们不应让 Griffe 因为无法解析外部符号而让整个程序崩溃。我们需要捕获特定的导入解析错误，并允许它作为“未解析的符号”存在，就像 LibCST 目前做的那样。我们关心的主要是当前文件的结构，而不是完美的全局类型推断。

## [WIP] fix(adapter): 在 Griffe 解析中抑制 AliasResolutionError

### 错误分析
Griffe 仅仅在 `visit` 单个文件时，如果遇到无法定位源头的导入（如 `from typing import List`），且当前环境未提供该模块的元数据，就会抛出 `AliasResolutionError`（表现为 `Could not resolve alias...`）。
在 `stitcher generate` 或 `check` 的场景下，这种严格的解析是不必要的。我们只需要知道那里有一个名为 `List` 的符号即可，即使我们不知道它确切指向 `typing.List` 对象。

### 用户需求
修改 `GriffePythonParser`，使其在解析过程中遇到无法解析的 Alias 时不要崩溃，而是优雅降级。

### 评论
Griffe 文档或源码表明 `visit` 默认行为是尝试解析。我们需要查阅 Griffe 是否提供了抑制选项，或者在我们的代码中捕获异常。然而，`visit` 方法本身抛出异常意味着解析过程被中断。

根据 Griffe 的设计，`visit` 本身通常不抛出 Alias 错误，这种错误通常发生在访问某些属性（如 `annotation` 或 `target`）时。
仔细看堆栈，`visit` 内部处理 `ImportFrom` 时调用了 `relative_to_absolute`，这已经修复。
现在的错误栈没有显示具体的行号，但提示是从 `test_griffe_resolves_imports` 抛出的。

实际上，Griffe 在解析过程中若遇到无法解析的引用，默认会记录警告。但如果配置为严格模式或某些操作触发了深层解析，则会抛错。
不过，`griffe.visit` 生成的对象可能是一个 `Alias` 对象而不是 `Function` 或 `Class`，若我们在 `_map_module` 中错误地处理了这些 `Alias` 对象（例如尝试访问其未解析的属性），就会触发这个错误。

**推测**：问题可能出在我们的遍历逻辑上。
在 `_map_module` 中：
```python
        for member in gm.members.values():
            if member.is_function:
```
访问 `member.is_function` 时，如果 `member` 是一个 `Alias` (即 `List` 是从 `typing` 导入的)，Griffe 会尝试解析该 Alias 以确定它指向的目标是否是函数。如果解析失败，就会抛出错误。

### 目标
修改 `_map_module`，在遍历成员时，安全地跳过无法解析的 Alias 对象，避免崩溃。

### 基本原理
对于导入的符号（Alias），我们不需要将其映射为当前模块的 Function 或 Class 定义。Stitcher 的 `ModuleDef` 只关心当前模块**定义**了什么，而不关心它导入了什么（导入应该在 `imports` 列表中处理）。因此，我们可以安全地忽略 `is_alias` 为真的成员。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/parser #scope/core #ai/instruct
#task/domain/engine #task/object/griffe-parser #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 安全地过滤模块成员

修改 `_map_module`，在检查 `is_function` 或 `is_class` 之前，先检查并跳过 `is_alias`。这样可以避免触发 Griffe 的解析逻辑，从而避免崩溃。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
    def _map_module(self, gm: griffe.Module, file_path: str) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            if member.is_function:
                functions.append(self._map_function(member))
            elif member.is_class:
                classes.append(self._map_class(member))
            elif member.is_attribute:
                attributes.append(self._map_attribute(member))

        docstring = gm.docstring.value if gm.docstring else None
~~~~~
~~~~~python.new
    def _map_module(self, gm: griffe.Module, file_path: str) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            # Skip aliases (imported names) to prevent resolution errors
            # We only want to map symbols DEFINED in this module.
            if member.is_alias:
                continue

            if member.is_function:
                functions.append(self._map_function(member))
            elif member.is_class:
                classes.append(self._map_class(member))
            elif member.is_attribute:
                attributes.append(self._map_attribute(member))

        docstring = gm.docstring.value if gm.docstring else None
~~~~~

### 下一步建议

再次运行集成测试。
如果这个修复奏效，`parser.parse` 将不再崩溃，测试将继续执行。
测试最后断言 `assert "List" in func.return_annotation`。由于我们忽略了 Alias 解析，Griffe 可能仅仅返回字符串 `"List[User]"` 作为注解，这正是我们期望的——我们不需要它解析为 `typing.List`，只要文本保留即可。
