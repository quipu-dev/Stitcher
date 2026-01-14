你的诊断非常准确。由于我们重构了核心算法和报告器的数据流，相关的单元测试也必须同步更新，否则它们就会因为接口不匹配而失败。

这是一个好现象，它证明了测试套件正在有效地捕捉接口契约的变化。

我将生成一个计划来修复这两个测试文件，使它们与新的实现保持一致。

## [WIP] fix(tests): 更新单元测试以匹配新的算法和报告器接口

### 错误分析

1.  **`test_algorithms.py`**: 此测试失败是因为 `detect_circular_dependencies` 的返回值已从一个简单的环路列表 (`List[List[str]]`) 变更为一个更丰富的结构化列表 (`List[Dict]`)，其中每个字典都包含了 SCC 的节点集和其内部的环路。测试中的断言逻辑没有相应更新。
2.  **`test_check_runner.py`**: 此测试失败是因为 `CheckRunner.report()` 方法的签名已从 `report(results)` 更改为 `report(file_results, arch_violations)`，以支持分离的报告逻辑。测试中的调用和 Mock 断言仍然使用旧的单参数签名。

### 用户需求

修复因近期重构而失败的单元测试，确保测试套件恢复到通过状态。

### 评论

这是一个标准的“重构-测试-修复”循环。修复这些测试不仅能让我们的 CI 重新变绿，还能将新的接口契约固化下来，确保未来的开发者能够理解并遵循正确的使用方式。

### 目标

1.  修改 `test_algorithms.py`，使其能够正确解析 `detect_circular_dependencies` 返回的新数据结构，并对 `scc` 和 `cycles` 键进行断言。
2.  修改 `test_check_runner.py`，更新对 `runner.report()` 的调用和 `mock_reporter.report.assert_called_once_with()` 的断言，为 `arch_violations` 参数传递一个空的列表。

### 基本原理

我们将对测试用例进行精确的手术刀式修改：
*   在算法测试中，我们将断言从检查一个扁平列表改为检查一个包含字典的列表，验证其内部结构是否符合预期。
*   在 Runner 测试中，我们将在所有调用点补全缺失的 `arch_violations` 参数，因为在这个单元测试的上下文中，我们不关心架构违规，所以传递一个空列表是完全合适的。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/refine #task/state/continue

---

### Script

#### Acts 1: 修复算法单元测试

更新 `test_detect_circular_dependencies` 以适应新的返回值结构。

~~~~~act
patch_file
packages/stitcher-analysis/tests/unit/graph/test_algorithms.py
~~~~~
~~~~~python.old
def test_detect_circular_dependencies():
    # 1. Arrange: Create a graph with a known cycle
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
            ("c.py", "a.py"),  # Cycle: a -> b -> c -> a
            ("d.py", "a.py"),  # Not part of cycle
        ]
    )

    # 2. Act
    cycles = detect_circular_dependencies(graph)

    # 3. Assert
    assert len(cycles) == 1
    # networkx can start the cycle from any node, so we sort to have a stable check
    assert sorted(cycles[0]) == ["a.py", "b.py", "c.py"]
~~~~~
~~~~~python.new
def test_detect_circular_dependencies():
    # 1. Arrange: Create a graph with a known cycle
    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("a.py", "b.py"),
            ("b.py", "c.py"),
            ("c.py", "a.py"),  # Cycle: a -> b -> c -> a
            ("d.py", "a.py"),  # Not part of cycle
        ]
    )

    # 2. Act
    scc_results = detect_circular_dependencies(graph)

    # 3. Assert
    # We expect one SCC with cycles
    assert len(scc_results) == 1
    result = scc_results[0]

    # Check the identified SCC nodes
    assert sorted(list(result["scc"])) == ["a.py", "b.py", "c.py"]

    # Check the cycles found within that SCC
    assert len(result["cycles"]) == 1
    # networkx can start the cycle from any node, so we sort to have a stable check
    assert sorted(result["cycles"][0]) == ["a.py", "b.py", "c.py"]
~~~~~

#### Acts 2: 修复 Runner 单元测试

更新 `test_check_runner.py` 中对 `report` 方法的调用和断言。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/runners/check/test_check_runner.py
~~~~~
~~~~~python.old
    # 继续执行工作流
    runner.auto_reconcile_docs(results, mock_modules)
    resolution_success = runner.resolve_conflicts(results, conflicts)
    report_success = runner.report(results)

    # 验证与 mock 的交互
    mock_engine.analyze.assert_called_once()
    mock_resolver.auto_reconcile_docs.assert_called_once_with(results, mock_modules)
    mock_resolver.resolve_conflicts.assert_called_once_with(
        results, conflicts, force_relink=False, reconcile=False
    )
    mock_reporter.report.assert_called_once_with(results)
~~~~~
~~~~~python.new
    # 继续执行工作流
    runner.auto_reconcile_docs(results, mock_modules)
    resolution_success = runner.resolve_conflicts(results, conflicts)
    report_success = runner.report(results, [])

    # 验证与 mock 的交互
    mock_engine.analyze.assert_called_once()
    mock_resolver.auto_reconcile_docs.assert_called_once_with(results, mock_modules)
    mock_resolver.resolve_conflicts.assert_called_once_with(
        results, conflicts, force_relink=False, reconcile=False
    )
    mock_reporter.report.assert_called_once_with(results, [])
~~~~~

### 下一步建议

测试已修复。请执行此计划，然后可以安全地将所有相关的改进作为一个完整的逻辑单元进行提交。
