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