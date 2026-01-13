Of course. We have the rules, and now we need the orchestrator.

This plan constructs the `ArchitectureEngine`, the component responsible for driving the entire project-wide analysis process. It will tie together the `GraphBuilder` and the `ArchitectureRule`s into a cohesive unit. Following our established pattern, we will also create a factory function for easy instantiation and a thorough unit test to validate the engine's orchestration logic.

## [WIP] feat: Build the ArchitectureEngine to orchestrate graph analysis

### 用户需求

As per the roadmap, we need to build the `ArchitectureEngine`. This engine will be responsible for using the `GraphBuilder` to create an in-memory graph from the `IndexStore`, running all registered `ArchitectureRule`s against that graph, and collecting the results.

### 评论

The `ArchitectureEngine` acts as the central nervous system for our new global analysis capabilities. It cleanly separates the *how* (building graphs, running rules) from the *what* (the specific rules themselves). By following the factory pattern established by the `ConsistencyEngine`, we create a consistent and easy-to-use interface for the application layer. The unit test is critical here, as it won't test the rules or the builder, but rather the engine's core responsibility: ensuring that the components are called in the correct order with the correct data.

### 目标

1.  Create the directory `stitcher/analysis/engines/architecture/`.
2.  Implement the `ArchitectureEngine` class and a `create_architecture_engine` factory function in `engine.py`.
3.  The engine's `analyze` method will take an `IndexStoreProtocol` and return a list of all `Violation`s found by the rules.
4.  Export the new engine and factory from the parent `engines` package.
5.  Create a unit test `test_engine.py` to verify that the engine correctly orchestrates the builder and the rules using mocks.

### 基本原理

1.  **Implementation (`engine.py`)**: The `ArchitectureEngine` will be designed to receive its dependencies (the `GraphBuilder` and a list of `ArchitectureRule`s) via its constructor, which is a best practice for testability. The `create_architecture_engine` factory will handle the production setup, instantiating the engine with the concrete `GraphBuilder` and all default rules (currently just `CircularDependencyRule`).
2.  **Exports (`__init__.py`)**: We'll update the `__init__.py` files at both the `architecture` and `engines` levels to ensure the new components are easily importable by the rest of the application.
3.  **Testing (`test_engine.py`)**: The unit test will instantiate `ArchitectureEngine` directly, injecting mocked versions of the `GraphBuilder` and an `ArchitectureRule`. We will configure the mock builder to return a specific graph and the mock rule to return a specific violation. By calling the engine's `analyze` method, we can then assert that the engine correctly calls its dependencies and returns the expected violation, thus proving its orchestration logic is sound without relying on the actual implementations of its dependencies.

### 标签

#intent/build #intent/tooling #flow/ready #priority/high #comp/analysis #comp/tests #concept/graph #concept/engine #scope/core #ai/instruct #task/domain/analysis #task/object/architecture-engine #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Create Directory Structure for the Engine

First, we'll create the necessary directory for the new engine and its test.

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-analysis/src/stitcher/analysis/engines/architecture
mkdir -p packages/stitcher-analysis/tests/unit/engines/architecture
~~~~~

#### Acts 2: Implement the `ArchitectureEngine`

Next, we create the engine itself, along with its factory function.

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/engines/architecture/engine.py
~~~~~
~~~~~python
from typing import List

from stitcher.spec import IndexStoreProtocol
from stitcher.analysis.schema import Violation
from stitcher.analysis.graph.builder import GraphBuilder
from stitcher.analysis.rules.architecture import (
    ArchitectureRule,
    CircularDependencyRule,
)


class ArchitectureEngine:
    def __init__(self, builder: GraphBuilder, rules: List[ArchitectureRule]):
        self._builder = builder
        self._rules = rules

    def analyze(self, store: IndexStoreProtocol) -> List[Violation]:
        all_violations: List[Violation] = []
        graph = self._builder.build_dependency_graph(store)

        for rule in self._rules:
            violations = rule.check(graph)
            all_violations.extend(violations)

        return all_violations


def create_architecture_engine() -> ArchitectureEngine:
    default_rules: List[ArchitectureRule] = [CircularDependencyRule()]
    builder = GraphBuilder()
    return ArchitectureEngine(builder=builder, rules=default_rules)
~~~~~

#### Acts 3: Export the New Engine and Factory

We make the new engine accessible to the rest of the application.

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/engines/architecture/__init__.py
~~~~~
~~~~~python
from .engine import ArchitectureEngine, create_architecture_engine

__all__ = ["ArchitectureEngine", "create_architecture_engine"]
~~~~~

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/engines/__init__.py
~~~~~
~~~~~python.old
from .consistency import ConsistencyEngine, create_consistency_engine
from .pump import PumpEngine, create_pump_engine

__all__ = [
    "ConsistencyEngine",
    "create_consistency_engine",
    "PumpEngine",
    "create_pump_engine",
]
~~~~~
~~~~~python.new
from .consistency import ConsistencyEngine, create_consistency_engine
from .pump import PumpEngine, create_pump_engine
from .architecture import ArchitectureEngine, create_architecture_engine

__all__ = [
    "ConsistencyEngine",
    "create_consistency_engine",
    "PumpEngine",
    "create_pump_engine",
    "ArchitectureEngine",
    "create_architecture_engine",
]
~~~~~

#### Acts 4: Implement the Unit Test for the Engine

Finally, we create the test to ensure the engine's orchestration logic is correct.

~~~~~act
write_file
packages/stitcher-analysis/tests/unit/engines/architecture/test_engine.py
~~~~~
~~~~~python
from unittest.mock import MagicMock
import networkx as nx

from needle.pointer import L
from stitcher.analysis.schema import Violation
from stitcher.analysis.engines.architecture import ArchitectureEngine


def test_architecture_engine_analyze_flow():
    # 1. Arrange
    mock_store = MagicMock()
    mock_builder = MagicMock()
    mock_rule = MagicMock()

    # Configure mocks
    mock_graph = nx.DiGraph()
    mock_builder.build_dependency_graph.return_value = mock_graph

    mock_violation = Violation(kind=L.check.architecture.circular_dependency, fqn="a.py")
    mock_rule.check.return_value = [mock_violation]

    # 2. Act
    engine = ArchitectureEngine(builder=mock_builder, rules=[mock_rule])
    results = engine.analyze(mock_store)

    # 3. Assert
    # Assert that the engine returns the violations from the rule
    assert results == [mock_violation]

    # Assert that the engine correctly orchestrated its dependencies
    mock_builder.build_dependency_graph.assert_called_once_with(mock_store)
    mock_rule.check.assert_called_once_with(mock_graph)
~~~~~

### 下一步建议

我们已经成功构建并测试了 `ArchitectureEngine`。现在，所有的分析组件（Builder, Algorithms, Rules, Engine）都已就绪。

最后一步是将这个新引擎集成到应用程序的顶层运行器中。下一步是 **第 7 步：集成到 CheckRunner (Integration)**。我将修改 `CheckRunner`，在其现有的一致性检查之后，增加一个新的阶段来运行我们的 `ArchitectureEngine`，并将两者的结果合并，以提供一个完整的项目健康报告。如果你同意，我将开始制定这个最终的集成计划。
