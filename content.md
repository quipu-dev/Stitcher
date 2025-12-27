## [WIP] fix(test): 修复集成测试中的路径断言错误

### 错误分析

测试 `test_app_run_multi_target` 失败，原因是断言的存根文件路径与实际生成路径不符。

1.  **逻辑推导**:
    *   **源文件**: `src/pkg_a/main.py`
    *   **逻辑路径推导**: `StitcherApp._derive_logical_path` 会剥离 `src` 目录，得到逻辑路径 `pkg_a/main.py`。这是为了确保生成的存根包保留正确的 Python 包结构。
    *   **输出路径计算**: `stub_path` 模式下，输出路径为 `root / config.stub_path / logical_path`。
    *   **配置**: 测试中设置 `stub_path = "typings/pkg_a"`。
    *   **实际结果**: `root / "typings/pkg_a" / "pkg_a/main.pyi"`。
    *   **错误断言**: 测试代码断言存在 `root / "typings/pkg_a/main.pyi"` (少了一层 `pkg_a`)。

2.  **结论**: `Stitcher` 的行为是正确且符合设计的（保留包结构），测试用例编写时忽略了包名目录的保留。

### 解决方案

修正 `tests/integration/test_end_to_end.py` 中的断言路径，使其包含包名目录。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/correction #task/state/continue

---
### Script

#### Acts 1: 修正 `test_end_to_end.py` 断言

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
    # 3. Assert
    # Check physical files
    assert (project_root / "typings/pkg_a/main.pyi").exists()
    assert (project_root / "typings/pkg_b/main.pyi").exists()

    # Check bus messages
~~~~~
~~~~~python.new
    # 3. Assert
    # Check physical files
    # Note: Stitcher preserves the package structure relative to 'src'.
    # So 'src/pkg_a/main.py' becomes 'pkg_a/main.pyi' inside the stub output directory.
    assert (project_root / "typings/pkg_a/pkg_a/main.pyi").exists()
    assert (project_root / "typings/pkg_b/pkg_b/main.pyi").exists()

    # Check bus messages
~~~~~
