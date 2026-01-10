好的，我们来执行这个重构计划。

将测试文件归类到它们所属的正确包和目录中，是维护一个清晰、可维护的 monorepo 的关键一步。这完全符合我们的**高保真工程公理 (HFEA)** 和 **Monorepo 测试架构**原则。

我将生成一个计划来移动这些文件。

## [WIP] test: 重构测试文件以遵循 monorepo 架构

### 用户需求

根据代码审核的结果，需要将 `stitcher-python-adapter` 和 `stitcher-python-analysis` 包中的测试文件重新组织，使其严格遵循“测试与代码共存”和“单元/集成测试分离”的原则。

### 评论

这是一个对开发者体验 (DX) 至关重要的重构。当前混乱的测试布局增加了认知负荷，使得定位和执行特定组件的测试变得困难。通过这次重构，我们将恢复架构的清晰性，并为未来的开发提供一个稳定、可预测的测试结构。

### 目标

1.  将所有用于测试 `stitcher-python-analysis` 功能但错误放置在 `stitcher-python-adapter` 中的测试文件，移动到 `stitcher-python-analysis/tests/` 目录下。
2.  在 `stitcher-python-adapter` 内部，将不属于单元测试的测试文件（如集成测试）从 `tests/` 根目录或 `tests/unit/` 移动到 `tests/integration/`。
3.  创建所有必需的子目录以支持新的文件结构。

### 基本原理

本计划严格遵循 `d3-principle-pytest-monorepo-architecture-D3-P1` 规范。该规范强制要求测试用例与其验证的代码在物理上位于同一个包内，并明确区分 `unit` 和 `integration` 测试。通过执行 `move_file` 操作，我们将纠正当前对该规范的偏离，从而提高代码库的内聚性和可维护性。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-organization #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建新的测试目录结构

首先，我们一次性创建所有需要的新目录，为文件移动做好准备。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-python-analysis/tests/unit/cst
mkdir -p packages/stitcher-python-analysis/tests/unit/griffe
mkdir -p packages/stitcher-python-analysis/tests/integration
mkdir -p packages/stitcher-python-adapter/tests/integration
~~~~~

#### Acts 2: 将 analysis 包的测试移回原位

这些测试文件验证的是 `stitcher-python-analysis` 的功能，必须移回该包内。

~~~~~act
move_file
packages/stitcher-python-adapter/tests/unit/test_parser.py
packages/stitcher-python-analysis/tests/unit/cst/test_visitors.py
~~~~~

~~~~~act
move_file
packages/stitcher-python-adapter/tests/unit/test_griffe_parser.py
packages/stitcher-python-analysis/tests/unit/griffe/test_parser.py
~~~~~

~~~~~act
move_file
packages/stitcher-python-adapter/tests/integration/test_griffe_parsing_bugs.py
packages/stitcher-python-analysis/tests/unit/griffe/test_parser_bugs.py
~~~~~

~~~~~act
move_file
packages/stitcher-python-adapter/tests/integration/test_griffe_resolution.py
packages/stitcher-python-analysis/tests/integration/test_griffe_resolution.py
~~~~~

#### Acts 3: 在 adapter 包内部重分类测试

这些测试属于集成测试，因为它们验证了多个组件的协同工作，需要被移动到 `integration` 目录。

~~~~~act
move_file
packages/stitcher-python-adapter/tests/test_index_adapter.py
packages/stitcher-python-adapter/tests/integration/test_index_adapter.py
~~~~~

~~~~~act
move_file
packages/stitcher-python-adapter/tests/unit/test_index_adapter_references.py
packages/stitcher-python-adapter/tests/integration/test_index_adapter_references.py
~~~~~

### 下一步建议

测试文件已经归位。现在，`stitcher-python-adapter` 和 `stitcher-python-analysis` 之间的边界因为测试文件的分离而变得更加清晰。

下一个关键步骤是**彻底消除 `stitcher-python-adapter` 中存在的冗余代理模块**，完成两个包在实现层面的解耦。我建议我们下一步执行以下操作：
1.  删除 `stitcher-python-adapter` 中的 `griffe_parser.py`, `parser.py` 和 `transformer.py`。
2.  更新代码库中所有对这些已删除模块的引用，使其直接指向 `stitcher-python-analysis` 中的原始实现。
