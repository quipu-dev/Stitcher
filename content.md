# [WIP] refactor(check): 将 CheckRunner 拆分为模块化组件

## 摘要头

### 用户需求

用户指出 `check.py` 文件已成为“面条代码”（逻辑复杂、职责纠缠），要求在实施新的 Index-First 逻辑之前，先对其进行结构上的拆分和重构。

### 评论

这是一个非常必要的“战术性撤退”。在当前的单文件结构上强行实施新的状态机逻辑会极大地增加认知负担和出错风险。通过将 `CheckRunner` 拆分为 `Analyzer`（读/分析）、`Resolver`（写/解决）和 `Reporter`（UI/报告）三个独立的关注点，我们为即将到来的逻辑重写创造了一个清晰、隔离的舞台。这完全符合“关注点分离”的架构原则。

### 目标

1.  创建 `packages/stitcher-application/src/stitcher/app/runners/check/` 目录。
2.  将原 `check.py` 的逻辑拆分到以下组件：
    *   `reporter.py`: 负责向 Message Bus 输出结果报告。
    *   `resolver.py`: 负责处理交互式冲突解决、应用变更和自动调和。
    *   `analyzer.py`: 负责文件分析、指纹计算和状态判定。
    *   `runner.py`: 作为外观（Facade），协调上述组件的工作。
3.  删除原有的 `check.py`。
4.  确保对外接口（`CheckRunner` 类及其方法签名）保持不变，以兼容现有调用方。

### 基本原理

*   **物理隔离**：将 300+ 行的代码拆分为多个 <100 行的文件，降低维护难度。
*   **职责单一**：
    *   `Analyzer` 只负责产生 `FileCheckResult` 和 `InteractionContext`。
    *   `Resolver` 只负责消费 Context 并产生 Side Effects。
    *   `Reporter` 只负责展示。
*   **为未来铺路**：下一步的“Index-First”重构将主要集中在 `Analyzer` 中，而无需触碰 `Resolver` 或 `Reporter`。

### 标签

#intent/refine #flow/ready #priority/high #comp/application #task/domain/quality #task/object/check-runner #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建目录结构

首先，我们为新的模块创建目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-application/src/stitcher/app/runners/check
~~~~~

#### Acts 2: 提取 Reporter 组件

将报告逻辑提取到 `reporter.py`。这是最独立的组件，只依赖于 `bus` 和数据类型。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python
from typing import List
from stitcher.common import bus
from needle.pointer import L
from stitcher.app.types import FileCheckResult


class CheckReporter:
    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0

        for res in results:
            # 1. Info / Success Messages
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)
            
            if res.is_clean:
                continue

            # 2. Reconciled Actions
            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
                for key in res.reconciled.get("purged", []):
                    bus.success(L.check.state.purged, key=key, path=res.path)

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
        # Errors
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

        # Warnings
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
~~~~~

#### Acts 3: 提取 Resolver 组件

将冲突解决、应用和自动调和逻辑提取到 `resolver.py`。这个组件包含了大部分的“副作用”逻辑。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Any

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
from stitcher.app.services import DocumentManager, SignatureManager
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult


class CheckResolver:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
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
                error_key = {
                    ConflictType.SIGNATURE_DRIFT: "signature_drift",
                    ConflictType.CO_EVOLUTION: "co_evolution",
                    ConflictType.DANGLING_DOC: "extra",
                }.get(context.conflict_type, "unknown")
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
                        k: self.doc_manager._serialize_ir(v) for k, v in docs.items()
                    }
                    self.doc_manager.adapter.save(doc_path, final_data)

    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_file(module.file_path)
~~~~~

#### Acts 4: 提取 Analyzer 组件

提取 `_analyze_file` 及其相关逻辑到 `analyzer.py`。这是“读”逻辑，也是下一步 Index-First 重构的核心区域。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/analyzer.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Tuple, Dict

from stitcher.spec import (
    ModuleDef,
    ConflictType,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager, Differ
from stitcher.app.protocols import InteractionContext
from stitcher.app.types import FileCheckResult


class CheckAnalyzer:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
        self.fingerprint_strategy = fingerprint_strategy

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        results = []
        conflicts = []
        for module in modules:
            res, conf = self._analyze_file(module)
            results.append(res)
            conflicts.extend(conf)
        return results, conflicts

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def _analyze_file(
        self, module: ModuleDef
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: List[InteractionContext] = []

        # Content checks
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            for fqn in doc_issues["extra"]:
                unresolved_conflicts.append(
                    InteractionContext(module.file_path, fqn, ConflictType.DANGLING_DOC)
                )

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )

        computed_fingerprints = self._compute_fingerprints(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module.file_path)

        all_fqns = set(computed_fingerprints.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            computed_fp = computed_fingerprints.get(fqn, Fingerprint())

            code_hash = computed_fp.get("current_code_structure_hash")
            current_sig_text = computed_fp.get("current_code_signature_text")
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )
            baseline_sig_text = (
                stored_fp.get("baseline_code_signature_text") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                sig_diff = None
                if baseline_sig_text and current_sig_text:
                    sig_diff = self.differ.generate_text_diff(
                        baseline_sig_text,
                        current_sig_text,
                        "baseline",
                        "current",
                    )
                elif current_sig_text:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_text}"

                conflict_type = (
                    ConflictType.SIGNATURE_DRIFT
                    if yaml_matches
                    else ConflictType.CO_EVOLUTION
                )

                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, conflict_type, signature_diff=sig_diff
                    )
                )

        if not is_tracked and module.is_documentable():
            undocumented = module.get_undocumented_public_keys()
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts
~~~~~

#### Acts 5: 重组 CheckRunner

创建新的 `runner.py`，它将充当一个精简的外观类，协调上述所有组件。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Tuple

from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
from .reporter import CheckReporter


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.analyzer = CheckAnalyzer(
            root_path, doc_manager, sig_manager, differ, fingerprint_strategy
        )
        self.resolver = CheckResolver(
            root_path,
            parser,
            doc_manager,
            sig_manager,
            interaction_handler,
            fingerprint_strategy,
        )
        self.reporter = CheckReporter()

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        return self.analyzer.analyze_batch(modules)

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

#### Acts 6: 更新包导出

创建 `__init__.py` 导出新的 Runner。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/__init__.py
~~~~~
~~~~~python
from .runner import CheckRunner

__all__ = ["CheckRunner"]
~~~~~

#### Acts 7: 清理旧文件

删除原来的大文件。

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~

### 下一步建议

现在 `CheckRunner` 已经被清晰地拆解。接下来，我们可以安全地执行 Index-First 重构计划：

1.  **修改 `CheckAnalyzer`**:
    *   在 `__init__` 中注入 `IndexStore`。
    *   重写 `_analyze_file` (或者创建一个新的 `_analyze_from_index`)。
    *   不再调用 `module.is_documentable()` 或 `doc_manager.check_module(module)`。
    *   直接查询 SQLite 数据库，对比 `symbols` 表和 YAML 文件的哈希值。
    *   仅在检测到 `docstring_hash` 不一致时，从 `SymbolRecord.docstring_content` 加载内容生成 Diff。

2.  **更新 `StitcherApp`**:
    *   确保在初始化 `CheckRunner` 时传入 `index_store`。
    *   调整 `run_check` 流程，不再需要先扫描 `modules` (或者仅为了兼容性保留，但 Analyzer 内部忽略它)。

这将彻底实现我们的目标：**Zero-IO Check** (对于 Clean 文件)。
