# [WIP] fix: 修正 ImportFrom 节点更新中的参数名错误

### 错误分析
测试失败，错误为 `TypeError: ImportFrom.__init__() got an unexpected keyword argument 'level'`。

这是因为 `libcst.ImportFrom` 节点的属性名是 `relative` 而不是 `level`。在 LibCST 中，`relative` 属性存储一个 `list[Dot]`，其长度表示相对导入的层级（例如 `.` 长度为 1）。如果 `relative` 为空列表，则表示绝对导入。

我在之前的修复中错误地使用了 `level`（这是 AST 模块的术语），而不是 LibCST 的 `relative`。

### 用户需求
修正 `SymbolRenamerTransformer` 中的 `leave_ImportFrom` 方法，使其正确使用 LibCST 的 API 来构造绝对导入节点。

### 评论
这是一个简单的 API 使用错误，修正后应能通过测试。

### 目标
修改 `packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py`，将 `level=0` 替换为 `relative=[]`。

### 基本原理
查阅 LibCST 文档确认 `ImportFrom` 的签名为：
```python
class ImportFrom(SmallStatement):
    module: Optional[BaseExpression]
    names: Union[ImportStar, Sequence[ImportAlias]]
    relative: Sequence[Dot] = ()
    # ...
```
要将其转换为绝对导入，我们需要显式传递 `relative=[]`。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/refactor #scope/core #ai/instruct #task/domain/refactoring #task/object/import-fix #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修正 ImportFrom 参数

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python.old
            if new_fqn:
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    level=0  # Force absolute import
                )
        return updated_node
~~~~~
~~~~~python.new
            if new_fqn:
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    relative=[]  # Force absolute import by removing dots
                )
        return updated_node
~~~~~

### 下一步建议

重新运行测试：`uv run pytest packages/stitcher-refactor/tests/integration/test_bug_relative_import_refactor.py`
