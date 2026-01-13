Of course. We have the graph and the algorithms; it's time to build the rules that use them to find architectural flaws.

This plan establishes the foundation for all future architectural rules by defining a new `ArchitectureRule` protocol. It then provides the first concrete implementation, `CircularDependencyRule`, which leverages our previously created `detect_circular_dependencies` algorithm. Crucially, this plan also updates the system's violation schema to recognize and correctly classify this new type of project-wide error.

## [WIP] feat: Implement architecture rules for project-wide analysis

### 用户需求

Following the roadmap, we must now implement the architectural rule layer. This involves creating a new rule protocol, implementing a `CircularDependencyRule` that detects import cycles, and ensuring this new type of violation is recognized by the system. Unit tests are required to validate the rule's logic.

### 评论

This is a significant step forward. We are moving beyond single-file consistency checks and into the realm of holistic, project-wide architectural validation. By defining a clear `ArchitectureRule` protocol, we create an extensible system for adding more complex checks in the future (e.g., layer violations, dependency constraints). The `CircularDependencyRule` provides immediate, high-value feedback to developers, preventing a common source of code brittleness and complexity. Integrating its violation type into the core schema ensures it will be treated as a first-class error throughout the application.

### 目标

1.  Create the directory structure for architecture rules: `stitcher/analysis/rules/architecture/`.
2.  Define a new `ArchitectureRule` protocol in `.../architecture/protocols.py`.
3.  Implement `CircularDependencyRule` in `.../architecture/circular_dependency.py`.
4.  Update `FileCheckResult` in `stitcher.analysis.schema.results` to classify circular dependency violations as errors.
5.  Create a unit test, `test_circular_dependency_rule.py`, to verify the rule's behavior.

### 基本原理

1.  **Directory and Protocol**: We will use `run_command` and `write_file` to create the new directories and the `protocols.py` file. This establishes a clean, extensible pattern for new rules.
2.  **Rule Implementation**: The `CircularDependencyRule` will implement the new protocol. Its `check` method will take a `DiGraph`, call `detect_circular_dependencies`, and transform each found cycle into a `Violation` object. The violation's context will contain a human-readable string representing the cycle path.
3.  **Schema Update**: A `patch_file` operation will be used to add the new semantic pointer (`L.check.architecture.circular_dependency`) to the `_ERROR_KINDS` set within the `FileCheckResult` dataclass. This ensures these violations are correctly counted and reported as errors.
4.  **Testing**: A new test file will be created. It will instantiate the `CircularDependencyRule` and test it against manually constructed `DiGraph` objects—one with a cycle and one without—to assert that violations are generated correctly and only when a cycle exists.

### 标签

#intent/build #intent/tooling #flow/ready #priority/high #comp/analysis #comp/tests #concept/graph #concept/rules #scope/core #ai/instruct #task/domain/analysis #task/object/architecture-rules #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Create Directory Structures

First, we create the necessary directories for the new rule and its test.

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-analysis/src/stitcher/analysis/rules/architecture
mkdir -p packages/stitcher-analysis/tests/unit/rules/architecture
~~~~~

#### Acts 2: Define `ArchitectureRule` Protocol

We define the contract for all architecture rules in a new `protocols.py` file.

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List
import networkx as nx

from stitcher.analysis.schema import Violation


class ArchitectureRule(Protocol):
    def check(self, graph: nx.DiGraph) -> List[Violation]: ...
~~~~~

#### Acts 3: Implement `CircularDependencyRule`

Now, we implement the first architecture rule for detecting circular dependencies.

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
~~~~~
~~~~~python
from typing import List
import networkx as nx
from dataclasses import dataclass

from needle.pointer import L
from stitcher.analysis.schema import Violation
from stitcher.analysis.graph.algorithms import detect_circular_dependencies
from .protocols import ArchitectureRule


@dataclass
class CircularDependencyRule(ArchitectureRule):
    def check(self, graph: nx.DiGraph) -> List[Violation]:
        violations: List[Violation] = []
        cycles = detect_circular_dependencies(graph)

        for cycle in cycles:
            # Create a human-readable representation of the cycle
            cycle_path = " -> ".join(cycle) + f" -> {cycle[0]}"

            # An architecture violation applies to the whole project, but we use
            # the first file in the cycle as the primary "location" for reporting.
            violations.append(
                Violation(
                    kind=L.check.architecture.circular_dependency,
                    fqn=cycle[0],
                    context={"cycle": cycle_path},
                )
            )
        return violations
~~~~~

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/__init__.py
~~~~~
~~~~~python
from .circular_dependency import CircularDependencyRule
from .protocols import ArchitectureRule

__all__ = ["CircularDependencyRule", "ArchitectureRule"]
~~~~~

#### Acts 4: Register New Violation as an Error

We update `FileCheckResult` to ensure our new violation is treated as a critical error.

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/schema/results.py
~~~~~
~~~~~python.old
    _ERROR_KINDS: Set[SemanticPointer] = field(
        default_factory=lambda: {
            L.check.issue.conflict,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.extra,
            L.check.issue.pending,
        },
        init=False,
        repr=False,
    )
~~~~~
~~~~~python.new
    _ERROR_KINDS: Set[SemanticPointer] = field(
        default_factory=lambda: {
            # Consistency Errors
            L.check.issue.conflict,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.extra,
            L.check.issue.pending,
            # Architecture Errors
            L.check.architecture.circular_dependency,
        },
        init=False,
        repr=False,
    )
~~~~~

#### Acts 5: Implement Unit Test for `CircularDependencyRule`

Finally, we create a test to verify the rule's logic.

~~~~~act
write_file
packages/stitcher-analysis/tests/unit/rules/architecture/test_circular_dependency_rule.py
~~~~~
~~~~~python
import networkx as nx

from needle.pointer import L
from stitcher.analysis.rules.architecture import CircularDependencyRule


def test_circular_dependency_rule_with_cycle():
    # 1. Arrange
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("a.py", "b.py"),
        ("b.py", "c.py"),
        ("c.py", "a.py"),
    ])
    rule = CircularDependencyRule()

    # 2. Act
    violations = rule.check(graph)

    # 3. Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.kind == L.check.architecture.circular_dependency
    assert violation.fqn in {"a.py", "b.py", "c.py"}  # Start node is arbitrary
    assert "cycle" in violation.context
    assert "a.py ->" in violation.context["cycle"]
    assert "b.py ->" in violation.context["cycle"]
    assert "c.py ->" in violation.context["cycle"]


def test_circular_dependency_rule_without_cycle():
    # 1. Arrange
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("a.py", "b.py"),
        ("b.py", "c.py"),
    ])
    rule = CircularDependencyRule()

    # 2. Act
    violations = rule.check(graph)

    # 3. Assert
    assert len(violations) == 0
~~~~~

### 下一步建议

我们已经成功地将图分析能力转化为一个具体的、可执行的架构规则。

现在，我们需要一个引擎来协调这一切。下一步是 **第 6 步：构建架构引擎 (Build Architecture Engine)**。我将创建一个 `ArchitectureEngine`，它会负责调用 `GraphBuilder` 来构建图，然后将图传递给我们刚刚创建的所有 `ArchitectureRule` 进行检查。如果你同意，我将开始制定此计划。
