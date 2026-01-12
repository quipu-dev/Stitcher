好的，我将开始执行路线图的第一阶段：修复 `stitcher-application` 核心逻辑。

这是一个基础性的重构，旨在将系统中的冲突表示从一个固定的 `Enum` 迁移到一个更灵活、语义更丰富的 `SemanticPointer` 系统。这将为未来的扩展和更精细的错误处理奠定基础。

我将生成一个计划，使用 `write_file` 来原子化地更新每个受影响的核心文件。

## [WIP] refactor: 迁移核心逻辑，将 ConflictType 替换为 violation_type 指针

### 用户需求

根据路线图，需要执行 Phase 1，将 `stitcher-application` 包中的核心组件 (`CheckAnalyzer`, `PumpAnalyzer`, `CheckResolver`, `NoOpInteractionHandler`) 从使用已废弃的 `ConflictType` Enum 迁移到在 `InteractionContext` 中使用新的 `violation_type: SemanticPointer`。

### 评论

这是整个迁移路线图中至关重要的一步。通过将核心业务逻辑与一个具体的、僵硬的 `Enum` 定义解耦，我们引入了 `SemanticPointer` 带来的灵活性和可扩展性。此举不仅是技术债务的清理，更是对系统架构的一次重要加固，使其更能适应未来的变化。

### 目标

1.  修改 `CheckAnalyzer`，使其在检测到不一致时，使用 `L` 指针 (`violation_type`) 实例化 `InteractionContext`。
2.  修改 `PumpAnalyzer`，使其在发现文档内容冲突时，也使用 `L` 指针来创建 `InteractionContext`。
3.  重构 `CheckResolver`，使其消费 `context.violation_type` 指针，而不是 `context.conflict_type` 枚举。
4.  更新 `NoOpInteractionHandler` 的判断逻辑，使其基于 `L` 指针进行决策。

### 基本原理

此次迁移的核心在于替换 `InteractionContext` 的冲突表示法。由于每个目标文件内部都有多处修改（包括但不限于：导入语句的增删、`InteractionContext` 的实例化、条件判断逻辑的变更），为确保操作的原子性和准确性，我将对每个文件使用 `write_file` 指令进行整体覆盖，而不是采用多个零散的 `patch_file` 操作。这将从根本上避免因上下文匹配不精确而导致的潜在错误。

### 标签

#intent/refine #flow/ready #priority/high #comp/cli #concept/state #scope/core #ai/instruct #task/domain/refactor #task/object/conflict-type #task/action/migration #task/state/begin

---

### Script

#### Acts 1: 修改 `CheckAnalyzer` 以使用 `violation_type` 指针

我们将重写 `analyzer.py`，更新 `InteractionContext` 的创建逻辑，并引入 `needle.pointer.L`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/analyzer.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Tuple

from needle.pointer import L
from stitcher.spec import DifferProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult
from .protocols import CheckSubject


class CheckAnalyzer:
    def __init__(self, root_path: Path, differ: DifferProtocol):
        self.root_path = root_path
        self.differ = differ

    def analyze_subject(
        self, subject: CheckSubject
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        result = FileCheckResult(path=subject.file_path)
        unresolved_conflicts: List[InteractionContext] = []

        is_tracked = (
            (self.root_path / subject.file_path).with_suffix(".stitcher.yaml").exists()
        )

        for fqn, state in subject.get_all_symbol_states().items():
            # --- State Machine Logic ---

            # 1. Content Checks
            if state.exists_in_code and state.exists_in_yaml:
                if state.source_doc_content and state.yaml_doc_ir:
                    if state.source_doc_content == state.yaml_doc_ir.summary:
                        result.warnings["redundant"].append(fqn)
                    else:
                        result.errors["conflict"].append(fqn)

            elif state.is_public and state.exists_in_code and not state.exists_in_yaml:
                if state.source_doc_content:
                    result.errors["pending"].append(fqn)
                else:
                    # Legacy Behavior: __doc__ is optional.
                    # If it's missing in both source and YAML, don't report it as missing.
                    if fqn != "__doc__":
                        result.warnings["missing"].append(fqn)

            elif not state.exists_in_code and state.exists_in_yaml:
                unresolved_conflicts.append(
                    InteractionContext(
                        subject.file_path, fqn, violation_type=L.check.issue.extra
                    )
                )

            # 2. Signature Checks
            code_hash = state.signature_hash
            baseline_code_hash = state.baseline_signature_hash

            if code_hash and not baseline_code_hash:  # New symbol, skip
                continue
            if (
                not code_hash and baseline_code_hash
            ):  # Deleted symbol, handled by DANGLING_DOC
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = state.yaml_content_hash == state.baseline_yaml_content_hash

            if code_matches and not yaml_matches:
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                sig_diff = self.differ.generate_text_diff(
                    state.baseline_signature_text or "",
                    state.signature_text or "",
                    "baseline",
                    "current",
                )

                violation_type = (
                    L.check.state.signature_drift
                    if yaml_matches
                    else L.check.state.co_evolution
                )
                unresolved_conflicts.append(
                    InteractionContext(
                        subject.file_path,
                        fqn,
                        violation_type=violation_type,
                        signature_diff=sig_diff,
                    )
                )

        # 3. Untracked File Check
        if not is_tracked and subject.is_documentable():
            # Check for any public symbols that would be documented
            undocumented = [
                s.fqn
                for s in subject.get_all_symbol_states().values()
                if s.is_public
                and s.fqn != "__doc__"
                and not s.source_doc_content
                and not s.exists_in_yaml
            ]
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts
~~~~~

#### Acts 2: 修改 `PumpAnalyzer`

同样地，我们更新 `pump/analyzer.py` 以使用 `violation_type`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/analyzer.py
~~~~~
~~~~~python
from typing import Dict, List

from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
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
        return {fqn: doc for fqn, doc in all_source_docs.items() if fqn in dirty_fqns}

    def analyze(self, modules: List[ModuleDef]) -> List[InteractionContext]:
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
                            violation_type=L.check.issue.conflict,
                            doc_diff=doc_diff,
                        )
                    )
        return all_conflicts
~~~~~

#### Acts 3: 修改 `CheckResolver` 以消费 `violation_type`

现在我们修改消费者。`resolver.py` 中的 `_mark_result_error` 方法将被重构，以处理 `SemanticPointer`。

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
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult


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
            if res.infos["doc_improvement"]:
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

                for fqn in res.infos["doc_improvement"]:
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
        # Should be safe since check logic guarantees interaction_handler is not None here
        assert self.interaction_handler is not None

        chosen_actions = self.interaction_handler.process_interactive_session(conflicts)
        resolutions_by_file = defaultdict(list)
        reconciled_results = defaultdict(lambda: defaultdict(list))

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action == ResolutionAction.RELINK:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["force_relink"].append(
                    context.fqn
                )
            elif action == ResolutionAction.RECONCILE:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["reconcile"].append(context.fqn)
            elif action == ResolutionAction.PURGE_DOC:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["purged"].append(context.fqn)
            elif action == ResolutionAction.SKIP:
                self._mark_result_error(results, context)
            elif action == ResolutionAction.ABORT:
                bus.warning(L.strip.run.aborted)
                return False

        self._apply_resolutions(dict(resolutions_by_file))
        self._update_results(results, reconciled_results)
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
        reconciled_results = defaultdict(lambda: defaultdict(list))

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action != ResolutionAction.SKIP:
                key = (
                    "force_relink" if action == ResolutionAction.RELINK else "reconcile"
                )
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path][key].append(context.fqn)
            else:
                self._mark_result_error(results, context)

        self._apply_resolutions(dict(resolutions_by_file))
        self._update_results(results, reconciled_results)
        return True

    def _mark_result_error(
        self, results: List[FileCheckResult], context: InteractionContext
    ):
        for res in results:
            if res.path == context.file_path:
                error_key_map = {
                    str(L.check.state.signature_drift): "signature_drift",
                    str(L.check.state.co_evolution): "co_evolution",
                    str(L.check.issue.extra): "extra",
                }
                error_key = error_key_map.get(str(context.violation_type), "unknown")
                res.errors[error_key].append(context.fqn)
                break

    def _update_results(self, results: List[FileCheckResult], reconciled_data: dict):
        for res in results:
            if res.path in reconciled_data:
                res.reconciled["force_relink"] = reconciled_data[res.path][
                    "force_relink"
                ]
                res.reconciled["reconcile"] = reconciled_data[res.path]["reconcile"]
                res.reconciled["purged"] = reconciled_data[res.path].get("purged", [])

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

            # NOTE: We are re-parsing here. This is one of the things we want to optimize later.
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

#### Acts 4: 修改 `NoOpInteractionHandler`

最后，我们更新非交互式处理器以使用新的 `violation_type` 进行判断。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/handlers/noop_handler.py
~~~~~
~~~~~python
from typing import List
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction
from needle.pointer import L


class NoOpInteractionHandler(InteractionHandler):
    def __init__(
        self,
        force_relink: bool = False,
        reconcile: bool = False,
        hydrate_force: bool = False,
        hydrate_reconcile: bool = False,
    ):
        self._force_relink = force_relink
        self._reconcile = reconcile  # For Check
        self._hydrate_force = hydrate_force
        self._hydrate_reconcile = hydrate_reconcile

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        actions: List[ResolutionAction] = []
        for context in contexts:
            action = ResolutionAction.SKIP
            if context.violation_type == L.check.state.signature_drift:
                if self._force_relink:
                    action = ResolutionAction.RELINK
            elif context.violation_type == L.check.state.co_evolution:
                if self._reconcile:
                    action = ResolutionAction.RECONCILE
            elif context.violation_type == L.check.issue.conflict:
                if self._hydrate_force:
                    action = ResolutionAction.HYDRATE_OVERWRITE
                elif self._hydrate_reconcile:
                    action = ResolutionAction.HYDRATE_KEEP_EXISTING
            actions.append(action)
        return actions
~~~~~

### 下一步建议

我们已经成功完成了路线图的第一阶段。核心应用逻辑现在已经完全迁移到使用 `violation_type` 语义指针。

接下来的关键步骤是 **Phase 2: 修复 `stitcher-cli` 交互逻辑**。这将确保面向用户的组件（特别是交互式冲突解决器）能够正确理解和显示由核心逻辑产生的新冲突类型。如果你同意，我将立即开始准备执行第二阶段的计划。
