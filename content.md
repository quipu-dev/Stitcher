好的，我来分析并修复这些测试失败。

## [WIP] fix(application): 修复 CheckRunner 中缺失的文档状态检测逻辑

### 错误分析
您提供的测试失败报告非常精确。在我将 `CheckRunner` 重构为 "Query-First" 模式时，为了追求性能，我过度简化了逻辑，导致了几个关键的回归错误：

1.  **`redundant` 和 `conflict` 状态检测丢失**: 新的 `_analyze_file` 方法只比较了代码和 YAML 各自与其*基准 (baseline)* 版本的哈希，但**完全丢失了代码中的文档哈希与 YAML 中的文档哈希之间的直接比较**。这导致：
    *   当代码文档和 YAML 文档内容相同时，无法识别为 `redundant` 状态。(`test_check_detects_matrix_states` 失败)
    *   当它们内容不同时，无法识别为 `conflict` 状态。(`test_check_detects_content_conflict` 失败)

2.  **`untracked` 状态报告逻辑错误**:
    *   `test_check_reports_untracked_with_details`: 我的逻辑错误地将一个未跟踪文件中的*所有*公共符号都报告为“需要文档”，而不是只报告那些*真正缺少*文档的符号。
    *   `test_check_reports_simple_untracked_if_all_docs_present`: 当一个未跟踪文件中的所有公共符号都已经有了文档时，我的逻辑没能正确地回退到发出一个简单的 `untracked` 警告，而是什么都没报告。

### 用户需求
修复 `CheckRunner` 的逻辑，使其能够正确地检测和报告所有的文档一致性状态（`missing`, `pending`, `redundant`, `conflict`），并修正对 `untracked` 文件的报告行为，以使所有相关测试通过。

### 评论
这是一个典型的重构回归案例。虽然 "Query-First" 的方向是正确的，但必须确保新实现能够 100% 覆盖旧实现的业务逻辑。这次修复将恢复 `check` 命令的正确性，同时保留其高性能的优点。

### 目标
1.  在 `CheckRunner._analyze_file` 中，重新引入代码文档哈希与 YAML 文档哈希的直接比较逻辑。
2.  基于上述比较，正确地将符号分类为 `redundant` 或 `conflict` 状态。
3.  重新实现 `missing` 和 `pending` 的检测逻辑，使其基于索引数据而不是不完整的集合运算。
4.  修正 `untracked` 状态的报告逻辑，使其能区分“需要详细报告”和“仅需简单报告”两种情况。

### 基本原理
我们将利用数据库中已经存在的 `docstring_hash` 字段和从 YAML 文件实时计算的哈希值。
-   对于已跟踪文件，我们将遍历所有公共符号，并根据其在代码和 YAML 中是否存在文档以及文档哈希是否匹配，将其精确地归类到五种状态之一。
-   对于未跟踪文件，我们将首先检查其中有多少公共符号是真正未文档化的。如果数量大于零，则发出详细报告；如果数量为零但文件本身有公共符号，则发出简单报告。

### 标签
#intent/fix #flow/ready #priority/critical #comp/application #comp/tests #concept/state #scope/core #ai/instruct #task/domain/runner #task/object/check-runner #task/action/query-first-refactor #task/state/continue

---

### Script

#### Acts 1: 完整重写 `check.py` 以修复所有逻辑错误

由于逻辑变更分散且相互关联，最安全的方式是使用 `write_file` 提供一个完整的、经过修正的 `check.py` 版本。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
)
from stitcher.index.store import IndexStore
from stitcher.index.types import SymbolRecord
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        index_store: IndexStore,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.parser = parser
        self.index_store = index_store
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
        self.interaction_handler = interaction_handler

    def _symbol_to_fingerprint(self, symbol: SymbolRecord) -> Fingerprint:
        fp = Fingerprint()
        if symbol.signature_hash:
            fp["current_code_structure_hash"] = symbol.signature_hash
        if symbol.signature_text:
            fp["current_code_signature_text"] = symbol.signature_text
        if symbol.docstring_hash:
            fp["current_code_docstring_hash"] = symbol.docstring_hash
        return fp

    def _analyze_file(
        self, file_path: str
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        result = FileCheckResult(path=file_path)
        unresolved_conflicts: List[InteractionContext] = []

        file_record = self.index_store.get_file_by_path(file_path)
        if not file_record:
            return result, []

        db_symbols = self.index_store.get_symbols_by_file(file_record.id)
        actual_fingerprints: Dict[str, Fingerprint] = {}
        for sym in db_symbols:
            if sym.logical_path:
                actual_fingerprints[sym.logical_path] = self._symbol_to_fingerprint(sym)

        stored_hashes_map = self.sig_manager.load_composite_hashes(file_path)
        module_stub = ModuleDef(file_path=file_path)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module_stub)

        # --- Doc Content and State Machine Analysis ---
        is_tracked = (self.root_path / file_path).with_suffix(".stitcher.yaml").exists()
        code_keys = set(actual_fingerprints.keys())
        yaml_keys = set(current_yaml_map.keys())
        public_code_keys = {k for k in code_keys if not k.split(".")[-1].startswith("_")}

        if is_tracked:
            # Extra (Dangling Doc)
            extra = yaml_keys - code_keys
            extra.discard("__doc__")
            for fqn in extra:
                unresolved_conflicts.append(
                    InteractionContext(file_path, fqn, ConflictType.DANGLING_DOC)
                )

            # Check states for all public symbols in code
            for key in public_code_keys:
                code_fp = actual_fingerprints.get(key, Fingerprint())
                has_code_doc = "current_code_docstring_hash" in code_fp
                has_yaml_doc = key in current_yaml_map

                if not has_code_doc and not has_yaml_doc:
                    result.warnings["missing"].append(key)
                elif has_code_doc and not has_yaml_doc:
                    result.errors["pending"].append(key)
                elif has_code_doc and has_yaml_doc:
                    if code_fp["current_code_docstring_hash"] == current_yaml_map[key]:
                        result.warnings["redundant"].append(key)
                    else:
                        result.errors["conflict"].append(key)

        # --- Signature Drift Analysis ---
        all_fqns = code_keys | set(stored_hashes_map.keys())
        for fqn in sorted(list(all_fqns)):
            computed_fp = actual_fingerprints.get(fqn, Fingerprint())
            stored_fp = stored_hashes_map.get(fqn)
            if not computed_fp or not stored_fp:
                continue

            code_hash = computed_fp.get("current_code_structure_hash")
            baseline_code_hash = stored_fp.get("baseline_code_structure_hash")
            yaml_hash = current_yaml_map.get(fqn)
            baseline_yaml_hash = stored_fp.get("baseline_yaml_content_hash")

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                conflict_type = (
                    ConflictType.SIGNATURE_DRIFT
                    if yaml_matches
                    else ConflictType.CO_EVOLUTION
                )
                unresolved_conflicts.append(
                    InteractionContext(
                        file_path,
                        fqn,
                        conflict_type,
                        signature_diff=self.differ.generate_text_diff(
                            stored_fp.get("baseline_code_signature_text", ""),
                            computed_fp.get("current_code_signature_text", ""),
                            "baseline",
                            "current",
                        ),
                    )
                )

        # --- Untracked File Logic ---
        if not is_tracked:
            undocumented_public_keys = [
                k
                for k in public_code_keys
                if not actual_fingerprints.get(k, Fingerprint()).get(
                    "current_code_docstring_hash"
                )
            ]
            if undocumented_public_keys:
                result.warnings["untracked_detailed"].extend(
                    sorted(undocumented_public_keys)
                )
            elif public_code_keys:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts

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

            file_record = self.index_store.get_file_by_path(file_path)
            if not file_record:
                continue
            db_symbols = self.index_store.get_symbols_by_file(file_record.id)
            actual_fingerprints = {}
            for sym in db_symbols:
                if sym.logical_path:
                    actual_fingerprints[sym.logical_path] = self._symbol_to_fingerprint(
                        sym
                    )

            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                ModuleDef(file_path=file_path)
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    current_fp = actual_fingerprints.get(fqn, Fingerprint())
                    current_code_hash = current_fp.get("current_code_structure_hash")
                    current_sig_text = current_fp.get("current_code_signature_text")
                    current_doc_hash = current_fp.get("current_code_docstring_hash")

                    if action == ResolutionAction.RELINK:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if current_sig_text:
                            fp["baseline_code_signature_text"] = str(current_sig_text)
                        if current_doc_hash:
                            fp["baseline_code_docstring_hash"] = str(current_doc_hash)

                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if current_sig_text:
                            fp["baseline_code_signature_text"] = str(current_sig_text)
                        if current_doc_hash:
                            fp["baseline_code_docstring_hash"] = str(current_doc_hash)

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
                        k: self.doc_manager._serialize_ir(v) for k, v in docs.items()
                    }
                    self.doc_manager.adapter.save(doc_path, final_data)

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        results = []
        conflicts = []
        for module in modules:
            res, conf = self._analyze_file(module.file_path)
            results.append(res)
            conflicts.extend(conf)
        return results, conflicts

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
            chosen_actions = self.interaction_handler.process_interactive_session(
                conflicts
            )
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
                    reconciled_results[context.file_path]["reconcile"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.PURGE_DOC:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["purged"].append(context.fqn)
                elif action == ResolutionAction.SKIP:
                    for res in results:
                        if res.path == context.file_path:
                            error_key = {
                                ConflictType.SIGNATURE_DRIFT: "signature_drift",
                                ConflictType.CO_EVOLUTION: "co_evolution",
                                ConflictType.DANGLING_DOC: "extra",
                            }.get(context.conflict_type, "unknown")
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False

            self._apply_resolutions(dict(resolutions_by_file))

            for res in results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]
                    res.reconciled["purged"] = reconciled_results[res.path].get(
                        "purged", []
                    )
        else:
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(conflicts)
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = (
                        "force_relink"
                        if action == ResolutionAction.RELINK
                        else "reconcile"
                    )
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                    for res in results:
                        if res.path == context.file_path:
                            error_key = {
                                ConflictType.SIGNATURE_DRIFT: "signature_drift",
                                ConflictType.CO_EVOLUTION: "co_evolution",
                                ConflictType.DANGLING_DOC: "extra",
                            }.get(context.conflict_type, "unknown")
                            res.errors[error_key].append(context.fqn)

            self._apply_resolutions(dict(resolutions_by_file))
            for res in results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]
        return True

    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_file(module.file_path)

    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0
        for res in results:
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)
            if res.is_clean:
                continue
            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
                for key in res.reconciled.get("purged", []):
                    bus.success(L.check.state.purged, key=key, path=res.path)
            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)
            for key in sorted(res.errors["extra"]):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(res.errors["signature_drift"]):
                bus.error(L.check.state.signature_drift, key=key)
            for key in sorted(res.errors["co_evolution"]):
                bus.error(L.check.state.co_evolution, key=key)
            for key in sorted(res.errors["conflict"]):
                bus.error(L.check.issue.conflict, key=key)
            for key in sorted(res.errors["pending"]):
                bus.error(L.check.issue.pending, key=key)
            for key in sorted(res.warnings["missing"]):
                bus.warning(L.check.issue.missing, key=key)
            for key in sorted(res.warnings["redundant"]):
                bus.warning(L.check.issue.redundant, key=key)
            for key in sorted(res.warnings["untracked_key"]):
                bus.warning(L.check.state.untracked_code, key=key)
            if "untracked_detailed" in res.warnings:
                keys = res.warnings["untracked_detailed"]
                bus.warning(
                    L.check.file.untracked_with_details, path=res.path, count=len(keys)
                )
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            elif "untracked" in res.warnings:
                bus.warning(L.check.file.untracked, path=res.path)

        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True
~~~~~

### 下一步建议

我们已经修复了 `CheckRunner` 的核心逻辑，使其能够正确处理所有文档状态。现在，测试应该能够全部通过。

如果测试通过，我将生成一个 `[COMMIT]` 计划，将 `CheckRunner` 的 "Query-First" 重构作为一个完整的、经过验证的工作单元进行提交。
