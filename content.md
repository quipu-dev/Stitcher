## [WIP] fix(tests): 解决单元测试文件导入冲突并修复 PumpExecutor 的 Mock 语法错误

### 错误分析

1.  **文件名冲突**: Pytest 报告 `import file mismatch` 错误，因为在 `packages/stitcher-application/tests/unit/runners/` 下，`check` 和 `pump` 目录中都存在 `test_analyzer.py` 和 `test_runner.py` 文件。测试模块名在全局范围内必须是唯一的。
2.  **语法错误**: `packages/stitcher-application/tests/unit/runners/pump/test_executor.py` 中的一行代码尝试对一个属性链（`executor.root_path / "src/main.py".read_text.return_value`）进行赋值，这是无效的 Python 语法。

### 用户需求

要求修复这些错误，并使用 `move_file` 为文件创建唯一的名称。

### 目标

1.  将 `check` 和 `pump` 单元测试文件重命名以解决命名空间冲突。
2.  修复 `test_pump_executor.py` 中的 Mocking 语法，改用正确的方式来模拟文件读取。

### 基本原理

为了解决 Pytest 的导入冲突，我们将为每个测试文件添加一个反映其逻辑角色的前缀（例如 `check_` 或 `pump_`）。对于语法错误，我们将使用 `MagicMock` 和 `configure_mock` 方法来安全地模拟文件路径对象上的方法调用。

### 标签

#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/unit-tests #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重命名 Check 相关的测试文件

为 `check` 目录下的测试文件添加 `check_` 前缀。

~~~~~act
move_file
packages/stitcher-application/tests/unit/runners/check/test_analyzer.py
packages/stitcher-application/tests/unit/runners/check/test_check_analyzer.py
~~~~~

~~~~~act
move_file
packages/stitcher-application/tests/unit/runners/check/test_runner.py
packages/stitcher-application/tests/unit/runners/check/test_check_runner.py
~~~~~

#### Acts 2: 重命名 Pump 相关的测试文件

为 `pump` 目录下的测试文件添加 `pump_` 前缀。

~~~~~act
move_file
packages/stitcher-application/tests/unit/runners/pump/test_analyzer.py
packages/stitcher-application/tests/unit/runners/pump/test_pump_analyzer.py
~~~~~

~~~~~act
move_file
packages/stitcher-application/tests/unit/runners/pump/test_executor.py
packages/stitcher-application/tests/unit/runners/pump/test_pump_executor.py
~~~~~

~~~~~act
move_file
packages/stitcher-application/tests/unit/runners/pump/test_runner.py
packages/stitcher-application/tests/unit/runners/pump/test_pump_runner.py
~~~~~

#### Acts 3: 修复 PumpExecutor 的 Mocking 语法错误

修复 `test_pump_executor.py` 中的语法错误。正确的做法是使用 `MagicMock` 来模拟 `Path` 对象的 `read_text` 方法。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/runners/pump/test_pump_executor.py
~~~~~
~~~~~python.old
    # Mock transformer strip call
    executor.transformer.strip.return_value = "stripped content"
    
    # Mock read_text for the source file
    executor.root_path / "src/main.py".read_text.return_value = "original content"

    executor.execute([sample_module], decisions=decisions, tm=mock_tm, strip=True)
~~~~~
~~~~~python.new
    # Mock transformer strip call
    executor.transformer.strip.return_value = "stripped content"
    
    # Mock Path.read_text for the source file read in _execute_strip_jobs
    source_path = executor.root_path / "src/main.py"
    source_path.read_text.return_value = "original content"

    executor.execute([sample_module], decisions=decisions, tm=mock_tm, strip=True)
~~~~~

### 下一步建议

现在命名冲突和语法错误已经修复，Pytest 应该能够正确收集并运行这些单元测试。下一步，我建议：

1.  **运行测试**: 验证所有 `pump` 单元测试是否成功通过。
2.  **继续重构**: 如果测试成功，继续执行原计划的下一步：为 `InitRunner` 和 `TransformRunner` 添加单元测试。
