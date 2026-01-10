# [WIP] fix: 增强 UsageVisitor 以支持动态导入解析

## [WIP] fix: 增强 UsageVisitor 以支持动态导入解析

### 错误分析
测试失败 `assert 0 > 0` 表明 `utils.do_work()` 未被识别为引用。
根本原因是 `PythonAdapter` 传递给 `UsageScanVisitor` 的 `local_symbols` 仅包含当前文件定义的类和函数，**不包含通过 `import` 语句引入的符号**。
当 Visitor 遍历到 `utils.do_work` 时，它尝试解析 `utils` (root_name)，但在 `local_symbols` 中找不到，因此忽略了该节点。

### 用户需求
使引用提取逻辑能够识别导入的符号，从而正确解析基于导入的属性访问（如 `utils.do_work`）。

### 评论
与其在 `PythonAdapter` 层面笨拙地预解析 import 字符串，不如利用 `UsageScanVisitor` 自身的 CST 遍历能力。Visitor 在访问 `Import` 和 `ImportFrom` 节点时，拥有最准确的上下文信息，理应由它来维护一个动态的“当前作用域符号表”。

### 目标
修改 `stitcher-python-analysis` 中的 `UsageScanVisitor`：
1.  引入 `self.active_symbols` 状态，初始化为传入的 `local_symbols`。
2.  在 `visit_Import` 和 `visit_ImportFrom` 中，动态解析导入语句，并将引入的本地名称（如别名）及其对应的绝对 FQN 注册到 `active_symbols` 中。
3.  更新 `visit_Attribute` 和 `visit_Name`，使其查询 `active_symbols` 而非静态的 `local_symbols`。

### 基本原理
通过让 Visitor 具备状态性（Stateful），我们模拟了 Python 解释器的行为：遇到导入语句时绑定名称。这使得后续的代码遍历能够基于上下文正确解析符号引用。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/analysis #task/object/usage-visitor #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 增强 UsageScanVisitor

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        file_path: Path,
        local_symbols: Dict[str, str],
        registry: UsageRegistry,
        current_module_fqn: Optional[str] = None,
        is_init_file: bool = False,
    ):
        self.file_path = file_path
        self.local_symbols = local_symbols
        self.registry = registry
        self.current_module_fqn = current_module_fqn
        self.is_init_file = is_init_file

        self.current_package = None
~~~~~
~~~~~python.new
    def __init__(
        self,
        file_path: Path,
        local_symbols: Dict[str, str],
        registry: UsageRegistry,
        current_module_fqn: Optional[str] = None,
        is_init_file: bool = False,
    ):
        self.file_path = file_path
        self.local_symbols = local_symbols
        # active_symbols starts with local definitions but grows as we encounter imports
        self.active_symbols = local_symbols.copy()
        self.registry = registry
        self.current_module_fqn = current_module_fqn
        self.is_init_file = is_init_file

        self.current_package = None
~~~~~

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.py
~~~~~
~~~~~python.old
    def visit_Name(self, node: cst.Name):
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn, ReferenceType.SYMBOL)
~~~~~
~~~~~python.new
    def visit_Name(self, node: cst.Name):
        target_fqn = self.active_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn, ReferenceType.SYMBOL)
~~~~~

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.py
~~~~~
~~~~~python.old
    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        for alias in node.names:
            absolute_module = get_full_name_for_node(alias.name)
            if absolute_module:
                self._register_node(
                    alias.name, absolute_module, ReferenceType.IMPORT_PATH
                )
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        absolute_module = None
        try:
            package_ctx = self.current_package if self.current_package else None
            absolute_module = get_absolute_module_from_package_for_import(
                package_ctx, node
            )
        except Exception:
            pass

        if absolute_module:
            if node.module:
                self._register_node(
                    node.module, absolute_module, ReferenceType.IMPORT_PATH
                )

            # Handle "from x import *"
            if isinstance(node.names, cst.ImportStar):
                return True

            for alias in node.names:
                if isinstance(alias, cst.ImportAlias):
                    name_node = alias.name
                    imported_name = get_full_name_for_node(name_node)
                    if imported_name:
                        full_fqn = f"{absolute_module}.{imported_name}"
                        self._register_node(name_node, full_fqn, ReferenceType.SYMBOL)
        return True

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        full_name = helpers.get_full_name_for_node(node)
        if not full_name:
            return True

        parts = full_name.split(".")
        if not parts:
            return True

        root_name = parts[0]
        root_fqn = self.local_symbols.get(root_name)

        if root_fqn:
            suffix = ".".join(parts[1:])
            absolute_fqn = f"{root_fqn}.{suffix}" if suffix else root_fqn
            self._register_node(node, absolute_fqn, ReferenceType.SYMBOL)

        return True
~~~~~
~~~~~python.new
    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        for alias in node.names:
            absolute_module = get_full_name_for_node(alias.name)
            if absolute_module:
                self._register_node(
                    alias.name, absolute_module, ReferenceType.IMPORT_PATH
                )
                
                # Update active_symbols
                # Case 1: import a.b.c as d -> local 'd' maps to 'a.b.c'
                if alias.asname:
                    if isinstance(alias.asname.name, cst.Name):
                        local_name = alias.asname.name.value
                        self.active_symbols[local_name] = absolute_module
                # Case 2: import a.b.c -> local 'a' maps to 'a'
                else:
                    top_level = absolute_module.split(".")[0]
                    self.active_symbols[top_level] = top_level

        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        absolute_module = None
        try:
            package_ctx = self.current_package if self.current_package else None
            absolute_module = get_absolute_module_from_package_for_import(
                package_ctx, node
            )
        except Exception:
            pass

        if absolute_module:
            if node.module:
                self._register_node(
                    node.module, absolute_module, ReferenceType.IMPORT_PATH
                )

            # Handle "from x import *"
            if isinstance(node.names, cst.ImportStar):
                return True

            for alias in node.names:
                if isinstance(alias, cst.ImportAlias):
                    name_node = alias.name
                    imported_name = get_full_name_for_node(name_node)
                    if imported_name:
                        full_fqn = f"{absolute_module}.{imported_name}"
                        self._register_node(name_node, full_fqn, ReferenceType.SYMBOL)
                        
                        # Update active_symbols
                        # from x import y as z -> local 'z' maps to 'x.y'
                        local_name = imported_name
                        if alias.asname and isinstance(alias.asname.name, cst.Name):
                            local_name = alias.asname.name.value
                        
                        self.active_symbols[local_name] = full_fqn
                        
        return True

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        full_name = helpers.get_full_name_for_node(node)
        if not full_name:
            return True

        parts = full_name.split(".")
        if not parts:
            return True

        root_name = parts[0]
        root_fqn = self.active_symbols.get(root_name)

        if root_fqn:
            suffix = ".".join(parts[1:])
            absolute_fqn = f"{root_fqn}.{suffix}" if suffix else root_fqn
            self._register_node(node, absolute_fqn, ReferenceType.SYMBOL)

        return True
~~~~~

### 下一步建议
重新运行 `packages/stitcher-python-adapter/tests/unit/test_index_adapter_references.py` 测试。期望现在 `do_work_refs` 能正确匹配到，因为 `utils` 已经被 `visit_ImportFrom` 正确解析并注册到了 `active_symbols` 中。
