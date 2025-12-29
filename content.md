好的，我们继续。现在，我将为 `GriffePythonParser` 实现属性（Attributes）的映射逻辑。

这是一个很好的增量步骤，因为属性的结构相对简单，能让我们快速验证 Griffe 对象到 Stitcher IR 的基本转换流程是否正确。

## [WIP] feat: 在 GriffePythonParser 中实现属性映射

### 用户需求
继续 Griffe 集成工作，具体实现 `_map_attribute` 方法，用于将 Griffe 的 `Attribute` 对象转换为 Stitcher 的 `Attribute` IR。

### 评论
这是一个完美的增量步骤。属性映射逻辑清晰直接，是验证我们适配器模式正确性的理想起点。完成这一步后，我们的新解析器将首次能够产出有意义的、可验证的 IR 数据。

### 目标
1.  在 `GriffePythonParser` 中完整实现 `_map_attribute` 方法的转换逻辑。
2.  处理 Griffe 属性的 `name`、`annotation`、`value` 和 `docstring` 字段，并将它们正确映射到 Stitcher IR 对象的相应字段。
3.  在主 `parse` 方法中激活对模块级属性的映射调用。

### 基本原理
我们将直接利用 Griffe 提供的结构化数据。`griffe.dataclasses.Attribute` 对象已经包含了我们需要的所有信息。我们的 `_map_attribute` 方法将作为一个纯粹的转换函数，接收 Griffe 对象并返回我们的 IR 对象。通过在 `parse` 方法中调用此函数，我们正式开始将 Griffe 的解析结果集成到 Stitcher 的数据流中。

### 标签
#intent/build #flow/ready #priority/high #comp/python-adapter #concept/parser #scope/core #ai/instruct #task/domain/parsing #task/object/griffe-adapter #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 实现属性映射逻辑

我们将修改 `griffe_parser.py` 文件，填充 `_map_attribute` 方法并启用它。该方法将处理名称、注解、值和文档字符串的转换。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
        # to stitcher.spec.ModuleDef.

        # Placeholder implementation for the skeleton:
        return ModuleDef(
            file_path=file_path,
            docstring=griffe_module.docstring.value if griffe_module.docstring else None,
            # functions=[self._map_function(f) for f in griffe_module.functions.values()],
            # classes=[self._map_class(c) for c in griffe_module.classes.values()],
            # attributes=[self._map_attribute(a) for a in griffe_module.attributes.values()],
        )

    def _map_function(self, griffe_func: dc.Function) -> FunctionDef:
        # TODO: Map Griffe function to FunctionDef
        pass

    def _map_class(self, griffe_class: dc.Class) -> ClassDef:
        # TODO: Map Griffe class to ClassDef
        pass

    def _map_attribute(self, griffe_attr: dc.Attribute) -> Attribute:
        # TODO: Map Griffe attribute to AttributeDef
        pass
~~~~~
~~~~~python.new
        # to stitcher.spec.ModuleDef.

        # Placeholder implementation for the skeleton:
        return ModuleDef(
            file_path=file_path,
            docstring=griffe_module.docstring.value if griffe_module.docstring else None,
            # functions=[self._map_function(f) for f in griffe_module.functions.values()],
            # classes=[self._map_class(c) for c in griffe_module.classes.values()],
            attributes=[
                self._map_attribute(a) for a in griffe_module.attributes.values()
            ],
        )

    def _map_function(self, griffe_func: dc.Function) -> FunctionDef:
        # TODO: Map Griffe function to FunctionDef
        pass

    def _map_class(self, griffe_class: dc.Class) -> ClassDef:
        # TODO: Map Griffe class to ClassDef
        pass

    def _map_attribute(self, griffe_attr: dc.Attribute) -> Attribute:
        """Maps a Griffe Attribute to a Stitcher IR Attribute."""
        return Attribute(
            name=griffe_attr.name,
            annotation=str(griffe_attr.annotation)
            if griffe_attr.annotation
            else None,
            value=griffe_attr.value if griffe_attr.value else None,
            docstring=griffe_attr.docstring.value if griffe_attr.docstring else None,
        )
~~~~~

### 下一步建议
属性映射已经完成。合乎逻辑的下一步是处理函数（Functions）的映射。这将是更复杂的一步，因为它涉及到参数、返回类型、装饰器和异步标志。

我建议我们接下来：
1.  **实现 `_map_function`**: 将 Griffe 的 `Function` 对象映射到我们的 `stitcher.spec.FunctionDef` IR。
2.  **实现一个辅助方法 `_map_argument`**: 用于处理函数参数的复杂映射。
3.  **在 `parse` 方法中启用 functions 的映射**。

如果您同意，我将为此生成详细计划。
