[简要回答]
我们将修改 `UsageScanVisitor`，使其在处理相对导入时不再生成指向父级包路径的虚假引用，从而修复循环依赖误报。

## [WIP] fix(analysis): 修复相对导入导致的虚假循环依赖

### 错误分析

在 `stitcher check` 的架构检查中，检测到了错误的循环依赖：`engines/__init__.py` <-> `consistency/__init__.py`。
经过分析，这是因为 `UsageScanVisitor` 在处理相对导入（如 `from .engine import ...`）时，过于激进地将其解析后的绝对路径（`pkg.engines.consistency.engine`）进行了前缀拆分，并注册了对所有父级路径（如 `pkg.engines`）的引用。
这导致子包被错误地判定为依赖于父包，从而在使用“桶式导出”模式时形成死循环（父导子，子虚假依赖父）。
对于相对导入，源代码中并不存在对父级绝对路径的显式引用，因此不应注册这些前缀依赖。

### 用户需求

修复 `stitcher check` 在处理 Python 相对导入时的逻辑，消除因错误的父级依赖推断而导致的误报循环依赖。

### 评论

这个修复不仅解决了当前的误报，还提高了引用分析的语义准确性。相对导入的设计初衷就是解耦父级路径，分析工具应尊重这一点。

### 目标

1.  修改 `UsageScanVisitor`，使其支持可配置的前缀展开行为。
2.  在处理 `ImportFrom` 节点时，检测是否为相对导入。
3.  对于相对导入，禁止注册其绝对路径的前缀引用。
4.  验证集成测试 `test_architecture_analysis.py` 通过。

### 基本原理

通过在 `_register_node` 方法中增加 `expand_prefixes` 控制标志，并在 `visit_ImportFrom` 中根据 `node.relative` 的存在与否来动态设置此标志。

### 标签

#intent/fix #flow/ready #priority/high #comp/analysis #concept/dependency-graph #scope/core #ai/instruct #task/domain/analysis #task/object/usage-visitor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 UsageScanVisitor

修改 `_register_node` 方法签名和逻辑，并在 `visit_ImportFrom` 中正确调用它。

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/analysis/usage_visitor.py
~~~~~
~~~~~python.old
    def _register_node(self, node: cst.CSTNode, fqn: str, ref_type: ReferenceType):
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
            ref_type=ref_type,
            target_node_fqn=fqn,
        )
        self.registry.register(fqn, loc)
        # Also register against prefixes for namespace refactoring
        if ref_type == ReferenceType.IMPORT_PATH:
            parts = fqn.split(".")
            for i in range(1, len(parts)):
                prefix_fqn = ".".join(parts[:i])
                self.registry.register(prefix_fqn, loc)
~~~~~
~~~~~python.new
    def _register_node(
        self,
        node: cst.CSTNode,
        fqn: str,
        ref_type: ReferenceType,
        expand_prefixes: bool = True,
    ):
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
            ref_type=ref_type,
            target_node_fqn=fqn,
        )
        self.registry.register(fqn, loc)
        # Also register against prefixes for namespace refactoring
        if ref_type == ReferenceType.IMPORT_PATH and expand_prefixes:
            parts = fqn.split(".")
            for i in range(1, len(parts)):
                prefix_fqn = ".".join(parts[:i])
                self.registry.register(prefix_fqn, loc)
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/analysis/usage_visitor.py
~~~~~
~~~~~python.old
        if absolute_module:
            if node.module:
                self._register_node(
                    node.module, absolute_module, ReferenceType.IMPORT_PATH
                )
~~~~~
~~~~~python.new
        if absolute_module:
            # Check if this is a relative import (node.relative is a sequence of Dots)
            is_relative = len(node.relative) > 0

            if node.module:
                self._register_node(
                    node.module,
                    absolute_module,
                    ReferenceType.IMPORT_PATH,
                    expand_prefixes=not is_relative,
                )
~~~~~

### 下一步建议

应用修复后，运行集成测试 `pytest packages/stitcher-analysis/tests/integration/test_architecture_analysis.py` 以验证修复效果。如果测试通过，我们可以将集成测试中的断言逻辑（目前是反向的 TODO）修正为正常的“无违规”断言并作为回归测试提交。
