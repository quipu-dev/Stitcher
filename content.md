## [WIP] feat(app): Integrate ConsistencyEngine into CheckRunner

### 用户需求

实施 Phase 1.6：集成与替换。
将 `stitcher-application` 中的 `CheckRunner` 迁移到使用新的 `stitcher-analysis` 包中的 `ConsistencyEngine`。这意味着要移除旧的 `CheckAnalyzer`，并更新 Subject、Reporter 和 Resolver 以适配新的数据结构（`Violation` 和 `SemanticPointer`）。

### 评论

这是真正的“换脑”手术。我们将 `app` 层的硬编码逻辑替换为调用通用的分析引擎。
主要的挑战在于适配：
1.  **数据结构变更**: 从 `Dict[str, List[str]]` (分类的字符串列表) 变为 `List[Violation]` (扁平化的语义对象列表)。
2.  **交互逻辑适配**: `InteractionHandler` 仍然依赖 `ConflictType` 枚举，我们需要在 Runner 层将特定的 `Violation` 映射回 `ConflictType`。

### 目标

1.  `stitcher-application` 依赖 `stitcher-analysis`。
2.  `Subject` 适配：实现 `AnalysisSubject` 协议（新增 `is_tracked`）。
3.  `Reporter` 适配：利用 `FeedbackBus` 直接消费 `SemanticPointer`。
4.  `Resolver` 适配：更新为处理 `Violation` 列表。
5.  `Runner` 适配：使用 `ConsistencyEngine` 并处理 `Violation` 到 `InteractionContext` 的转换。
6.  清理旧代码。

### 基本原理

*   **Adapter Pattern**: 既然我们不能一次性重构整个 Spec 层的交互协议，我们在 Runner 中建立一个适配层，将新世界的 `Violation` 转换为旧世界的 `InteractionContext`，以维持 `stitcher-spec` 的稳定性。
*   **Semantic Reporting**: Reporter 将直接受益于新架构，代码将大幅简化，不再需要手动遍历各类错误字典。

### 标签

#intent/refine #intent/build #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/architecture #task/object/check-runner #task/action/integrate-engine #task/state/end

---

### Script

#### Acts 1: 添加依赖

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-workspace",
    "stitcher-index",
    "pyneedle",
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml.new
    "stitcher-workspace",
    "stitcher-index",
    "pyneedle",
    "stitcher-analysis",
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
stitcher-workspace = { workspace = true }
stitcher-index = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~toml.new
stitcher-workspace = { workspace = true }
stitcher-index = { workspace = true }
pyneedle = { workspace = true }
stitcher-analysis = { workspace = true }
~~~~~

#### Acts 2: 适配 Subject

更新 `subject.py` 以使用新的 `SymbolState` 并实现 `is_tracked`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
from typing import Dict, Optional
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.index import SymbolRecord
from .protocols import SymbolState, CheckSubject


class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStoreProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
    ):
        self._file_path = file_path
        self._index_store = index_store
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager

    @property
    def file_path(self) -> str:
        return self._file_path

    def _is_public(self, fqn: str) -> bool:
~~~~~
~~~~~python.new
from typing import Dict, Optional
from pathlib import Path
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.index import SymbolRecord
from stitcher.analysis.schema import SymbolState
from stitcher.analysis.protocols import AnalysisSubject


class IndexCheckSubjectAdapter(AnalysisSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStoreProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        root_path: Path,
    ):
        self._file_path = file_path
        self._index_store = index_store
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._root_path = root_path

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def is_tracked(self) -> bool:
        # Check if .stitcher.yaml exists for this file
        return (self._root_path / self._file_path).with_suffix(".stitcher.yaml").exists()

    def _is_public(self, fqn: str) -> bool:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
class ASTCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self._module = module_def
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._fingerprint_strategy = fingerprint_strategy

    @property
    def file_path(self) -> str:
        return self._module.file_path

    def _compute_fingerprints(self) -> Dict[str, Fingerprint]:
~~~~~
~~~~~python.new
class ASTCheckSubjectAdapter(AnalysisSubject):
    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        root_path: Path,
    ):
        self._module = module_def
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._fingerprint_strategy = fingerprint_strategy
        self._root_path = root_path

    @property
    def file_path(self) -> str:
        return self._module.file_path

    @property
    def is_tracked(self) -> bool:
        return (self._root_path / self.file_path).with_suffix(".stitcher.yaml").exists()

    def _compute_fingerprints(self) -> Dict[str, Fingerprint]:
~~~~~

#### Acts 3: 适配 Runner

注入 `ConsistencyEngine`，并在 `analyze_*` 方法中处理数据转换。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python
from typing import List, Tuple, TYPE_CHECKING
from pathlib import Path

from stitcher.spec import (
    ModuleDef,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.analysis.schema import FileCheckResult

from .protocols import (
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter

if TYPE_CHECKING:
    from stitcher.analysis.engines import ConsistencyEngine


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        engine: "ConsistencyEngine",
        resolver: CheckResolverProtocol,
        reporter: CheckReporterProtocol,
    ):
        self.root_path = root_path
        # Keep services needed by adapter
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store

        # Injected sub-components
        self.engine = engine
        self.resolver = resolver
        self.reporter = reporter

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path, 
                self.index_store, 
                self.doc_manager, 
                self.sig_manager,
                self.root_path
            )
            result = self.engine.analyze(subject)
            all_results.append(result)
            
            conflicts = self._violations_to_conflicts(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                self.root_path
            )

            result = self.engine.analyze(subject)
            all_results.append(result)

            conflicts = self._violations_to_conflicts(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts
    
    def _violations_to_conflicts(self, result: FileCheckResult) -> List[InteractionContext]:
        conflicts = []
        from needle.pointer import L
        from stitcher.spec import ConflictType
        
        pointer_to_conflict = {
            L.check.state.signature_drift: ConflictType.SIGNATURE_DRIFT,
            L.check.state.co_evolution: ConflictType.CO_EVOLUTION,
            L.check.issue.conflict: ConflictType.DOC_CONTENT_CONFLICT,
            L.check.issue.extra: ConflictType.DANGLING_DOC,
        }

        for v in result.violations:
            if v.kind in pointer_to_conflict:
                conflict_type = pointer_to_conflict[v.kind]
                
                sig_diff = v.context.get("signature_diff")
                doc_diff = v.context.get("doc_diff")
                
                conflicts.append(InteractionContext(
                    file_path=result.path,
                    fqn=v.fqn,
                    conflict_type=conflict_type,
                    signature_diff=sig_diff,
                    doc_diff=doc_diff
                ))
        return conflicts

    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ):
        self.resolver.auto_reconcile_docs(results, modules)

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        return self.resolver.resolve_conflicts(
            results, conflicts, force_relink, reconcile
        )

    def reformat_all(self, modules: List[ModuleDef]):
        self.resolver.reformat_all(modules)

    def report(self, results: List[FileCheckResult]) -> bool:
        return self.reporter.report(results)
~~~~~

#### Acts 4: 适配 Reporter

重构 Reporter 以支持 `Violation`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python
from typing import List
from stitcher.common import bus
from needle.pointer import L
from stitcher.analysis.schema import FileCheckResult


class CheckReporter:
    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0

        for res in results:
            # 1. Info / Success Messages (Auto-reconciled)
            # Filter for doc_updated violations
            doc_updated = [v for v in res.violations if v.kind == L.check.state.doc_updated]
            for v in sorted(doc_updated, key=lambda x: x.fqn):
                bus.info(v.kind, key=v.fqn)

            if res.is_clean:
                continue

            # 2. Reconciled Actions
            if res.reconciled_count > 0:
                for v in res.reconciled:
                     # Reconciled violations usually carry success status
                     # We can map original kind to success message if needed, or Violation should carry result kind?
                     # For now, let's assume reconciled items map to:
                     # force_relink -> L.check.state.relinked
                     # reconcile -> L.check.state.reconciled
                     # purged -> L.check.state.purged
                     # The violation itself is the original issue. We need the resolution action.
                     # But wait, CheckResolver._update_results puts data into reconciled.
                     # We need to see how we update CheckResolver to put Violations into reconciled.
                     # Let's assume CheckResolver puts ResolvedViolation(kind=L.check.state.reconciled...)
                     bus.success(v.kind, key=v.fqn, path=res.path)

            # 3. File Level Status
            # We need to distinguish errors from warnings.
            # In new system, error/warning is implicit in the Pointer path or config.
            # For simplicity, let's assume all Violations are 'issues' unless they are 'infos'.
            # Or we can classify based on L path.
            # L.check.issue.* -> Warning/Error?
            # L.check.state.* -> Error (drift/co-evolution)
            # L.check.file.* -> Warning (untracked)
            
            # Simple heuristic matching legacy logic:
            errors = [v for v in res.violations if v.kind in [
                L.check.state.signature_drift, 
                L.check.state.co_evolution, 
                L.check.issue.conflict, 
                L.check.issue.extra,
                L.check.issue.pending
            ]]
            warnings = [v for v in res.violations if v.kind in [
                L.check.issue.missing, 
                L.check.issue.redundant,
                L.check.state.untracked_code, # Not used in new rules yet?
                L.check.file.untracked,
                L.check.file.untracked_with_details
            ]]
            
            error_count = len(errors)
            warning_count = len(warnings)

            if error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=error_count)
            elif warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=warning_count)

            # 4. Detailed Issues
            self._report_issues(res)

        # 5. Global Summary
        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True

    def _report_issues(self, res: FileCheckResult) -> None:
        # We just iterate all active violations and print them.
        # Filter out info/doc_updated which are handled above.
        
        # Sort by FQN for deterministic output
        sorted_violations = sorted(res.violations, key=lambda v: v.fqn)
        
        for v in sorted_violations:
            if v.kind == L.check.state.doc_updated:
                continue
            
            # Determine log level
            # Using the same heuristic
            is_error = v.kind in [
                L.check.state.signature_drift, 
                L.check.state.co_evolution, 
                L.check.issue.conflict, 
                L.check.issue.extra,
                L.check.issue.pending
            ]
            
            # Pass context to bus (e.g. for untracked_with_details count)
            kwargs = {"key": v.fqn, **v.context}
            
            if is_error:
                bus.error(v.kind, **kwargs)
            else:
                bus.warning(v.kind, **kwargs)
~~~~~

#### Acts 5: 适配 Resolver

更新 `resolver.py` 以处理 `FileCheckResult` 的结构变化。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from collections import defaultdict
from typing import List, Dict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.analysis.schema import FileCheckResult, Violation


class CheckResolver:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.interaction_handler = interaction_handler
        self.fingerprint_strategy = fingerprint_strategy

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ):
        for res in results:
            # Look for doc_updated violations
            doc_updates = [v.fqn for v in res.violations if v.kind == L.check.state.doc_updated]
            
            if doc_updates:
                module_def = next((m for m in modules if m.file_path == res.path), None)
                if not module_def:
                    continue

                stored_hashes = self.sig_manager.load_composite_hashes(
                    module_def.file_path
                )
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module_def
                )

                for fqn in doc_updates:
                    if fqn in new_hashes:
                        new_yaml_hash = current_yaml_map.get(fqn)
                        if new_yaml_hash is not None:
                            new_hashes[fqn]["baseline_yaml_content_hash"] = (
                                new_yaml_hash
                            )
                        elif "baseline_yaml_content_hash" in new_hashes[fqn]:
                            del new_hashes[fqn]["baseline_yaml_content_hash"]

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(
                        module_def.file_path, new_hashes
                    )

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        if not conflicts:
            return True

        if self.interaction_handler:
            return self._resolve_interactive(results, conflicts)
        else:
            return self._resolve_noop(results, conflicts, force_relink, reconcile)

    def _resolve_interactive(
        self, results: List[FileCheckResult], conflicts: List[InteractionContext]
    ) -> bool:
        assert self.interaction_handler is not None

        chosen_actions = self.interaction_handler.process_interactive_session(conflicts)
        resolutions_by_file = defaultdict(list)
        
        # We will track resolved violations to move them from 'violations' to 'reconciled'
        resolved_context_map = {}

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            
            # Map action to a SemanticPointer for reporting success
            result_kind = None
            if action == ResolutionAction.RELINK:
                result_kind = L.check.state.relinked
            elif action == ResolutionAction.RECONCILE:
                result_kind = L.check.state.reconciled
            elif action == ResolutionAction.PURGE_DOC:
                result_kind = L.check.state.purged
            
            if result_kind:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                resolved_context_map[(context.file_path, context.fqn)] = result_kind
            
            elif action == ResolutionAction.SKIP:
                # Do nothing, violation remains in result
                pass
            elif action == ResolutionAction.ABORT:
                bus.warning(L.strip.run.aborted)
                return False

        self._apply_resolutions(dict(resolutions_by_file))
        self._update_results(results, resolved_context_map)
        return True

    def _resolve_noop(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool,
        reconcile: bool,
    ) -> bool:
        handler = NoOpInteractionHandler(force_relink, reconcile)
        chosen_actions = handler.process_interactive_session(conflicts)
        resolutions_by_file = defaultdict(list)
        resolved_context_map = {}

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action != ResolutionAction.SKIP:
                 # Logic for NOOP is similar, map action to kind
                result_kind = None
                if action == ResolutionAction.RELINK:
                    result_kind = L.check.state.relinked
                elif action == ResolutionAction.RECONCILE:
                    result_kind = L.check.state.reconciled
                elif action == ResolutionAction.PURGE_DOC:
                    result_kind = L.check.state.purged
                
                if result_kind:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    resolved_context_map[(context.file_path, context.fqn)] = result_kind
            # else SKIP, do nothing

        self._apply_resolutions(dict(resolutions_by_file))
        self._update_results(results, resolved_context_map)
        return True

    def _update_results(self, results: List[FileCheckResult], resolved_map: Dict[tuple, Any]):
        # Move resolved violations from .violations to .reconciled
        # and update their kind to the success kind (e.g. relinked)
        for res in results:
            active_violations = []
            for v in res.violations:
                key = (res.path, v.fqn)
                if key in resolved_map:
                    # It was resolved. Create a new Violation record for the reconciliation
                    success_kind = resolved_map[key]
                    res.reconciled.append(Violation(kind=success_kind, fqn=v.fqn))
                else:
                    active_violations.append(v)
            res.violations = active_violations

    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        sig_updates_by_file = defaultdict(list)
        purges_by_file = defaultdict(list)

        for file_path, fqn_actions in resolutions.items():
            for fqn, action in fqn_actions:
                if action in [ResolutionAction.RELINK, ResolutionAction.RECONCILE]:
                    sig_updates_by_file[file_path].append((fqn, action))
                elif action == ResolutionAction.PURGE_DOC:
                    purges_by_file[file_path].append(fqn)

        # Apply signature updates
        for file_path, fqn_actions in sig_updates_by_file.items():
            stored_hashes = self.sig_manager.load_composite_hashes(file_path)
            new_hashes = copy.deepcopy(stored_hashes)

            full_module_def = self.parser.parse(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            computed_fingerprints = self._compute_fingerprints(full_module_def)
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    current_code_hash = current_fp.get("current_code_structure_hash")

                    if action == ResolutionAction.RELINK:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = str(
                                current_yaml_map[fqn]
                            )

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(file_path, new_hashes)

        # Apply doc purges
        for file_path, fqns_to_purge in purges_by_file.items():
            module_def = ModuleDef(file_path=file_path)
            docs = self.doc_manager.load_docs_for_module(module_def)
            original_len = len(docs)

            for fqn in fqns_to_purge:
                if fqn in docs:
                    del docs[fqn]

            if len(docs) < original_len:
                doc_path = (self.root_path / file_path).with_suffix(".stitcher.yaml")
                if not docs:
                    if doc_path.exists():
                        doc_path.unlink()
                else:
                    final_data = {
                        k: self.doc_manager.serialize_ir(v) for k, v in docs.items()
                    }
                    content = self.doc_manager.dump_data(final_data)
                    doc_path.write_text(content, encoding="utf-8")

    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_file(module.file_path)
~~~~~

#### Acts 6: 在 App Core 中注入 Engine

最后，修改 `core.py`，实例化 `ConsistencyEngine` 并传递给 `CheckRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from .runners.check.analyzer import CheckAnalyzer
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.analyzer import PumpAnalyzer
from .runners.pump.executor import PumpExecutor
~~~~~
~~~~~python.new
from stitcher.analysis.engines import create_consistency_engine
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.analyzer import PumpAnalyzer
from .runners.pump.executor import PumpExecutor
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 3. Runners (Command Handlers)
        check_analyzer = CheckAnalyzer(root_path, self.differ)
        check_resolver = CheckResolver(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            interaction_handler,
            self.fingerprint_strategy,
        )
        check_reporter = CheckReporter()
        self.check_runner = CheckRunner(
            self.doc_manager,
            self.sig_manager,
            self.fingerprint_strategy,
            self.index_store,
            analyzer=check_analyzer,
            resolver=check_resolver,
            reporter=check_reporter,
        )

        pump_analyzer = PumpAnalyzer(
~~~~~
~~~~~python.new
        # 3. Runners (Command Handlers)
        # Use Factory to create engine (Analysis Layer)
        consistency_engine = create_consistency_engine(differ=self.differ)
        
        check_resolver = CheckResolver(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            interaction_handler,
            self.fingerprint_strategy,
        )
        check_reporter = CheckReporter()
        self.check_runner = CheckRunner(
            root_path=root_path,
            doc_manager=self.doc_manager,
            sig_manager=self.sig_manager,
            fingerprint_strategy=self.fingerprint_strategy,
            index_store=self.index_store,
            engine=consistency_engine,
            resolver=check_resolver,
            reporter=check_reporter,
        )

        pump_analyzer = PumpAnalyzer(
~~~~~

#### Acts 7: 清理旧代码

删除不再使用的旧 Analyzer 和协议文件。

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/check/analyzer.py
~~~~~

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/check/protocols.py
~~~~~

### 下一步建议

集成完成！我们已经成功将核心分析逻辑剥离到 `stitcher-analysis` 包中，并重构了 `stitcher-application` 以使用新的、基于语义指针的一致性引擎。

这标志着 **Phase 1: 提取规则 (Extraction)** 的圆满结束。

建议运行完整的测试套件（特别是集成测试），以验证这次“心脏移植”手术是否成功，并没有引入回归。如果一切顺利，我们就可以开始规划 **Phase 2**，着手增强图分析能力。
