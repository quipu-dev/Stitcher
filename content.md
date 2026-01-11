简要回答
我们遇到了两个问题：一是 `ScopeAnalyzer` 漏掉了类名本身的注册导致 `KeyError`，二是 Linker 无法解析指向“模块”本身的引用（因为此前适配器没有为模块文件本身生成符号记录），且测试期望的 SURI 与文件系统实际布局不符。

本计划将修复这两个问题：首先修复作用域分析，其次增强 Python 适配器以生成模块级符号，最后修正集成测试的断言。

## [WIP] fix: 修复 ScopeAnalyzer 类注册并增强模块符号生成

### 错误分析
1.  **`KeyError: 'MyClass'`**:
    在 `packages/stitcher-python-analysis/src/stitcher/python/analysis/scope.py` 中，注册类的代码行 `# cls_fqn = register_local(cls.name)` 被注释掉了。这导致类名没有被添加到本地符号表中，后续查询时抛出错误。
2.  **`AssertionError: assert None == 'py://pkg.py'`**:
    *   **原因 1 (机制缺失)**: Linker 依赖 `symbols` 表来解析引用。之前 `PythonAdapter` 只提取了模块内部的函数/类/变量，没有为“模块本身”生成一条符号记录。因此，当代码 `import pkg` 时，Linker 找不到 `canonical_fqn="pkg"` 的符号。
    *   **原因 2 (测试错误)**: 测试环境创建了 `pkg/__init__.py`，但断言期望解析为 `py://pkg.py`。正确的 SURI 应该是 `py://pkg/__init__.py`。

### 用户需求
1.  修复 `ScopeAnalyzer` 以正确处理类定义。
2.  更新 `PythonAdapter`，使其在解析文件时，额外生成一条代表“模块/文件本身”的符号记录，以便 Linker 能解析模块导入。
3.  修正 `test_scanner_aliases.py` 中的断言。

### 评论
为模块本身生成符号（Symbol with kind='module'）是建立完整语义图谱的关键补充。这使得 `import numpy` 这样的语句能正确指向 `site-packages/numpy/__init__.py` (如果我们扫描了它) 或项目内的模块文件，消除了“文件”与“符号”之间的概念鸿沟。

### 目标
1.  修改 `scope.py`，取消注释类注册代码。
2.  修改 `index_adapter.py`，在提取符号列表时，始终添加一个 `kind='module'` 的根符号。
3.  修改 `test_scanner_aliases.py`，将期望值 `py://pkg.py` 改为 `py://pkg/__init__.py`。

### 基本原理
通过在 `symbols` 表中显式记录模块（Module）符号，我们利用现有的 Linker SQL 逻辑（基于 `canonical_fqn` 匹配）自然而然地支持了模块级引用的解析，无需编写特殊的“文件查找”逻辑。这保持了 Linker 的简洁性和统一性。

### 标签
#intent/fix #flow/ready #priority/high #comp/python-analysis #comp/python-adapter #comp/tests #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/linker #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 ScopeAnalyzer

取消对类名注册的注释。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/scope.py
~~~~~
~~~~~python.old
        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            # cls_fqn = register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
~~~~~
~~~~~python.new
        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
~~~~~

#### Acts 2: 增强 PythonAdapter 以生成模块符号

在 `_extract_symbols` 方法开头添加模块自身的符号记录。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
    def _extract_symbols(
        self, rel_path: str, module: ModuleDef, logical_module_fqn: str
    ) -> List[SymbolRecord]:
        symbols: List[SymbolRecord] = []

        # Helper to add symbol
        def add(
            name: str,
~~~~~
~~~~~python.new
    def _extract_symbols(
        self, rel_path: str, module: ModuleDef, logical_module_fqn: str
    ) -> List[SymbolRecord]:
        symbols: List[SymbolRecord] = []

        # 0. Module Symbol (The file/module itself)
        # This allows other files to import this module.
        module_name = logical_module_fqn.split(".")[-1]
        module_suri = SURIGenerator.for_file(rel_path)
        
        symbols.append(
            SymbolRecord(
                id=module_suri,
                name=module_name,
                kind="module",
                lineno=0,
                col_offset=0,
                end_lineno=0,
                end_col_offset=0,
                logical_path=None, # Module root has no logical path suffix
                canonical_fqn=logical_module_fqn,
                alias_target_fqn=None,
                alias_target_id=None,
                signature_hash=None,
            )
        )

        # Helper to add symbol
        def add(
            name: str,
~~~~~

#### Acts 3: 修正集成测试断言

将 `py://pkg.py` 修正为 `py://pkg/__init__.py`。

~~~~~act
patch_file
packages/stitcher-index/tests/integration/test_scanner_aliases.py
~~~~~
~~~~~python.old
    assert alias_pkg_defs.kind == "alias"
    # The target of 'import pkg.defs' is the 'pkg' module itself in this context
    assert alias_pkg_defs.alias_target_id == "py://pkg.py"

    # 3b. Verify References in main.py
    references = store.get_references_by_file(main_py_record.id)
~~~~~
~~~~~python.new
    assert alias_pkg_defs.kind == "alias"
    # The target of 'import pkg.defs' is the 'pkg' module itself in this context
    # Note: 'pkg' is a package directory containing __init__.py, so the SURI points to __init__.py
    assert alias_pkg_defs.alias_target_id == "py://pkg/__init__.py"

    # 3b. Verify References in main.py
    references = store.get_references_by_file(main_py_record.id)
~~~~~

### 下一步建议

重新运行测试。如果通过，我们将完成 Linker 的核心实现。接下来可以考虑：
1.  性能优化：在 `Linker.link()` 中添加 `BATCH_SIZE` 限制，避免在一个事务中更新过多行。
2.  死链报告：开发一个工具方法来查询所有 `target_id IS NULL` 的引用，用于诊断。
3.  开始 Phase 3：设计 Refactor 如何利用 Index DB。
