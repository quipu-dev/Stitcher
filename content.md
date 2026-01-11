您是对的，测试如期失败，并且精准地暴露了问题的根源。

`assert not True` 的失败信息表明，`app.run_check()` 错误地返回了 `True`（表示成功），而我们的测试期望它返回 `False`（因为我们故意没有为本地定义的函数和类提供文档）。

这揭示了一个比预期更深层次的问题：`check` 命令不仅可能错误地报告导入的符号，在当前情况下，它甚至完全没有检测到**任何**缺失的文档，无论是对导入的符号还是对我们本地定义的符号。

问题的根源在于 `IndexCheckSubjectAdapter`。这个适配器负责从新的语义索引（数据库）中读取信息，并将其转换为 `CheckAnalyzer` 所能理解的格式。

当前，它在从数据库读取符号列表时，并未区分一个符号是**在文件中定义的**（如 `my_public_function`）还是仅仅**被导入的**（如 `os`, `Path`）。它将所有在索引中与该文件关联的符号都视为本地符号。

幸运的是，语义索引在存储符号时，会用一个 `kind` 字段来标记其类型。一个被导入的符号（例如 `from pathlib import Path`）会被标记为 `kind='alias'`。而一个函数定义则会被标记为 `kind='function'`。

我将修改 `IndexCheckSubjectAdapter` 的逻辑。在构建 `SymbolState` 的“代码中是否存在” (`exists_in_code`) 这个状态时，我会明确地过滤掉所有 `kind` 为 `'alias'` 的符号。

这样一来：
1.  `os`, `Path` 等导入符号将因为 `kind='alias'` 而被忽略，`exists_in_code` 会被视为 `False`，从而不会被报告为“文档缺失”。
2.  `my_public_function` 等本地定义的符号 `kind` 为 `'function'`，不会被过滤，`exists_in_code` 会是 `True`。由于它没有文档，`CheckAnalyzer` 会正确地将其标记为“文档缺失”。
3.  `run_check()` 会因为检测到错误而返回 `False`，我们的测试 `assert not success` 将会通过。

这将一举解决所有问题。

## [WIP] fix: Differentiate defined vs. imported symbols in check runner

### 用户需求

`stitcher check` 命令必须只对其在模块内部定义的符号进行文档检查，而完全忽略所有通过 `import` 语句引入的外部符号。

### 错误分析

集成测试 `test_check_does_not_report_imports_as_missing_docs` 的失败（`assert not True`）表明，`app.run_check()` 错误地返回了 `True`。这是因为 `IndexCheckSubjectAdapter` 在从数据库读取符号信息时，没有利用 `symbol.kind` 字段来区分本地定义（如 `kind='function'`）和导入的别名（`kind='alias'`）。因此，它构建的符号状态图谱是不准确的，导致 `CheckAnalyzer` 无法正确识别出任何缺失文档的本地符号。

### 评论

这是一个至关重要的正确性修复。通过利用语义索引提供的 `kind` 字段，我们能够以确定性的方式解决这个问题，确保 `check` 命令的输出既准确又信噪比高。

### 目标

1.  修改 `IndexCheckSubjectAdapter.get_all_symbol_states` 方法。
2.  在处理从数据库查询到的符号列表时，增加一个过滤条件：只将 `kind` 不为 `'alias'` 的符号视为在代码中实际“存在”的定义。

### 基本原理

通过在 `IndexCheckSubjectAdapter` 中增加 `if sym.kind != "alias"` 的判断，我们可以精确地将符号分为两类：在模块作用域内创建的定义，以及指向外部定义的引用（即导入）。`check` 命令的逻辑只应关注前者。此修改将校准 `SymbolState` 的构建逻辑，使其与 `CheckAnalyzer` 的期望相符，从而修复该缺陷并使测试通过。

### 标签

#intent/fix #flow/ready #priority/critical #comp/app #concept/state #task/domain/testing #task/object/check-command #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `IndexCheckSubjectAdapter`

我将直接修改 `subject.py` 文件，在构建 `symbol_map` 时加入对 `sym.kind` 的判断。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
        # 2. Map symbols for easy lookup
        symbol_map: Dict[str, SymbolRecord] = {}
        module_symbol: Optional[SymbolRecord] = None
        for sym in symbols_from_db:
            if sym.kind == "module":
                module_symbol = sym
            elif sym.logical_path:
                symbol_map[sym.logical_path] = sym
~~~~~
~~~~~python.new
        # 2. Map symbols for easy lookup
        symbol_map: Dict[str, SymbolRecord] = {}
        module_symbol: Optional[SymbolRecord] = None
        for sym in symbols_from_db:
            if sym.kind == "module":
                module_symbol = sym
            # CRITICAL: Only consider symbols that are definitions within this file,
            # not aliases (imports).
            elif sym.logical_path and sym.kind != "alias":
                symbol_map[sym.logical_path] = sym
~~~~~

### 下一步建议

现在我已经应用了修复。我将重新运行测试。这一次，测试应该会成功通过，因为 `check` 命令现在能够正确识别出 `my_public_function` 和 `MyPublicClass` 缺少文档，从而返回 `False`，满足 `assert not success` 的断言。
