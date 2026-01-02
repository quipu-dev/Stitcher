好的，我完全理解了问题所在。`strip` 命令目前的设计只考虑了模块、类和函数的文档字符串，但忽略了附加在变量（如 dataclass 字段）上的文档字符串。这确实是一个需要修复的缺陷。

根据您的要求，我的首要任务是创建一个单元测试来复现并锁定这个问题。这个测试在当前的代码库中应该会失败，一旦我们修复了 `strip` 的逻辑，它就应该通过。

我将生成一个计划，把这个新的单元测试添加到现有的测试文件中。

## [WIP] test: 为属性文档字符串的剥离功能添加单元测试

### 错误分析

用户提供的示例暴露了当前 `strip` 功能的一个实现缺陷。`strip` 命令依赖于 `StripperTransformer` (位于 `packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py`) 来遍历源代码的抽象语法树 (AST) 并移除文档字符串。

当前的 `StripperTransformer` 实现只重写了 `leave_ClassDef`、`leave_FunctionDef` 和 `leave_Module` 方法，这意味着它只能识别并处理这三种结构块直属的文档字符串。它缺少对 `Assign` (赋值) 和 `AnnAssign` (带类型注解的赋值) 节点的访问和处理逻辑，而变量和 dataclass 字段的文档字符串在语法层面是紧跟在这些赋值语句之后的。因此，转换器会直接跳过它们，导致剥离失败。

### 用户需求

用户发现 `strip` 命令无法移除 dataclass 或模块/类级别变量的文档字符串，并要求创建一个单元测试来复现此问题。

### 评论

这是一个非常有价值的发现。确保 `strip` 功能的完备性对于维持代码库的整洁至关重要，特别是在文档已经由 Stitcher 管理的情况下。创建一个失败的单元测试是遵循测试驱动开发 (TDD) 的最佳实践，它能确保我们后续的修复是准确且有效的。

### 目标

1.  在 `packages/stitcher-application/tests/integration/test_lifecycle_commands.py` 文件中添加一个新的集成测试用例。
2.  该测试用例将创建一个包含带文档字符串的类属性的 Python 源文件。
3.  测试将调用 `run_strip()` 命令。
4.  断言命令执行后，源文件中的属性文档字符串已被移除，而属性定义本身仍然存在。
5.  此测试在当前代码基础上运行时必须失败。

### 基本原理

我们将通过 `patch_file` 为现有的测试文件 `test_lifecycle_commands.py` 追加一个新的测试函数 `test_strip_command_removes_attribute_docstrings`。这个文件是测试 `strip` 和 `inject` 等核心生命周期命令的理想位置。新测试将使用 `WorkspaceFactory` 来构建一个包含问题的最小复现环境，然后执行 `strip` 操作并验证其输出，这能精确地捕获当前行为与预期行为之间的偏差。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #comp/runtime #concept/executor #ai/instruct #task/domain/testing #task/object/attribute-stripping #task/action/bug-reproduction #task/state/begin

---

### Script

#### Acts 1: 向生命周期命令测试文件添加属性剥离测试

我们将向 `test_lifecycle_commands.py` 文件追加一个新的测试用例，该用例专门验证对类属性文档字符串的剥离操作。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_lifecycle_commands.py
~~~~~
~~~~~python.old
def test_inject_command_injects_docstrings(tmp_path, monkeypatch):
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    initial_code = "def func(): pass"
    docs_data = {"func": "Injected docstring."}

    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, initial_code)
        .with_docs("src/main.stitcher.yaml", docs_data)
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_inject()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""Injected docstring."""' in final_code

    spy_bus.assert_id_called(L.inject.file.success)
    spy_bus.assert_id_called(L.inject.run.complete)
~~~~~
~~~~~python.new
def test_inject_command_injects_docstrings(tmp_path, monkeypatch):
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    initial_code = "def func(): pass"
    docs_data = {"func": "Injected docstring."}

    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, initial_code)
        .with_docs("src/main.stitcher.yaml", docs_data)
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_inject()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""Injected docstring."""' in final_code

    spy_bus.assert_id_called(L.inject.file.success)
    spy_bus.assert_id_called(L.inject.run.complete)


def test_strip_command_removes_attribute_docstrings(tmp_path, monkeypatch):
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    initial_code = dedent("""
    from dataclasses import dataclass

    @dataclass
    class MyData:
        attr: str
        \"\"\"Attr doc.\"\"\"
    """)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, initial_code)
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_strip()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""Attr doc."""' not in final_code
    assert "attr: str" in final_code  # Ensure the attribute itself was not removed

    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)
~~~~~

### 下一步建议

我们已经创建了复现问题的单元测试。下一步是运行测试套件，确认这个新测试会按预期失败。

确认失败后，我将提出一个计划来修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py` 中的 `StripperTransformer`。具体的修改将涉及添加对赋值节点（`Assign` 和 `AnnAssign`）的访问和处理逻辑，以正确识别并移除附着在变量和属性上的文档字符串。
