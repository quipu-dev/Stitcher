这是关于 Runner 架构重构的计划。

我们将通过 **控制反转 (IoC)** 模式，将配置加载、文件扫描和服务配置的职责从各个 `Runner` 上浮至 `StitcherApp`。`Runner` 将转变为无状态（或低状态）的执行器，仅负责处理由 App 准备好的数据（`ModuleDef` 列表）。

## [WIP] refactor: 重构 Runner 架构以解耦配置加载与业务执行

### 用户需求
当前的 Runner 设计违反了单一职责原则，将配置加载、文件扫描和业务逻辑耦合在一起。这导致无法统一注入服务策略（如 `DocstringStyle`），且代码重复度高。需要重构架构，由 `StitcherApp` 统一负责上下文准备，Runner 专注于业务执行。

### 评论
这是一个关键的架构治理。虽然代码量较大，但逻辑清晰。它将消除 `load_config_from_path` 在代码库中的重复调用，并为后续的“多风格文档支持”打下坚实的基础。这也使得 Runner 更容易被单元测试（因为不再依赖文件系统中的配置文件）。

### 目标
1.  **StitcherApp**: 承担 Orchestrator 角色，负责加载 Config、配置 Service、扫描 Files，并将准备好的 `modules` 传递给 Runner。
2.  **Runner**: 剥离 Config Loading 和 Scanning 逻辑，提供 `run_batch` 或类似接口，接受 `List[ModuleDef]` 和 `StitcherConfig`。
3.  **CheckRunner**: 将 Analysis, Resolution, Reporting 逻辑解耦，支持由 App 驱动的批量处理。

### 基本原理
通过将“数据获取（Scanning）”与“数据处理（Runner Execution）”分离，我们实现了一个典型的 **管道-过滤器（Pipeline-Filter）** 架构。`StitcherApp` 作为管道控制器，负责输送数据；Runner 作为过滤器，负责处理数据。这不仅解决了 Config 注入的问题，也使得 Multi-target 的处理逻辑收敛到了唯一的一处（`StitcherApp`）。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #task/domain/architecture #task/object/runners #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 `CheckRunner`
CheckRunner 是最复杂的，我们需要将其拆分为“分析阶段”和“报告阶段”。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
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
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
        self.interaction_handler = interaction_handler

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
            module_def = ModuleDef(file_path=file_path)
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
            res, conf = self._analyze_file(module)
            results.append(res)
            conflicts.extend(conf)
        return results, conflicts

    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ):
        for res in results:
            if res.infos["doc_improvement"]:
                module_def = next(
                    (m for m in modules if m.file_path == res.path), None
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
                            new_hashes[fqn]["baseline_yaml_content_hash"] = (
                                new_yaml_hash
                            )
                        elif "baseline_yaml_content_hash" in new_hashes[fqn]:
                            del new_hashes[fqn]["baseline_yaml_content_hash"]

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)

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
            self.sig_manager.reformat_hashes_for_module(module)

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

#### Acts 2: 重构 `GenerateRunner`

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/generate.py
~~~~~
~~~~~python
from typing import List, Optional
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import StitcherConfig
from stitcher.spec import ModuleDef, StubGeneratorProtocol
from stitcher.app.services import (
    DocumentManager,
    StubPackageManager,
    ScannerService,
)


class GenerateRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        stub_pkg_manager: StubPackageManager,
        generator: StubGeneratorProtocol,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.stub_pkg_manager = stub_pkg_manager
        self.generator = generator

    def _scaffold_stub_package(
        self, config: StitcherConfig, stub_base_name: Optional[str]
    ):
        if not config.stub_package or not stub_base_name:
            return
        pkg_path = self.root_path / config.stub_package
        package_namespace: str = ""
        for path_str in config.scan_paths:
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                # This handles cases like 'src/my_app' where 'my_app' is the namespace.
                package_namespace = path_parts[-1]
                break

        if not package_namespace:
            # Fallback for when all scan_paths end in 'src'.
            # Derives namespace from the target name (e.g., 'stitcher-cli' -> 'stitcher').
            package_namespace = stub_base_name.split("-")[0]
        stub_pkg_name = f"{stub_base_name}-stubs"
        bus.info(L.generate.stub_pkg.scaffold, name=stub_pkg_name)
        created = self.stub_pkg_manager.scaffold(
            pkg_path, stub_base_name, package_namespace
        )
        if created:
            bus.success(L.generate.stub_pkg.success, name=stub_pkg_name)
        else:
            bus.info(L.generate.stub_pkg.exists, name=stub_pkg_name)

    def run_batch(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        project_name: Optional[str] = None,
    ) -> List[Path]:
        generated_files: List[Path] = []
        created_py_typed: set[Path] = set()

        if config.stub_package:
            stub_base_name = config.name if config.name != "default" else project_name
            self._scaffold_stub_package(config, stub_base_name)

        for module in modules:
            self.doc_manager.apply_docs_to_module(module)
            pyi_content = self.generator.generate(module)
            if config.stub_package:
                logical_path = self.scanner.derive_logical_path(module.file_path)
                stub_logical_path = self.stub_pkg_manager._get_pep561_logical_path(
                    logical_path
                )
                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )
                if stub_logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / stub_logical_path.parts[0]
                    )
                    if top_level_pkg_dir not in created_py_typed:
                        top_level_pkg_dir.mkdir(parents=True, exist_ok=True)
                        (top_level_pkg_dir / "py.typed").touch(exist_ok=True)
                        created_py_typed.add(top_level_pkg_dir)
            elif config.stub_path:
                logical_path = self.scanner.derive_logical_path(module.file_path)
                output_path = (
                    self.root_path / config.stub_path / logical_path.with_suffix(".pyi")
                )
            else:
                output_path = self.root_path / Path(module.file_path).with_suffix(
                    ".pyi"
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    (current / "__init__.pyi").touch(exist_ok=True)
                    current = current.parent
            output_path.write_text(pyi_content, encoding="utf-8")
            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
~~~~~

#### Acts 3: 重构 `InitRunner`

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python
from typing import List, Dict
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import Fingerprint, ModuleDef
from stitcher.app.services import DocumentManager, SignatureManager


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager

    def run_batch(self, modules: List[ModuleDef]) -> List[Path]:
        created_files: List[Path] = []
        for module in modules:
            output_path = self.doc_manager.save_docs_for_module(module)

            # Use the new unified compute method
            computed_fingerprints = self.sig_manager.compute_fingerprints(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

            combined: Dict[str, Fingerprint] = {}
            all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

            for fqn in all_fqns:
                # Get the base computed fingerprint (code structure, sig text, etc.)
                fp = computed_fingerprints.get(fqn, Fingerprint())

                # Convert 'current' keys to 'baseline' keys for storage
                if "current_code_structure_hash" in fp:
                    fp["baseline_code_structure_hash"] = fp[
                        "current_code_structure_hash"
                    ]
                    del fp["current_code_structure_hash"]

                if "current_code_signature_text" in fp:
                    fp["baseline_code_signature_text"] = fp[
                        "current_code_signature_text"
                    ]
                    del fp["current_code_signature_text"]

                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]

                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
                created_files.append(output_path)
        return created_files
~~~~~

#### Acts 4: 重构 `PumpRunner`

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
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
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
    DocstringMerger,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        differ: Differ,
        merger: DocstringMerger,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.differ = differ
        self.merger = merger
        self.interaction_handler = interaction_handler

    def _generate_execution_plan(
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager.flatten_module_docs(module)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                pass
            else:
                exec_plan.update_code_fingerprint = True

                if decision == ResolutionAction.HYDRATE_OVERWRITE or (
                    decision is None and has_source_doc
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

    def run_batch(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        strip: bool = False,
        force: bool = False,
        reconcile: bool = False,
    ) -> PumpResult:
        all_conflicts: List[InteractionContext] = []

        # --- Phase 1: Analysis ---
        for module in modules:
            res = self.doc_manager.hydrate_module(
                module, force=False, reconcile=False, dry_run=True
            )
            if not res["success"]:
                source_docs = self.doc_manager.flatten_module_docs(module)
                yaml_docs = self.doc_manager.load_docs_for_module(module)
                for key in res["conflicts"]:
                    yaml_summary = yaml_docs[key].summary if key in yaml_docs else ""
                    src_summary = (
                        source_docs[key].summary if key in source_docs else ""
                    )
                    doc_diff = self.differ.generate_text_diff(
                        yaml_summary or "",
                        src_summary or "",
                        "yaml",
                        "code",
                    )
                    all_conflicts.append(
                        InteractionContext(
                            module.file_path,
                            key,
                            ConflictType.DOC_CONTENT_CONFLICT,
                            doc_diff=doc_diff,
                        )
                    )

        # --- Phase 2: Decision ---
        decisions: Dict[str, ResolutionAction] = {}
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

        # --- Phase 3 & 4: Planning & Execution ---
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        for module in modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)

            source_docs = self.doc_manager.flatten_module_docs(module)
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module)
            current_fingerprints = self.sig_manager.compute_fingerprints(module)

            new_yaml_docs = current_yaml_docs.copy()
            new_hashes = copy.deepcopy(stored_hashes)

            file_had_updates = False
            file_has_errors = False
            file_has_redundancy = False
            updated_keys_in_file = []
            reconciled_keys_in_file = []

            for fqn, plan in file_plan.items():
                if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                    unresolved_conflicts_count += 1
                    file_has_errors = True
                    bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                    continue

                if plan.hydrate_yaml:
                    if fqn in source_docs:
                        src_ir = source_docs[fqn]
                        existing_ir = new_yaml_docs.get(fqn)
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
                        fp["baseline_code_structure_hash"] = current_fp[
                            "current_code_structure_hash"
                        ]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp[
                            "current_code_signature_text"
                        ]
                    fqn_was_updated = True

                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            serialized = self.doc_manager._serialize_ir(ir_to_save)
                            doc_hash = self.doc_manager.compute_yaml_content_hash(
                                serialized
                            )
                            fp["baseline_yaml_content_hash"] = doc_hash
                            fqn_was_updated = True

                if fqn_was_updated:
                    new_hashes[fqn] = fp

                if (
                    fqn in decisions
                    and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                ):
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)

                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            signatures_need_save = new_hashes != stored_hashes

            if not file_has_errors:
                if file_had_updates:
                    final_data = {
                        k: self.doc_manager._serialize_ir(v)
                        for k, v in new_yaml_docs.items()
                    }
                    module_path = self.root_path / module.file_path
                    doc_path = module_path.with_suffix(".stitcher.yaml")
                    self.doc_manager.adapter.save(doc_path, final_data)

                if signatures_need_save:
                    self.sig_manager.save_composite_hashes(module, new_hashes)

                if file_has_redundancy:
                    redundant_files_list.append(self.root_path / module.file_path)

            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(updated_keys_in_file),
                )

            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(reconciled_keys_in_file),
                )

        # --- Phase 5: Stripping ---
        if strip_jobs:
            total_stripped_files = 0
            for file_path, whitelist in strip_jobs.items():
                source_path = self.root_path / file_path
                if not whitelist:
                    continue
                try:
                    original_content = source_path.read_text("utf-8")
                    stripped_content = self.transformer.strip(
                        original_content, whitelist=whitelist
                    )
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, "utf-8")
                        bus.success(
                            L.strip.file.success,
                            path=source_path.relative_to(self.root_path),
                        )
                        total_stripped_files += 1
                except Exception as e:
                    bus.error(L.error.generic, error=e)

            if total_stripped_files > 0:
                bus.success(L.strip.run.complete, count=total_stripped_files)

        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)

        has_activity = (total_updated_keys > 0) or strip_jobs
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)

        return PumpResult(success=True, redundant_files=redundant_files_list)
~~~~~

#### Acts 5: 重构 `CoverageRunner`

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/coverage.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List
import typer

from stitcher.app.services import DocumentManager
from stitcher.app.types import CoverageResult
from stitcher.spec import ModuleDef


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager

    def _analyze_module_coverage(self, module: ModuleDef) -> CoverageResult:
        public_fqns = module.get_public_documentable_fqns()
        documented_fqns = set(self.doc_manager.load_docs_for_module(module).keys())

        if module.docstring and "__doc__" in public_fqns:
            documented_fqns.add("__doc__")

        total = len(public_fqns)
        documented = len(public_fqns.intersection(documented_fqns))
        missing = total - documented
        coverage = (documented / total * 100) if total > 0 else 100.0

        return CoverageResult(
            path=module.file_path,
            total_symbols=total,
            documented_symbols=documented,
            missing_symbols=missing,
            coverage=coverage,
        )

    def run_batch(self, modules: List[ModuleDef]) -> List[CoverageResult]:
        results = []
        for module in modules:
            results.append(self._analyze_module_coverage(module))
        return results

    def report(self, results: List[CoverageResult]):
        if not results:
            return

        paths = [r.path for r in results if r.total_symbols > 0]
        max_path_len = max(len(p) for p in paths) if paths else 0
        name_col_width = max(len("Name"), len("TOTAL"), max_path_len)

        stmts_col_width = 7
        miss_col_width = 7
        cover_col_width = 10

        total_width = (
            name_col_width + stmts_col_width + miss_col_width + cover_col_width + 3
        )

        typer.echo("\n" + ("-" * total_width))
        typer.secho(
            f"{'Name':<{name_col_width}} {'Stmts':>{stmts_col_width}} {'Miss':>{miss_col_width}} {'Cover':>{cover_col_width}}",
            bold=True,
        )
        typer.echo("-" * total_width)

        total_stmts = 0
        total_miss = 0

        for res in sorted(results, key=lambda r: r.path):
            if res.total_symbols == 0:
                continue

            total_stmts += res.total_symbols
            total_miss += res.missing_symbols

            cover_str = f"{res.coverage:.1f}%"

            color = typer.colors.GREEN
            if res.coverage < 50:
                color = typer.colors.RED
            elif res.coverage < 90:
                color = typer.colors.YELLOW

            typer.secho(
                (
                    f"{res.path:<{name_col_width}} "
                    f"{res.total_symbols:>{stmts_col_width}} "
                    f"{res.missing_symbols:>{miss_col_width}} "
                    f"{cover_str:>{cover_col_width}}"
                ),
                fg=color,
            )

        typer.echo("-" * total_width)

        total_coverage = (
            ((total_stmts - total_miss) / total_stmts * 100)
            if total_stmts > 0
            else 100.0
        )
        cover_str = f"{total_coverage:.1f}%"
        typer.secho(
            (
                f"{'TOTAL':<{name_col_width}} "
                f"{total_stmts:>{stmts_col_width}} "
                f"{total_miss:>{miss_col_width}} "
                f"{cover_str:>{cover_col_width}}"
            ),
            bold=True,
        )
        typer.echo("")
~~~~~

#### Acts 6: 重构 `TransformRunner`

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/transform.py
~~~~~
~~~~~python
from typing import List
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import LanguageTransformerProtocol, ModuleDef
from stitcher.app.services import DocumentManager


class TransformRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        transformer: LanguageTransformerProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.transformer = transformer

    def run_strip(self, files: List[Path]) -> List[Path]:
        all_modified_files: List[Path] = []
        for file_path in files:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = self.transformer.strip(
                    original_content, whitelist=None
                )
                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    all_modified_files.append(file_path)
                    relative_path = file_path.relative_to(self.root_path)
                    bus.success(L.strip.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if all_modified_files:
            bus.success(L.strip.run.complete, count=len(all_modified_files))
        return all_modified_files

    def run_inject_batch(self, modules: List[ModuleDef]) -> List[Path]:
        modified_files: List[Path] = []
        total_docs_found = 0

        for module in modules:
            docs_ir = self.doc_manager.load_docs_for_module(module)
            if not docs_ir:
                continue
            total_docs_found += len(docs_ir)

            docs_str = {k: v.summary or "" for k, v in docs_ir.items()}
            source_path = self.root_path / module.file_path
            try:
                original_content = source_path.read_text(encoding="utf-8")
                injected_content = self.transformer.inject(original_content, docs_str)
                if original_content != injected_content:
                    source_path.write_text(injected_content, encoding="utf-8")
                    modified_files.append(source_path)
                    relative_path = source_path.relative_to(self.root_path)
                    bus.success(L.inject.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        return modified_files
~~~~~

#### Acts 7: 更新 `StitcherApp` 以编排新 Runner
最后，更新 `StitcherApp`，实现统一的 Loop 和 Context 管理。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Optional, Tuple

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
    ModuleDef,
)
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
)
from .types import PumpResult, FileCheckResult, CoverageResult


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
        self.differ = Differ()
        self.merger = DocstringMerger()

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
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
            root_path, self.doc_manager, self.sig_manager
        )
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
            bus.info(L.generate.target.processing, name=config.name)
        
        # Future: self.doc_manager.set_strategy(config.docstring_style)

        # Handle Plugins
        plugin_modules = self.scanner.process_plugins(config.plugins)
        
        # Handle Files
        unique_files = self.scanner.get_files_from_config(config)
        source_modules = self.scanner.scan_files(unique_files)
        
        all_modules = source_modules + plugin_modules
        if not all_modules:
            # We don't warn here per config, but maybe we should?
            # Original logic warned if ALL configs yielded nothing.
            pass
            
        return all_modules

    def run_from_config(self) -> List[Path]:
        configs, project_name = self._load_configs()
        all_generated: List[Path] = []
        found_any = False
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            found_any = True
            
            paths = self.generate_runner.run_batch(modules, config, project_name)
            all_generated.extend(paths)
            
        if not found_any and len(configs) == 1:
             bus.warning(L.warning.no_files_or_plugins_found)

        if all_generated:
            bus.success(L.generate.run.complete, count=len(all_generated))
        return all_generated

    def run_init(self) -> List[Path]:
        configs, _ = self._load_configs()
        all_created: List[Path] = []
        found_any = False

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            found_any = True
            
            created = self.init_runner.run_batch(modules)
            all_created.extend(created)
            
        if not found_any:
            bus.info(L.init.no_docs_found)
        elif all_created:
            bus.success(L.init.run.complete, count=len(all_created))
        else:
            bus.info(L.init.no_docs_found)
            
        return all_created

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            all_modules.extend(modules)
            
            results, conflicts = self.check_runner.analyze_batch(modules)
            
            # Interactive resolution is tricky across batches if we want to support 'abort'.
            # But typically we resolve per batch or resolve all at once.
            # Original logic resolved ALL at once.
            # Let's aggregate first.
            all_results.extend(results)
            
            # Auto-reconcile docs (infos) immediately per batch or globally?
            # Modules are needed for re-saving.
            self.check_runner.auto_reconcile_docs(results, modules)

            # Resolve conflicts for this batch
            if not self.check_runner.resolve_conflicts(results, conflicts, force_relink, reconcile):
                return False

        # Reformat All
        self.check_runner.reformat_all(all_modules)

        # Final Report
        return self.check_runner.report(all_results)

    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = self._load_configs()
        
        global_success = True
        all_redundant: List[Path] = []
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            
            result = self.pump_runner.run_batch(modules, config, strip, force, reconcile)
            if not result.success:
                global_success = False
            all_redundant.extend(result.redundant_files)

        return PumpResult(success=global_success, redundant_files=all_redundant)

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        files_to_process = []
        if files:
            files_to_process = files
        else:
            configs, _ = self._load_configs()
            for config in configs:
                files_to_process.extend(self.scanner.get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))
            
        return self.transform_runner.run_strip(files_to_process)

    def run_inject(self) -> List[Path]:
        configs, _ = self._load_configs()
        all_modified: List[Path] = []
        found_any_docs = False
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            
            # We assume if modules exist, docs might exist.
            # Transform runner will check doc existence.
            modified = self.transform_runner.run_inject_batch(modules)
            if modified:
                found_any_docs = True
            all_modified.extend(modified)
            
        if all_modified:
            bus.success(L.inject.run.complete, count=len(all_modified))
        elif not found_any_docs:
            bus.info(L.inject.no_docs_found)
            
        return all_modified

    def run_cov(self) -> bool:
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []
        
        for config in configs:
            modules = self._configure_and_scan(config)
            results = self.coverage_runner.run_batch(modules)
            all_results.extend(results)
            
        self.coverage_runner.report(all_results)
        return True
~~~~~

### 下一步建议
我们已经完成了核心架构的重构。Runner 现在是无状态的、可测试的单元。下一步，我们可以重新尝试实施 **阶段 2: 核心解耦与集成** 的任务，即向 `DocumentManager` 和 `StitcherApp` 中注入 `DocstringSerializer` 策略。由于现在的架构已经支持在 `_configure_and_scan` 中统一配置服务，这将变得非常容易。
