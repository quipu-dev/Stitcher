好的，我们开始执行“彻底重构 `CheckReporter`”这一优先任务。

为了实现这一目标，我们需要从数据产生的源头 (`stitcher-analysis`) 到数据消费的终端 (`CheckReporter`)，贯穿整个调用链，将数据结构升级为现代的、基于 `Violation` 对象的模式，并彻底拆除遗留的、基于字典的兼容层。

这是一个系统性的重构，将涉及 `stitcher-analysis` 和 `stitcher-application` 两个包。

## [WIP] refactor(app): 将 CheckReporter 重构为直接消费 Violation 对象

### 用户需求

根据上一阶段的架构债务分析，`CheckReporter` 目前依赖一个陈旧的、基于字典的 `FileCheckResult` 数据结构。这迫使 `CheckRunner` 维护一个复杂的 `_translate_results` 方法，将现代的 `Violation` 对象降级为旧格式，从而产生了不必要的兼容性开销和技术债务。

我们需要重构整个 `check` 命令的数据流，使其从头到尾都使用 `stitcher.analysis.schema` 中定义的、基于 `Violation` 对象的 `FileCheckResult`。

### 评论

这是一个关键的“正本清源”步骤。通过本次重构，我们将：
1.  **消除兼容层**: 彻底移除 `CheckRunner` 中臃肿的 `_translate_results` 方法。
2.  **提升类型安全**: 让 `CheckReporter` 和 `CheckResolver` 直接与类型化的 `Violation` 对象交互，而不是脆弱的字符串键。
3.  **简化逻辑**: `Reporter` 的逻辑将从操作字典转变为操作对象列表，代码更清晰、更健壮。
4.  **遵循 HFEA 原则**: 根除架构异味，确保数据模型在系统内部流转时保持其“本体论正确性”。

### 目标

1.  **增强 `analysis` 层的 `FileCheckResult`**: 为其添加必要的辅助属性（如 `error_count`, `warning_count`），使其能独立承担报告所需的数据计算。
2.  **重构 `CheckResolver`**: 修改其内部逻辑，使其能够直接操作新的 `FileCheckResult` 对象，将已解决的 `Violation` 从 `violations` 列表移至 `reconciled` 列表。
3.  **重写 `CheckReporter`**: 使其完全基于新的 `FileCheckResult` 和 `Violation` 对象进行报告渲染。
4.  **重构 `CheckRunner`**: 拆除 `_translate_results` 转换逻辑，让 `analysis` 引擎产生的 `FileCheckResult` 对象无缝流经 `Resolver` 并最终抵达 `Reporter`。

### 基本原理

我们将采用自底向上的策略：
1.  首先，强化数据模型 (`FileCheckResult` in `analysis`)，赋予其更强的自描述能力。
2.  其次，改造数据处理层 (`CheckResolver`) 和数据消费层 (`CheckReporter`)，使其适应新的数据模型。
3.  最后，改造数据编排层 (`CheckRunner`)，打通整个数据链路，移除旧的适配器逻辑。

这种方法确保了每一步修改都有坚实的基础，最终实现整个 `check` 功能数据流的现代化和纯净化。

### 标签

#intent/refine #flow/ready #priority/high #comp/app #comp/analysis #concept/ui #scope/core #scope/dx #ai/instruct #task/domain/testing #task/object/reporter #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 增强 `stitcher.analysis.schema.results.FileCheckResult`

我们将为 `FileCheckResult` 添加分类和计数的属性，使其能够自我描述其内部状态，从而简化上游消费者的逻辑。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/schema/results.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import List

from .violation import Violation


@dataclass
class FileCheckResult:
    path: str

    # All findings (errors, warnings, infos)
    violations: List[Violation] = field(default_factory=list)

    # Records of actions taken during auto-reconciliation
    # Reconciled items are also fundamentally Violations that were resolved.
    reconciled: List[Violation] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import List, Dict, Set

from needle.pointer import L, SemanticPointer
from .violation import Violation


@dataclass
class FileCheckResult:
    path: str

    # All findings (errors, warnings, infos)
    violations: List[Violation] = field(default_factory=list)

    # Records of actions taken during auto-reconciliation
    # Reconciled items are also fundamentally Violations that were resolved.
    reconciled: List[Violation] = field(default_factory=list)

    # --- Severity Mapping ---
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

    _WARNING_KINDS: Set[SemanticPointer] = field(
        default_factory=lambda: {
            L.check.issue.missing,
            L.check.issue.redundant,
            L.check.file.untracked,
            L.check.file.untracked_with_details,
        },
        init=False,
        repr=False,
    )

    # --- Computed Properties ---
    @property
    def error_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.kind in self._ERROR_KINDS]

    @property
    def warning_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.kind in self._WARNING_KINDS]

    @property
    def info_violations(self) -> List[Violation]:
        error_and_warning_kinds = self._ERROR_KINDS | self._WARNING_KINDS
        return [v for v in self.violations if v.kind not in error_and_warning_kinds]

    @property
    def error_count(self) -> int:
        return len(self.error_violations)

    @property
    def warning_count(self) -> int:
        return len(self.warning_violations)

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0
~~~~~

#### Acts 2: 重构 `CheckResolver` 以适配新的 `FileCheckResult`

`CheckResolver` 是交互式冲突解决的核心。我们必须修改它，使其不再操作旧的字典式 `FileCheckResult`，而是直接修改新的、基于 `Violation` 列表的 `FileCheckResult`。

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
from needle.pointer import L, SemanticPointer
from stitcher.spec import (
    ModuleDef,
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
        # Helper duplicated here for simplicity in applying updates,
        # ideally this logic belongs to a shared utility or service.
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
            # Find all "doc_updated" violations and update baselines
            doc_update_violations = [
                v for v in res.info_violations if v.kind == L.check.state.doc_updated
            ]
            if not doc_update_violations:
                continue

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

            for violation in doc_update_violations:
                fqn = violation.fqn
                if fqn in new_hashes:
                    new_yaml_hash = current_yaml_map.get(fqn)
                    if new_yaml_hash is not None:
                        new_hashes[fqn]["baseline_yaml_content_hash"] = new_yaml_hash
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
        unresolved_contexts: List[InteractionContext] = []

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action in (
                ResolutionAction.RELINK,
                ResolutionAction.RECONCILE,
                ResolutionAction.HYDRATE_OVERWRITE,
                ResolutionAction.HYDRATE_KEEP_EXISTING,
                ResolutionAction.PURGE_DOC,
            ):
                resolutions_by_file[context.file_path].append((context, action))
            elif action == ResolutionAction.SKIP:
                unresolved_contexts.append(context)
            elif action == ResolutionAction.ABORT:
                bus.warning(L.strip.run.aborted)
                return False

        self._apply_resolutions(dict(resolutions_by_file))
        self._update_results(results, dict(resolutions_by_file))

        # Unresolved conflicts are kept in the violations list, so no action needed.
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

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action != ResolutionAction.SKIP:
                resolutions_by_file[context.file_path].append((context, action))

        self._apply_resolutions(dict(resolutions_by_file))
        self._update_results(results, dict(resolutions_by_file))
        return True

    def _update_results(
        self,
        results: List[FileCheckResult],
        resolutions: Dict[str, List[tuple[InteractionContext, ResolutionAction]]],
    ):
        for res in results:
            if res.path not in resolutions:
                continue

            resolved_fqns_by_kind: Dict[SemanticPointer, set] = defaultdict(set)
            for context, _ in resolutions[res.path]:
                resolved_fqns_by_kind[context.violation_type].add(context.fqn)

            # Filter out violations that have been resolved and move them to reconciled
            remaining_violations = []
            for violation in res.violations:
                resolved_fqns = resolved_fqns_by_kind.get(violation.kind, set())
                if violation.fqn in resolved_fqns:
                    res.reconciled.append(violation)
                else:
                    remaining_violations.append(violation)
            res.violations = remaining_violations

    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[InteractionContext, ResolutionAction]]]
    ):
        sig_updates_by_file = defaultdict(list)
        purges_by_file = defaultdict(list)

        for file_path, context_actions in resolutions.items():
            for context, action in context_actions:
                if action in [ResolutionAction.RELINK, ResolutionAction.RECONCILE]:
                    sig_updates_by_file[file_path].append((context.fqn, action))
                elif action == ResolutionAction.PURGE_DOC:
                    purges_by_file[file_path].append(context.fqn)

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

#### Acts 3: 重写 `CheckReporter`

现在，我们将 `CheckReporter` 的实现完全切换到新的数据模型上，使其逻辑更清晰、更健壮。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python
from typing import List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.analysis.schema import FileCheckResult, Violation


class CheckReporter:
    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0

        for res in results:
            # 1. Info / Success Messages (Auto-reconciled doc updates)
            for info_violation in res.info_violations:
                if info_violation.kind == L.check.state.doc_updated:
                    bus.info(L.check.state.doc_updated, key=info_violation.fqn)

            if res.is_clean and not res.reconciled:
                continue

            # 2. Reconciled Actions (User-driven or flag-driven resolutions)
            if res.reconciled:
                # Group reconciled violations by kind for clear reporting
                reconciled_by_kind = defaultdict(list)
                for v in res.reconciled:
                    reconciled_by_kind[v.kind].append(v.fqn)

                # Map kind to success message
                reconcile_message_map = {
                    L.check.state.signature_drift: L.check.state.relinked,
                    L.check.state.co_evolution: L.check.state.reconciled,
                    L.check.issue.conflict: L.check.state.reconciled,
                    L.check.issue.extra: L.check.state.purged,
                }
                for kind, fqns in reconciled_by_kind.items():
                    message_id = reconcile_message_map.get(kind)
                    if message_id:
                        for fqn in sorted(fqns):
                            bus.success(message_id, key=fqn, path=res.path)

            # 3. File Level Status
            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)

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
        # Group all remaining violations by their kind
        violations_by_kind = defaultdict(list)
        for v in res.violations:
            violations_by_kind[v.kind].append(v)

        # Define the order and message for reporting
        REPORTING_ORDER = [
            # Errors
            L.check.issue.extra,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.conflict,
            L.check.issue.pending,
            # Warnings
            L.check.issue.missing,
            L.check.issue.redundant,
            L.check.file.untracked_with_details,
            L.check.file.untracked,
        ]

        for kind in REPORTING_ORDER:
            if kind not in violations_by_kind:
                continue

            violations = violations_by_kind[kind]
            # Special handling for untracked files
            if kind == L.check.file.untracked_with_details:
                violation = violations[0]  # There should only be one
                keys = violation.context.get("keys", [])
                bus.warning(kind, path=res.path, count=len(keys))
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            elif kind == L.check.file.untracked:
                bus.warning(kind, path=res.path)
            else:
                # Standard symbol-based violations
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    bus_func(v.kind, key=v.fqn)
~~~~~

#### Acts 4: 重构 `CheckRunner` 以移除兼容层

最后，我们重构 `CheckRunner`，拆除 `_translate_results` 方法，让 `AnalysisFileCheckResult` 对象在整个流程中畅通无阻。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python
from typing import List, Tuple
from pathlib import Path

from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
    DifferProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.analysis.schema import FileCheckResult as AnalysisFileCheckResult

from .protocols import (
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter
from stitcher.analysis.engines.consistency.engine import create_consistency_engine


class CheckRunner:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        differ: DifferProtocol,
        resolver: CheckResolverProtocol,
        reporter: CheckReporterProtocol,
        root_path: Path,
    ):
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store
        self.root_path = root_path

        self.engine = create_consistency_engine(differ=differ)
        self.resolver = resolver
        self.reporter = reporter

    def _extract_conflicts(
        self, analysis_result: AnalysisFileCheckResult
    ) -> List[InteractionContext]:
        conflicts: List[InteractionContext] = []

        INTERACTIVE_VIOLATIONS = {
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.extra,
            L.check.issue.conflict,
        }

        for violation in analysis_result.violations:
            if violation.kind in INTERACTIVE_VIOLATIONS:
                conflicts.append(
                    InteractionContext(
                        file_path=analysis_result.path,
                        fqn=violation.fqn,
                        violation_type=violation.kind,
                        signature_diff=violation.context.get("signature_diff"),
                        doc_diff=violation.context.get("doc_diff"),
                    )
                )
        return conflicts

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[AnalysisFileCheckResult], List[InteractionContext]]:
        all_results: List[AnalysisFileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path,
                self.index_store,
                self.doc_manager,
                self.sig_manager,
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            conflicts = self._extract_conflicts(analysis_result)
            all_results.append(analysis_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[AnalysisFileCheckResult], List[InteractionContext]]:
        all_results: List[AnalysisFileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            conflicts = self._extract_conflicts(analysis_result)
            all_results.append(analysis_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def auto_reconcile_docs(
        self, results: List[AnalysisFileCheckResult], modules: List[ModuleDef]
    ):
        self.resolver.auto_reconcile_docs(results, modules)

    def resolve_conflicts(
        self,
        results: List[AnalysisFileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        return self.resolver.resolve_conflicts(
            results, conflicts, force_relink, reconcile
        )

    def reformat_all(self, modules: List[ModuleDef]):
        self.resolver.reformat_all(modules)

    def report(self, results: List[AnalysisFileCheckResult]) -> bool:
        return self.reporter.report(results)
~~~~~

### 下一步建议

我们已经成功地将 `check` 命令的核心数据流现代化。然而，架构中仍然存在一些遗留的定义：

1.  **`stitcher.app.types.FileCheckResult`**: 这个旧的、基于字典的 `FileCheckResult` 依然存在，尽管它现在只被 `CheckRunner` 的测试用例（可能）和一些未触及的旧逻辑间接引用。
2.  **`stitcher.app.runners.check.protocols.py`**: 其中定义的 `SymbolState` 和 `CheckSubject` 协议现在完全是 `stitcher.analysis` 中对应协议的“影子副本”。

我建议下一步将这些遗留定义彻底清除，让 `stitcher-application` 完全依赖 `stitcher-analysis` 提供的 Schema 和 Protocol，完成架构的最终统一。
