这里有修复 `InjectorTransformer` 无法向单行函数体注入文档字符串的计划。

## [WIP] fix: 修复 `inject_docstrings` 对单行函数的支持

### 错误分析
测试 `test_inject_multiline_handling` 失败，因为 `InjectorTransformer._inject_into_body` 方法目前对 `cst.SimpleStatementSuite`（例如 `def f(): pass`）的处理是直接返回原节点，没有执行注入。
要解决这个问题，我们需要将 `SimpleStatementSuite` 转换为 `IndentedBlock`，以便能够容纳新插入的文档字符串语句。

### 用户需求
用户希望 `inject_docstrings` 能够处理所有形式的函数体，包括紧凑的单行形式。

### 目标
修改 `transformer.py`：
1.  在 `_inject_into_body` 中实现从 `SimpleStatementSuite` 到 `IndentedBlock` 的转换逻辑。
2.  在转换过程中，如果原函数体仅包含 `pass`，则在注入文档后将其移除，以保持代码整洁。

### 标签
#intent/fix #flow/ready #priority/high
#comp/scanner #concept/parser #scope/core
#ai/instruct
#task/domain/dev-tools #task/object/lifecycle-management #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 增强 `InjectorTransformer` 以支持单行块转换

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/transformer.py
~~~~~
~~~~~python.old
    def _inject_into_body(
        self, 
        body: Union[cst.BaseSuite, cst.SimpleStatementSuite], 
        doc_content: str
    ) -> Union[cst.BaseSuite, cst.SimpleStatementSuite]:
        
        new_doc_node = self._create_docstring_node(doc_content)

        if isinstance(body, cst.SimpleStatementSuite):
            # Convert simple suite to indented block for cleanliness if adding docstring?
            # Or assume we can just replace. 
            # If it was "def f(): pass", converting to docstring is tricky without changing type.
            # Let's stick to IndentedBlock for injection usually, but if source is SimpleStatementSuite
            # we might need to convert it. LibCST makes changing node types hard.
            # For MVP: If it's a simple suite, we replace its content.
            return body  # TODO: Handle conversion to IndentedBlock if needed for style

        elif isinstance(body, cst.IndentedBlock):
            new_body_stmts = []
~~~~~
~~~~~python.new
    def _inject_into_body(
        self,
        body: Union[cst.BaseSuite, cst.SimpleStatementSuite],
        doc_content: str,
    ) -> Union[cst.BaseSuite, cst.SimpleStatementSuite]:

        new_doc_node = self._create_docstring_node(doc_content)

        if isinstance(body, cst.SimpleStatementSuite):
            # Convert "def f(): stmt" to:
            # def f():
            #     """doc"""
            #     stmt
            new_stmts = [new_doc_node]

            # Process existing statements in the one-liner
            for stmt in body.body:
                # If it's just 'pass', we can remove it since we now have a docstring
                if isinstance(stmt, cst.Pass):
                    continue
                
                # Wrap small statement into a line
                new_stmts.append(cst.SimpleStatementLine(body=[stmt]))

            return cst.IndentedBlock(body=new_stmts)

        elif isinstance(body, cst.IndentedBlock):
            new_body_stmts = []
~~~~~

### 下一步建议
再次运行 `packages/stitcher-scanner/tests/test_transformer.py`。
通过后，即可着手实现 `stitcher-application` 中的 `strip` 和 `eject` 命令集成。
