你的分析非常准确。当前的 `IRBuildingVisitor` 在面对 Python 丰富的赋值语法时显得过于脆弱，这直接限制了 Stitcher 对公共 API 的识别能力。

我将按照 TDD（测试驱动开发）的流程，首先建立针对“解包赋值”和“嵌套类”的测试用例，然后增强 `IRBuildingVisitor` 的实现。

## [WIP] feat(lang-python): 增强 IR 解析器以支持解包赋值和鲁棒处理嵌套类

### 用户需求
1.  **支持解包赋值**: 解析器应能识别 `x, y = 1, 2` 或 `[a, b] = func()` 形式的属性定义。
2.  **鲁棒处理嵌套类**: 确保嵌套类及其内部定义的函数/属性不会导致解析器崩溃，且不会错误地“泄露”到模块顶层。

### 评论
这是提升 Python 静态分析精度的关键一步。在数据科学和很多现代库中，解包赋值（如 `SUCCESS, FAILURE = range(2)`）是非常常见的 API 定义方式。如果不处理这些，会导致索引不完整。

### 目标
1.  在 `test_visitors.py` 中增加解包赋值的测试。
2.  修改 `IRBuildingVisitor.visit_Assign`，支持迭代处理 `cst.Tuple` 和 `cst.List` 类型的 target。
3.  确保 `visit_ClassDef` 的栈逻辑在处理深度嵌套时依然稳定。

### 基本原理
我们利用 LibCST 的树结构。当 `Assign.targets[0].target` 为 `Tuple` 或 `List` 时，我们遍历其内部元素。如果元素是 `Name`，则将其视为一个新的属性定义。对于嵌套类，我们继续沿用当前的栈逻辑，但确保在 `leave_ClassDef` 时即使不处理嵌套类，也要安全地弹出，防止污染后续同级定义的上下文。

### 标签
#intent/build #flow/ready #priority/high #comp/lang-python #concept/parser #scope/core #ai/refine #task/domain/analysis #task/object/ir-parser #task/action/enhancement #task/state/begin

---

### Script

#### Acts 1: 创建测试用例以重现缺失能力

首先，我们在 `packages/stitcher-lang-python/tests/analysis/unit/cst/test_visitors.py` 中增加新的测试函数。

~~~~~act
patch_file
packages/stitcher-lang-python/tests/analysis/unit/cst/test_visitors.py
~~~~~
~~~~~python.old
        module = parse_source_code(code)
        assert "import os" in module.imports
        assert "from sys import path" in module.imports
~~~~~
~~~~~python.new
        module = parse_source_code(code)
        assert "import os" in module.imports
        assert "from sys import path" in module.imports

    def test_parse_unpacking_assignment(self):
        code = """
x, y = 1, 2
[a, b] = func()
        """
        module = parse_source_code(code)
        
        attr_names = {a.name for a in module.attributes}
        assert "x" in attr_names
        assert "y" in attr_names
        assert "a" in attr_names
        assert "b" in attr_names

    def test_nested_class_robustness(self):
        code = """
class Outer:
    class Inner:
        def inner_method(self):
            pass
    def outer_method(self):
        pass
        """
        # 目标是确保解析过程不崩溃，且 inner_method 不会出现在 Outer 或模块顶层
        module = parse_source_code(code)
        assert len(module.classes) == 1
        outer = module.classes[0]
        assert outer.name == "Outer"
        
        # 目前模型不支持嵌套类，所以 Inner 应该被忽略，但 outer_method 必须存在
        method_names = {m.name for m in outer.methods}
        assert "outer_method" in method_names
        assert "inner_method" not in method_names
~~~~~

#### Acts 2: 增强 `IRBuildingVisitor` 的赋值解析逻辑

现在我们修改解析器，使其能够递归处理赋值目标。

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/analysis/visitors.py
~~~~~
~~~~~python.old
    def visit_Assign(self, node: cst.Assign) -> Optional[bool]:
        # Handle: x = 1
        # Only handle simple assignment to a single name for now
        if len(node.targets) != 1:
            return False

        target = node.targets[0].target
        if not isinstance(target, cst.Name):
            return False

        name = target.value
        value = self._dummy_module.code_for_node(node.value).strip()

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            self.dunder_all = value
            return False

        loc = self._extract_location(node)
        self._add_attribute(
            Attribute(name=name, annotation=None, value=value, location=loc)
        )
        return False
~~~~~
~~~~~python.new
    def visit_Assign(self, node: cst.Assign) -> Optional[bool]:
        # Handle: x = 1 or x, y = 1, 2
        if len(node.targets) != 1:
            return False

        target_node = node.targets[0].target
        value_code = self._dummy_module.code_for_node(node.value).strip()
        loc = self._extract_location(node)

        def process_target(target: cst.CSTNode):
            if isinstance(target, cst.Name):
                name = target.value
                # Special handling for __all__
                if name == "__all__" and not self._class_stack:
                    self.dunder_all = value_code
                else:
                    self._add_attribute(
                        Attribute(name=name, annotation=None, value=value_code, location=loc)
                    )
            elif isinstance(target, (cst.Tuple, cst.List)):
                for element in target.elements:
                    if isinstance(element, (cst.TupleElement, cst.ListElement)):
                        process_target(element.value)

        process_target(target_node)
        return False
~~~~~

### 下一步建议

1.  **运行测试**: 执行 `pytest packages/stitcher-lang-python/tests/analysis/unit/cst/test_visitors.py` 验证修复。
2.  **处理嵌套类索引**: 虽然目前 `ClassDef` 模型不直接持有 `classes` 列表，但我们可以考虑将嵌套类作为 `Attribute` 处理，其 `value` 为类名，或者扩展模型以支持真正的树状结构。
3.  **支持方法内的属性**: 当前 `Assign` 仅在类和模块层级起作用，方法内部的 `self.x = 1` 尚未捕捉，这是后续增强 `UsageScanVisitor` 的重点。
