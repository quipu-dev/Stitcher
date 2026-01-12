Of course. While `PumpRunner` doesn't instantiate as many distinct sub-components as `CheckRunner` did, its core issue is a monolithic `run_batch` method that violates the Single Responsibility Principle. We will apply the same dependency injection pattern by decomposing this large method into logical, testable components (`Analyzer`, `Executor`) and injecting them into a simplified `PumpRunner`.

## [WIP] refactor: Decompose monolithic PumpRunner into injectable components

### 用户需求
The user wants to apply the same dependency injection and modularization principles to `PumpRunner` that were successfully applied to `CheckRunner`, in order to improve its testability and maintainability.

### 评论
This is an excellent refactoring step. The current `PumpRunner.run_batch` method is a "god method" that handles analysis, decision-making, planning, and execution all in one place. By breaking it down into distinct `PumpAnalyzer` and `PumpExecutor` components, we create a much clearer separation of concerns. The `PumpRunner` will be transformed into a clean orchestrator, making the entire "pump" workflow easier to understand, test, and evolve.

### 目标
1.  **Define Protocols**: Create `pump/protocols.py` to define `PumpAnalyzerProtocol` and `PumpExecutorProtocol`.
2.  **Create Analyzer**: Implement `PumpAnalyzer` by extracting the conflict-detection logic from the beginning of `run_batch`.
3.  **Create Executor**: Implement `PumpExecutor` by extracting the transaction-building and stripping logic from the latter half of `run_batch`.
4.  **Refactor `PumpRunner`**: Simplify `PumpRunner` into a high-level orchestrator that coordinates the analyzer, interaction handler, and executor. Its constructor will now accept these components via DI.
5.  **Update Composition Root**: Modify `StitcherApp` to instantiate and inject the new `PumpAnalyzer` and `PumpExecutor` into the `PumpRunner`.

### 基本原理
This plan applies the **Single Responsibility Principle (SRP)** to decompose the complex `PumpRunner`. The `Analyzer` is responsible for "what needs to be done?", the `InteractionHandler` for "what should be done?", and the `Executor` for "how to do it?". The `PumpRunner` itself only orchestrates this flow. This adheres to the **Dependency Injection** pattern, where `StitcherApp` acts as the **Composition Root** that wires these components together.

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/interfaces #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Create Protocols and New Runner Directory

First, we establish the directory structure and the contracts for our new components.

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-application/src/stitcher/app/runners/pump
mv packages/stitcher-application/src/stitcher/app/runners/pump.py packages/stitcher-application/src/stitcher/app/runners/pump/runner.py
touch packages/stitcher-application/src/stitcher/app/runners/pump/__init__.py
~~~~~

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
from stitcher.config import StitcherConfig


class PumpAnalyzerProtocol(Protocol):
    def analyze(
        self, modules: List[ModuleDef]
    ) -> List[InteractionContext]: ...


class PumpExecutorProtocol(Protocol):
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult: ...
~~~~~

#### Acts 2: Implement the PumpAnalyzer

We extract the analysis logic into its own dedicated class.

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/analyzer.py
~~~~~
~~~~~python
from typing import Dict, List

from stitcher.spec import (
    ModuleDef,
    ConflictType,
    DocstringIR,
    DifferProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext


class PumpAnalyzer:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        index_store: IndexStoreProtocol,
        differ: DifferProtocol,
    ):
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.index_store = index_store
        self.differ = differ

    def _get_dirty_source_docs(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        actual_symbols = self.index_store.get_symbols_by_file_path(module.file_path)
        actual_map = {
            s.logical_path: s for s in actual_symbols if s.logical_path is not None
        }

        baseline_hashes = self.sig_manager.load_composite_hashes(module.file_path)

        dirty_fqns: set[str] = set()
        all_fqns = set(actual_map.keys()) | set(baseline_hashes.keys())

        for fqn in all_fqns:
            actual = actual_map.get(fqn)
            baseline = baseline_hashes.get(fqn)

            actual_hash = actual.docstring_hash if actual else None
            baseline_hash = (
                baseline.get("baseline_code_docstring_hash") if baseline else None
            )

            if actual_hash != baseline_hash:
                dirty_fqns.add(fqn)

        if not dirty_fqns:
            return {}

        all_source_docs = self.doc_manager.flatten_module_docs(module)
        return {
            fqn: doc for fqn, doc in all_source_docs.items() if fqn in dirty_fqns
        }

    def analyze(
        self, modules: List[ModuleDef]
    ) -> List[InteractionContext]:
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            dirty_docs = self._get_dirty_source_docs(module)
            if not dirty_docs:
                continue
            
            res = self.doc_manager.hydrate_module(
                module, dry_run=True, source_docs_override=dirty_docs
            )
            if not res["success"]:
                source_docs = self.doc_manager.flatten_module_docs(module)
                yaml_docs = self.doc_manager.load_docs_for_module(module)
                for key in res["conflicts"]:
                    yaml_summary = yaml_docs[key].summary if key in yaml_docs else ""
                    src_summary = source_docs[key].summary if key in source_docs else ""
                    doc_diff = self.differ.generate_text_diff(
                        yaml_summary or "", src_summary or "", "yaml", "code"
                    )
                    all_conflicts.append(
                        InteractionContext(
                            module.file_path,
                            key,
                            ConflictType.DOC_CONTENT_CONFLICT,
                            doc_diff=doc_diff,
                        )
                    )
        return all_conflicts
~~~~~

#### Acts 3: Implement the PumpExecutor

Next, we extract the execution and transaction logic.

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/executor.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    DocstringIR,
    DocstringMergerProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.app.types import PumpResult
from stitcher.common.transaction import TransactionManager


class PumpExecutor:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        transformer: LanguageTransformerProtocol,
        merger: DocstringMergerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.merger = merger
        self.fingerprint_strategy = fingerprint_strategy

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            fingerprints[cls.name] = self.fingerprint_strategy.compute(cls)
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def _generate_execution_plan(
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
        source_docs: Dict[str, DocstringIR],
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)
            if decision != ResolutionAction.SKIP:
                exec_plan.update_code_fingerprint = True
                if decision == ResolutionAction.HYDRATE_OVERWRITE or (
                    decision is None and has_source_doc
                ):
                    exec_plan.hydrate_yaml = True
                    exec_plan.update_doc_fingerprint = True
                if strip_requested and (
                    decision == ResolutionAction.HYDRATE_OVERWRITE
                    or decision == ResolutionAction.HYDRATE_KEEP_EXISTING
                    or (decision is None and has_source_doc)
                ):
                    exec_plan.strip_source_docstring = True
            plan[fqn] = exec_plan
        return plan

    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult:
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        for module in modules:
            source_docs = self.doc_manager.flatten_module_docs(module)
            file_plan = self._generate_execution_plan(
                module, decisions, strip, source_docs
            )
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module.file_path)
            current_fingerprints = self._compute_fingerprints(module)

            new_yaml_docs = current_yaml_docs.copy()
            new_hashes = copy.deepcopy(stored_hashes)

            file_had_updates, file_has_errors, file_has_redundancy = False, False, False
            updated_keys_in_file, reconciled_keys_in_file = [], []

            for fqn, plan in file_plan.items():
                if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                    unresolved_conflicts_count += 1
                    file_has_errors = True
                    bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                    continue

                if plan.hydrate_yaml and fqn in source_docs:
                    src_ir, existing_ir = source_docs[fqn], new_yaml_docs.get(fqn)
                    merged_ir = self.merger.merge(existing_ir, src_ir)
                    if existing_ir != merged_ir:
                        new_yaml_docs[fqn] = merged_ir
                        updated_keys_in_file.append(fqn)
                        file_had_updates = True

                fp = new_hashes.get(fqn) or Fingerprint()
                fqn_was_updated = False
                if plan.update_code_fingerprint:
                    current_fp = current_fingerprints.get(fqn, Fingerprint())
                    if "current_code_structure_hash" in current_fp:
                        fp["baseline_code_structure_hash"] = current_fp["current_code_structure_hash"]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp["current_code_signature_text"]
                    fqn_was_updated = True

                if plan.update_doc_fingerprint and fqn in source_docs:
                    ir_to_save = new_yaml_docs.get(fqn)
                    if ir_to_save:
                        fp["baseline_yaml_content_hash"] = self.doc_manager.compute_ir_hash(ir_to_save)
                        fqn_was_updated = True

                if fqn_was_updated: new_hashes[fqn] = fp
                if fqn in decisions and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING:
                    reconciled_keys_in_file.append(fqn)
                if plan.strip_source_docstring: strip_jobs[module.file_path].append(fqn)
                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            if not file_has_errors:
                if file_had_updates:
                    final_data = {k: self.doc_manager.serialize_ir(v) for k, v in new_yaml_docs.items()}
                    doc_path = (self.root_path / module.file_path).with_suffix(".stitcher.yaml")
                    yaml_content = self.doc_manager.dump_data(final_data)
                    tm.add_write(str(doc_path.relative_to(self.root_path)), yaml_content)
                
                if new_hashes != stored_hashes:
                    sig_path = self.sig_manager.get_signature_path(module.file_path)
                    rel_sig_path = str(sig_path.relative_to(self.root_path))
                    if not new_hashes:
                        if sig_path.exists(): tm.add_delete_file(rel_sig_path)
                    else:
                        sig_content = self.sig_manager.serialize_hashes(module.file_path, new_hashes)
                        tm.add_write(rel_sig_path, sig_content)

                if file_has_redundancy:
                    redundant_files_list.append(self.root_path / module.file_path)

            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(L.pump.file.success, path=module.file_path, count=len(updated_keys_in_file))
            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(L.pump.info.reconciled, path=module.file_path, count=len(reconciled_keys_in_file))

        if strip_jobs:
            self._execute_strip_jobs(strip_jobs, tm)

        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)
        
        has_activity = (total_updated_keys > 0) or strip_jobs
        if not has_activity: bus.info(L.pump.run.no_changes)
        else: bus.success(L.pump.run.complete, count=total_updated_keys)
        return PumpResult(success=True, redundant_files=redundant_files_list)

    def _execute_strip_jobs(self, strip_jobs: Dict[str, List[str]], tm: TransactionManager):
        total_stripped_files = 0
        for file_path, whitelist in strip_jobs.items():
            source_path = self.root_path / file_path
            if not whitelist: continue
            try:
                original_content = source_path.read_text("utf-8")
                stripped_content = self.transformer.strip(original_content, whitelist=whitelist)
                if original_content != stripped_content:
                    relative_path = source_path.relative_to(self.root_path)
                    tm.add_write(str(relative_path), stripped_content)
                    bus.success(L.strip.file.success, path=relative_path)
                    total_stripped_files += 1
            except Exception as e:
                bus.error(L.error.generic, error=e)
        
        if total_stripped_files > 0:
            bus.success(L.strip.run.complete, count=total_stripped_files)
~~~~~

#### Acts 4: Refactor PumpRunner into an Orchestrator

The `PumpRunner` is now dramatically simplified.

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/runner.py
~~~~~
~~~~~python
from typing import List
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.spec.interaction import InteractionHandler
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager
from .protocols import PumpAnalyzerProtocol, PumpExecutorProtocol


class PumpRunner:
    def __init__(
        self,
        analyzer: PumpAnalyzerProtocol,
        executor: PumpExecutorProtocol,
        interaction_handler: InteractionHandler | None,
    ):
        self.analyzer = analyzer
        self.executor = executor
        self.interaction_handler = interaction_handler

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
        all_conflicts = self.analyzer.analyze(modules)

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
        return self.executor.execute(modules, decisions, tm, strip)
~~~~~

#### Acts 5: Update StitcherApp (Composition Root)

Finally, we wire everything together in `core.py`.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/__init__.py
~~~~~
~~~~~python.old
from .check import CheckRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner
from .coverage import CoverageRunner
~~~~~
~~~~~python.new
from .check import CheckRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner
from .coverage import CoverageRunner
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from .runners.check.analyzer import CheckAnalyzer
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from stitcher.common.transaction import TransactionManager
~~~~~
~~~~~python.new
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from .runners.check.analyzer import CheckAnalyzer
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.analyzer import PumpAnalyzer
from .runners.pump.executor import PumpExecutor
from stitcher.common.transaction import TransactionManager
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            reporter=check_reporter,
        )

        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
            index_store=self.index_store,
        )
        self.init_runner = InitRunner(
            root_path,
            self.doc_manager,
~~~~~
~~~~~python.new
            reporter=check_reporter,
        )

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

        self.init_runner = InitRunner(
            root_path,
            self.doc_manager,
~~~~~

### 下一步建议
我们已经成功地将 `CheckRunner` 和 `PumpRunner` 重构为模块化、可注入的组件。现在，`stitcher-application` 层的核心业务逻辑已经非常清晰和可测试。下一步可以继续应用此模式到剩余的 Runner（如 `TransformRunner`），或者进入 **“阶段四：Refactor 引擎泛化”**，开始处理 `stitcher-refactor` 包的解耦工作。
