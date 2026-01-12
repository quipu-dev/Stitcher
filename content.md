好的，这是一个很棒的架构重构提议。将 `PumpAnalyzer` 的职责迁移到 `stitcher-analysis` 包中，并将其重塑为一个 `PumpEngine`，这完全符合关注点分离（Separation of Concerns）的原则。`analysis` 包应该负责“是什么”和“为什么”（分析问题），而 `application` 包则负责“何时”和“如何”（编排流程）。

我将生成一个计划来实现这一重构。

## [WIP] refactor(pump): 将 PumpAnalyzer 提取到 stitcher-analysis 中的 PumpEngine

### 用户需求

将 `stitcher-application` 中的 `PumpAnalyzer` 迁移至 `stitcher-analysis` 包，并重构为一个新的 `PumpEngine`，使其与 `ConsistencyEngine` 的架构模式保持一致。

### 评论

这是一个高质量的架构改进。通过将 Pump 的分析逻辑从应用层下沉到分析层，我们增强了系统的模块化和内聚性。`PumpEngine` 将成为一个纯粹的分析组件，它接收一个 `AnalysisSubject` 并返回分析结果，而不关心上层的执行和交互逻辑。这使得我们的分层更加清晰，并为未来扩展分析能力奠定了坚实的基础。

### 目标

1.  在 `stitcher-analysis` 包内创建一个新的 `PumpEngine`，其职责是识别需要从源代码“抽取”到 YAML 的文档。
2.  将 `PumpAnalyzer` 的核心逻辑迁移到 `PumpEngine` 中，并重构其实现，使其依赖 `AnalysisSubject` 协议而不是具体的 `ModuleDef` 和服务管理器。
3.  更新 `stitcher-application` 中的 `PumpRunner`，使其依赖并调用新的 `PumpEngine`。
4.  删除 `stitcher-application` 中旧的 `PumpAnalyzer` 及其相关协议。
5.  确保整个应用的依赖注入和组件装配都更新以反映这一变化。

### 基本原理

当前的 `PumpAnalyzer` 位于应用层，但其核心功能——“识别源代码与文档之间的差异以确定是否需要同步”——本质上是一种分析任务，与 `ConsistencyEngine` 的职责类似。

为了遵循我们“分析与执行分离”的核心架构原则，我们将执行以下操作：
1.  **创建 `PumpEngine`**: 在 `stitcher.analysis.engines` 命名空间下创建一个新的 `PumpEngine`。它将遵循与其他引擎相同的模式：接受一个 `differ` 实例，并提供一个 `analyze(subject: AnalysisSubject)` 方法。
2.  **重构分析逻辑**: `PumpEngine` 的 `analyze` 方法将不再直接与 `IndexStore` 或 `SignatureManager` 交互。相反，它将利用 `AnalysisSubject` 提供的 `get_all_symbol_states()` 方法。`SymbolState` 对象已经封装了所有需要的信息（源码文档内容、YAML 文档内容、基线哈希等），这使得引擎的逻辑更加纯粹和可测试。
3.  **更新 `PumpRunner`**: `PumpRunner` 将保留在应用层，其职责是编排分析和执行。它将负责为每个 `ModuleDef` 创建一个 `ASTCheckSubjectAdapter`，然后将其传递给 `PumpEngine` 以获取分析结果（即需要处理的冲突）。
4.  **清理**: 完成迁移后，我们将删除应用层中所有与旧 `PumpAnalyzer` 相关的代码，完成重构。

这次重构将使 `stitcher-analysis` 成为所有“是什么”问题的权威来源，而 `stitcher-application` 则专注于处理“做什么”的决策。

### 标签
#intent/refine #flow/ready #priority/high #comp/analysis #comp/application #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/pump-engine #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 在 `stitcher-analysis` 中创建新的 `PumpEngine`

我们将首先创建 `PumpEngine` 的目录结构和核心实现文件。这个引擎将包含从旧 `PumpAnalyzer` 迁移并重构后的逻辑。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-analysis/src/stitcher/analysis/engines/pump
~~~~~
~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/engines/pump/__init__.py
~~~~~
~~~~~python
from .engine import PumpEngine, create_pump_engine

__all__ = ["PumpEngine", "create_pump_engine"]
~~~~~
~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/engines/pump/engine.py
~~~~~
~~~~~python
from typing import List
from dataclasses import dataclass

from needle.pointer import L
from stitcher.spec import DifferProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.common.services import Differ
from stitcher.analysis.protocols import AnalysisSubject


@dataclass
class PumpEngine:
    differ: DifferProtocol

    def analyze(self, subject: AnalysisSubject) -> List[InteractionContext]:
        """
        Analyzes the subject to find symbols with new or conflicting docstrings
        in the source code that should be "pumped" into the YAML documentation.
        """
        conflicts: List[InteractionContext] = []
        states = subject.get_all_symbol_states()

        for fqn, state in states.items():
            # A symbol is a candidate for pumping if it has a docstring in the source code.
            if not state.source_doc_content:
                continue

            # Case 1: New docstring (exists in code, not in YAML).
            # This is not a conflict, but a candidate for clean hydration.
            # The runner will handle this, the engine just needs to identify conflicts.
            if not state.exists_in_yaml:
                continue

            # Case 2: Conflict (exists in both, content differs).
            # We need to compare the summaries.
            yaml_ir = state.yaml_doc_ir
            yaml_summary = yaml_ir.summary if yaml_ir else ""
            src_summary = state.source_doc_content or ""

            if src_summary != yaml_summary:
                doc_diff = self.differ.generate_text_diff(
                    yaml_summary or "", src_summary or "", "yaml", "code"
                )
                conflicts.append(
                    InteractionContext(
                        file_path=subject.file_path,
                        fqn=fqn,
                        violation_type=L.check.issue.conflict,
                        doc_diff=doc_diff,
                    )
                )

        return conflicts


def create_pump_engine(differ: DifferProtocol | None = None) -> PumpEngine:
    effective_differ = differ or Differ()
    return PumpEngine(differ=effective_differ)
~~~~~

#### Acts 2: 将 `PumpEngine` 集成到 `analysis` 包的顶层命名空间

现在，我们将新的 `PumpEngine` 导出到 `stitcher.analysis.engines` 中。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/engines/__init__.py
~~~~~
~~~~~python.old
from .consistency import ConsistencyEngine, create_consistency_engine

__all__ = ["ConsistencyEngine", "create_consistency_engine"]
~~~~~
~~~~~python.new
from .consistency import ConsistencyEngine, create_consistency_engine
from .pump import PumpEngine, create_pump_engine

__all__ = ["ConsistencyEngine", "create_consistency_engine", "PumpEngine", "create_pump_engine"]
~~~~~

#### Acts 3: 移除旧的 `PumpAnalyzer` 协议

`PumpAnalyzerProtocol` 将被废弃，我们首先清空协议文件。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Dict
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.spec.interaction import InteractionContext
from stitcher.common.transaction import TransactionManager
from stitcher.app.types import PumpResult


class PumpExecutorProtocol(Protocol):
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult: ...
~~~~~

#### Acts 4: 更新 `PumpRunner` 以使用新的 `PumpEngine`

这是重构的核心部分。`PumpRunner` 现在将依赖 `PumpEngine`，并采用与 `CheckRunner` 类似的模式，通过 `ASTCheckSubjectAdapter` 来准备分析所需的数据。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/runner.py
~~~~~
~~~~~python
from typing import List

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    FingerprintStrategyProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionHandler
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager
from stitcher.analysis.engines import PumpEngine
from .protocols import PumpExecutorProtocol
from ..check.subject import ASTCheckSubjectAdapter


class PumpRunner:
    def __init__(
        self,
        pump_engine: PumpEngine,
        executor: PumpExecutorProtocol,
        interaction_handler: InteractionHandler | None,
        # Dependencies required for subject creation
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.pump_engine = pump_engine
        self.executor = executor
        self.interaction_handler = interaction_handler
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy

    def run_batch(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        tm: TransactionManager,
        strip: bool = False,
        force: bool = False,
        reconcile: bool = False,
    ) -> PumpResult:
        # --- Phase 1: Analysis ---
        all_conflicts = []
        # The runner is responsible for adapting ModuleDefs to AnalysisSubjects
        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                tm.root_path,
            )
            conflicts = self.pump_engine.analyze(subject)
            all_conflicts.extend(conflicts)

        # --- Phase 2: Decision ---
        decisions = {}
        if all_conflicts:
            handler = self.interaction_handler or NoOpInteractionHandler(
                hydrate_force=force, hydrate_reconcile=reconcile
            )
            chosen_actions = handler.process_interactive_session(all_conflicts)
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                decisions[context.fqn] = action

        # --- Phase 3: Execution ---
        # The executor still works with ModuleDefs, which is fine.
        return self.executor.execute(modules, decisions, tm, strip)
~~~~~

#### Acts 5: 更新应用组合根 (`core.py`)

我们需要在 `StitcherApp` 的构造函数中创建 `PumpEngine` 实例，并用它来初始化 `PumpRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from .runners.pump.analyzer import PumpAnalyzer
from .runners.pump.executor import PumpExecutor
~~~~~
~~~~~python.new
from .runners.pump.executor import PumpExecutor
from stitcher.analysis.engines import PumpEngine, create_pump_engine
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        pump_analyzer = PumpAnalyzer(
            self.doc_manager, self.sig_manager, self.index_store, self.differ
        )
        pump_executor = PumpExecutor(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.merger,
            self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            analyzer=pump_analyzer,
            executor=pump_executor,
            interaction_handler=interaction_handler,
        )
~~~~~
~~~~~python.new
        pump_engine = create_pump_engine(differ=self.differ)
        pump_executor = PumpExecutor(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.merger,
            self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            pump_engine=pump_engine,
            executor=pump_executor,
            interaction_handler=interaction_handler,
            # Pass dependencies needed for subject creation
            doc_manager=self.doc_manager,
            sig_manager=self.sig_manager,
            fingerprint_strategy=self.fingerprint_strategy,
        )
~~~~~

#### Acts 6: 删除旧的 `PumpAnalyzer` 实现文件

最后，我们删除已经不再使用的 `analyzer.py` 文件。

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/pump/analyzer.py
~~~~~
~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/pump/protocols.py
~~~~~

### 下一步建议

我们已经成功地将分析逻辑提取到了 `stitcher-analysis` 包中。下一步是验证我们的重构是否正确。
我建议：
1.  **运行测试**: 运行现有的测试套件，特别是与 `pump` 命令相关的测试，确保所有功能仍然按预期工作。
2.  **创建提交**: 如果测试通过，我将生成一个 `[COMMIT]` 计划来将这些架构改进固化到版本历史中。
