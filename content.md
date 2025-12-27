我们需要使 `extract_arg` 函数更加健壮，在访问 `param.name` 之前，先用 `hasattr` 检查其是否存在。

我将生成一个计划来修复这个解析器 bug。

## [WIP] fix(scanner): Handle bare star (*) in function signatures

### 错误分析
`stitcher check` 运行时抛出 `AttributeError: 'ParamStar' object has no attribute 'name'`，导致解析流程意外终止。根本原因在于 `stitcher.scanner.parser.py` 的 `extract_arg` 辅助函数未能正确处理函数签名中的裸星号 `*`（用于分隔位置参数和关键字参数）。`libcst` 使用 `cst.ParamStar` 节点表示此语法，但该节点在这种情况下没有 `name` 属性。现有代码在尝试访问 `param.name` 之前未进行存在性检查，从而引发了该属性错误。

### 用户需求
修复 `stitcher check` 命令遇到的 `AttributeError` 崩溃，使其能够正确解析包含裸星号 `*` 的函数签名。

### 评论
这是一个关键的 bug 修复，它增强了 AST 解析器的健壮性，使其能够兼容现代 Python 3 的常见语法。修复此问题将确保 Stitcher 可以在更广泛、更复杂的代码库上稳定运行。

### 目标
1.  定位 `stitcher.scanner.parser.py` 中的 `extract_arg` 函数。
2.  在访问 `param.name` 属性之前，添加 `hasattr` 检查。
3.  确保修改后的逻辑能同时正确处理 `*args` 和裸星号 `*`。

### 基本原理
我们将通过防御性编程来修复此问题。在 `extract_arg` 函数中，针对 `cst.ParamStar` 类型的节点，我们将首先使用 `hasattr(param, 'name')` 来判断 `name` 属性是否存在。只有在存在的情况下，才继续尝试获取其值。这样可以优雅地处理裸星号语法，避免程序崩溃。

### 标签
#intent/fix #flow/ready #priority/critical #comp/scanner #concept/parser #scope/core #ai/instruct #task/domain/parsing #task/object/signature-parser #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `parser.py` 中的 `extract_arg` 函数

我们将修改 `extract_arg` 函数，使其在处理 `cst.ParamStar` 节点时更加安全。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.py
~~~~~
~~~~~python.old
        def extract_arg(
            param: Union[cst.Param, cst.ParamStar], kind: ArgumentKind
        ) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)
            # cst.ParamStar only has name if it's *args (not just *)

            if isinstance(param, cst.ParamStar):
                # Handle *args (bare * has no name)
                name = param.name.value if isinstance(param.name, cst.Name) else ""
                annotation = None
                if isinstance(param.annotation, cst.Annotation):
                    annotation = dummy_module.code_for_node(
                        param.annotation.annotation
                    ).strip()
                return Argument(name=name, kind=kind, annotation=annotation)
~~~~~
~~~~~python.new
        def extract_arg(
            param: Union[cst.Param, cst.ParamStar], kind: ArgumentKind
        ) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)
            # cst.ParamStar only has name if it's *args (not just *)

            if isinstance(param, cst.ParamStar):
                # Handle *args. A bare '*' separator won't have a .name attribute.
                name = ""
                if hasattr(param, "name") and isinstance(param.name, cst.Name):
                    name = param.name.value

                annotation = None
                if hasattr(param, "annotation") and isinstance(
                    param.annotation, cst.Annotation
                ):
                    annotation = dummy_module.code_for_node(
                        param.annotation.annotation
                    ).strip()
                return Argument(name=name, kind=kind, annotation=annotation)
~~~~~
