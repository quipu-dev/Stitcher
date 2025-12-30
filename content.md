好的，我们继续。现在我将提取最复杂的 `CheckRunner` 和 `PumpRunner`，并最终重构 `StitcherApp` 使其成为一个轻量级的协调器。

## [WIP] refactor: 提取 Check/Pump Runners 并重构 StitcherApp

### 用户需求
继续对 `packages/stitcher-application/src/stitcher/app/core.py` 进行重构，提取剩余的业务逻辑。

### 评论
这是本次重构的核心部分。`check` 和 `pump` 命令的逻辑最为复杂，包含了状态分析、冲突解决和文件系统写操作。将它们各自封装到独立的 Runner 中，将最终实现我们分离关注点的目标。`StitcherApp` 将彻底转变为一个干净的、易于理解的入口点。

### 目标
1.  创建 `stitcher.app.runners.check` 模块，并将 `check` 命令的所有相关逻辑迁移到 `CheckRunner` 类中。
2.  创建 `stitcher.app.runners.pump` 模块，并将 `pump` 命令的所有相关逻辑迁移到 `PumpRunner` 类中。
3.  重写 `stitcher.app.core.StitcherApp`，移除所有具体的业务逻辑实现，使其仅负责初始化服务和 Runners，并将外部调用委托给相应的 Runner 执行。
4.  更新 `runners/__init__.py` 以导出所有 Runner。

### 基本原理
通过完成 `CheckRunner` 和 `PumpRunner` 的提取，我们完成了对命令执行逻辑的全面封装。`StitcherApp` 的职责被简化为依赖注入和高级流程协调，这使得整个应用核心的结构更加清晰，符合单一职责原则，并为未来的功能扩展和测试打下了坚实的基础。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #scope/core #ai/instruct
#task/domain/app-core #task/object/stitcher-app #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 提取 CheckRunner
`check` 命令的逻辑包含文件分析、自动调和、交互式冲突解决等，是整个应用中最复杂的部分之一。我们将其完整地迁移到 `CheckRunner` 中。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python
import copy
import difflib
from pathlib import Path
from typing import List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.interaction_handler = interaction_handler

    def _generate_diff(self, a: str, b: str, label_a: str, label_b: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )

    def _analyze_file(
        self, module: ModuleDef
    ) -> tuple[FileCheckResult, list[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: list[InteractionContext] = []

        # Content checks (unchanged)
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            result.errors["extra"].extend(doc_issues["extra"])

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )

        computed_fingerprints = self.sig_manager.compute_fingerprints(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

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
                    sig_diff = self._generate_diff(
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

    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        for file_path, fqn_actions in resolutions.items():
            module_def = ModuleDef(file_path=file_path)  # Minimal def for path logic
            stored_hashes = self.sig_manager.load_composite_hashes(module_def)
            new_hashes = copy.deepcopy(stored_hashes)

            full_module_def = self.parser.parse(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            computed_fingerprints = self.sig_manager.compute_fingerprints(
                full_module_def
            )
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
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

    def run(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        all_results: list[FileCheckResult] = []
        all_conflicts: list[InteractionContext] = []
        all_modules: list[ModuleDef] = []

        # 1. Analysis Phase
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            all_modules.extend(modules)
            for module in modules:
                result, conflicts = self._analyze_file(module)
                all_results.append(result)
                all_conflicts.extend(conflicts)

        # 2. Execution Phase (Auto-reconciliation for doc improvements)
        for res in all_results:
            if res.infos["doc_improvement"]:
                module_def = next(
                    (m for m in all_modules if m.file_path == res.path), None
                )
                if not module_def:
                    continue

                stored_hashes = self.sig_manager.load_composite_hashes(module_def)
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module_def
                )

                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_yaml_hash = current_yaml_map.get(fqn)
                        if new_yaml_hash is not None:
                            new_hashes[fqn]["baseline_yaml_content_hash"] = new_yaml_hash
                        elif "baseline_yaml_content_hash" in new_hashes[fqn]:
                            del new_hashes[fqn]["baseline_yaml_content_hash"]

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)

        # 3. Interactive Resolution Phase
        if all_conflicts and self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(
                all_conflicts
            )
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["force_relink"].append(context.fqn)
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["reconcile"].append(context.fqn)
                elif action == ResolutionAction.SKIP:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = "signature_drift" if context.conflict_type == ConflictType.SIGNATURE_DRIFT else "co_evolution"
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False

            self._apply_resolutions(dict(resolutions_by_file))

            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path]["force_relink"]
                    res.reconciled["reconcile"] = reconciled_results[res.path]["reconcile"]
        else:
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = "force_relink" if action == ResolutionAction.RELINK else "reconcile"
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = "signature_drift" if context.conflict_type == ConflictType.SIGNATURE_DRIFT else "co_evolution"
                            res.errors[error_key].append(context.fqn)
            self._apply_resolutions(dict(resolutions_by_file))
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path]["force_relink"]
                    res.reconciled["reconcile"] = reconciled_results[res.path]["reconcile"]

        # 4. Reformatting Phase
        bus.info(L.check.run.reformatting)
        for module in all_modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_module(module)

        # 5. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
        for res in all_results:
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)
            if res.is_clean:
                continue
            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
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
                bus.warning(L.check.file.untracked_with_details, path=res.path, count=len(keys))
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

#### Acts 2: 提取 PumpRunner
`pump` 命令的逻辑同样复杂，它负责从代码中提取文档、处理冲突、更新签名，并可选地剥离源码中的文档。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python
import copy
import difflib
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    LanguageParserProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.interaction_handler = interaction_handler

    def _generate_diff(self, a: str, b: str, label_a: str, label_b: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )
    
    def _generate_execution_plan(
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
    ) -> Dict[str, FunctionExecutionPlan]:
        """根据用户决策和命令行标志，生成最终的函数级执行计划。"""
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager.flatten_module_docs(module)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                pass  # All flags default to False
            elif (
                decision == ResolutionAction.HYDRATE_OVERWRITE
                or (decision is None and has_source_doc)
            ):
                exec_plan.hydrate_yaml = True
                exec_plan.update_doc_fingerprint = True
                if strip_requested:
                    exec_plan.strip_source_docstring = True
            elif decision == ResolutionAction.HYDRATE_KEEP_EXISTING:
                if strip_requested:
                    exec_plan.strip_source_docstring = True

            plan[fqn] = exec_plan

        return plan

    def run(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # --- Phase 1: Analysis ---
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            if not modules: continue
            all_modules.extend(modules)

            for module in modules:
                res = self.doc_manager.hydrate_module(module, force=force, reconcile=reconcile, dry_run=True)
                if not res["success"]:
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)
                    for key in res["conflicts"]:
                        doc_diff = self._generate_diff(yaml_docs.get(key, ""), source_docs.get(key, ""), "yaml", "code")
                        all_conflicts.append(InteractionContext(module.file_path, key, ConflictType.DOC_CONTENT_CONFLICT, doc_diff=doc_diff))

        # --- Phase 2: Decision ---
        decisions: Dict[str, ResolutionAction] = {}
        if all_conflicts:
            handler = self.interaction_handler or NoOpInteractionHandler(hydrate_force=force, hydrate_reconcile=reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                decisions[context.fqn] = action

        # --- Phase 3 & 4: Planning & Execution ---
        strip_jobs = defaultdict(list)
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0
        
        for module in all_modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)
            
            source_docs = self.doc_manager.flatten_module_docs(module)
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module)
            
            new_yaml_docs = current_yaml_docs.copy()
            new_hashes = copy.deepcopy(stored_hashes)
            
            file_had_updates = False
            updated_keys_in_file = []
            reconciled_keys_in_file = []

            for fqn, plan in file_plan.items():
                if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                    unresolved_conflicts_count += 1
                    bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                    continue

                if plan.hydrate_yaml:
                    if fqn in source_docs and new_yaml_docs.get(fqn) != source_docs[fqn]:
                        new_yaml_docs[fqn] = source_docs[fqn]
                        updated_keys_in_file.append(fqn)
                        file_had_updates = True

                fp = new_hashes.get(fqn) or Fingerprint()
                
                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        doc_hash = self.doc_manager.compute_yaml_content_hash(source_docs[fqn])
                        fp["baseline_yaml_content_hash"] = doc_hash
                        if fqn not in stored_hashes:
                             current_fp = self.sig_manager.compute_fingerprints(module).get(fqn, Fingerprint())
                             if "current_code_structure_hash" in current_fp:
                                 fp["baseline_code_structure_hash"] = current_fp["current_code_structure_hash"]
                        new_hashes[fqn] = fp
                        file_had_updates = True
                
                if fqn in decisions and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING:
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)

            if file_had_updates:
                module_path = self.root_path / module.file_path
                doc_path = module_path.with_suffix(".stitcher.yaml")
                self.doc_manager.adapter.save(doc_path, new_yaml_docs)
                self.sig_manager.save_composite_hashes(module, new_hashes)
                
            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(L.pump.file.success, path=module.file_path, count=len(updated_keys_in_file))
            
            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(L.pump.info.reconciled, path=module.file_path, count=len(reconciled_keys_in_file))

        # --- Phase 5: Stripping ---
        if strip_jobs:
            for file_path, whitelist in strip_jobs.items():
                source_path = self.root_path / file_path
                if not whitelist: continue
                try:
                    original_content = source_path.read_text("utf-8")
                    stripped_content = self.transformer.strip(original_content, whitelist=whitelist)
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, "utf-8")
                        bus.success(L.strip.file.success, path=source_path.relative_to(self.root_path))
                except Exception as e:
                    bus.error(L.error.generic, error=e)
        
        # Final Reporting
        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)
        
        if total_updated_keys == 0 and total_reconciled_keys == 0 and not strip_jobs:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)

        return PumpResult(success=True, redundant_files=[])
~~~~~

#### Acts 3: 更新 Runners 的 `__init__.py`
导出所有新建的 Runner 类，以便 `StitcherApp` 可以方便地导入它们。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/__init__.py
~~~~~
~~~~~python
from .check import CheckRunner
from .generate import GenerateRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner

__all__ = [
    "CheckRunner",
    "GenerateRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
]
~~~~~

#### Acts 4: 重构核心 StitcherApp
这是最后一步，我们将 `core.py` 中的 `StitcherApp` 彻底重构为一个轻量级的协调器。它将不再包含任何业务逻辑的实现，只负责创建和协调 Runners。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Optional

from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
)
from .types import PumpResult


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        stub_generator: StubGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            transformer,
            interaction_handler,
        )
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
        )
        self.init_runner = InitRunner(
            root_path, self.scanner, self.doc_manager, self.sig_manager
        )
        self.transform_runner = TransformRunner(
            root_path, self.scanner, self.doc_manager, transformer
        )

    def run_from_config(self) -> List[Path]:
        return self.generate_runner.run()

    def run_init(self) -> List[Path]:
        return self.init_runner.run()

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        return self.check_runner.run(force_relink=force_relink, reconcile=reconcile)

    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        # Pass-through all options to the dedicated runner
        result = self.pump_runner.run(strip=strip, force=force, reconcile=reconcile)
        
        # The secondary, interactive strip confirmation logic remains here for now,
        # as it's a cross-command concern (pump -> strip).
        # A more advanced implementation might use an event bus or a post-execution hook.
        if (
            self.pump_runner.interaction_handler
            and result.redundant_files
            and not strip
        ):
            import typer # Lazy import for CLI-specific interaction
            typer.echo("")
            typer.secho(
                f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.",
                fg=typer.colors.YELLOW,
            )
            if typer.confirm("Do you want to strip them now?", default=True):
                self.run_strip(files=result.redundant_files)

        return result


    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        return self.transform_runner.run_strip(files=files)

    def run_inject(self) -> List[Path]:
        return self.transform_runner.run_inject()
~~~~~
