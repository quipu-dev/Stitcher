简要回答

分析正确。这个 `AssertionError` 暴露了 `GriffeDocstringParser` 中一个微妙的语义映射错误。对于 `Returns` 部分，Griffe 将返回类型（如 "bool"）解析到了其内部模型的 `name` 字段。我的代码错误地将这个 `name` 直接映射到了我们 `DocstringItem` 的 `name` 字段，而不是 `annotation` 字段。

我将立即修复这个映射逻辑。

## [WIP] fix: 修正返回类型的语义映射

### 错误分析

**症状**: `AssertionError: assert None == 'bool'`
**原因**: `GriffeDocstringParser` 在处理 `Returns` 类型的 Docstring Section 时，错误地将返回类型（Griffe 解析结果中的 `name`）赋给了 `DocstringItem` 的 `name` 属性，而 `annotation` 属性被置为 `None`。正确的做法是应将返回类型赋给 `annotation` 属性，`name` 属性应为 `None`（因为返回值通常没有名字）。
**解决方案**: 修改 `_map_section` 方法，为 `DocstringSectionReturns` 和 `DocstringSectionYields` 提供专门的映射逻辑，将 Griffe `item.name` 映射到 `DocstringItem.annotation`。

### 用户需求

修复 `test_parsers.py` 中因 `Returns` 部分解析逻辑错误导致的断言失败。

### 评论

这是一个关键的修复。确保 IR (Intermediate Representation) 的语义正确性是整个架构的基石。如果类型信息被错误地存储在 `name` 字段，后续的渲染器、校验器和代码生成器都将无法正常工作。这个错误暴露了对 Griffe 内部模型的假设偏差，现在我们将予以纠正。

### 目标

1.  修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/parsers.py`，分离并修正 `Returns`/`Yields`/`Raises` section 的映射逻辑。

### 基本原理

我们将专门处理 `DocstringSectionReturns` 和 `DocstringSectionYields`，确保从 Griffe 解析出的类型信息被正确地放入 `DocstringItem` 的 `annotation` 字段，从而使我们的 IR 模型与语义意图保持一致。

### 标签

#intent/fix #flow/ready #priority/high #comp/adapter #concept/parser #task/domain/docstring #task/object/adapter #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `_map_section` 的映射逻辑

我们将重构 `_map_section` 方法，为不同类型的 Section 提供更精确的映射规则。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/parsers.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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

        if isinstance(section, (DocstringSectionReturns, DocstringSectionYields)):
            # For returns/yields, Griffe often puts the type in the `name` field.
            items = []
            for item in section.value:
                items.append(
                    DocstringItem(
                        name=None,  # The type is not a name
                        annotation=item.name,  # The type is stored in griffe's 'name'
                        description=item.description or "",
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, DocstringSectionRaises):
            # For raises, the exception type is in the `annotation` field.
            items = []
            for item in section.value:
                items.append(
                    DocstringItem(
                        name=None,  # The exception type is not a name
                        annotation=str(item.annotation) if item.annotation else None,
                        description=item.description or "",
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, DocstringSectionAdmonition):
            # Admonitions like "Note", "Warning"
~~~~~

### 下一步建议

此修复应该能解决当前的断言错误。请重新运行测试。如果所有测试都通过，适配器层的基本功能就已稳固，我们可以放心地进入 **阶段 2: 存储层升级**。
