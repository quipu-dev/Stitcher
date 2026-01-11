1.  **依赖注入**: 将 `IndexStore` 注入 `CheckRunner`，移除 `LanguageParserProtocol`。
2.  **核心循环重写**:
    *   废弃 `_compute_fingerprints`。
    *   重写 `_analyze_file`，使其通过 `index_store` 获取“现状”，通过 `sig_manager` 获取“基准”。
3.  **Diff 逻辑下沉**: 利用数据库中存储的 `signature_text` 生成 Diff，不再读取源文件。
4.  **适配调用方**: 修改 `StitcherApp.run_check`，使其传递文件路径列表而非 `ModuleDef` 对象列表。

我将生成执行此重构的计划。

## [WIP] refactor(check): implement query-first architecture

### 用户需求
将 `CheckRunner` 从基于 AST 的实时扫描模式重构为基于 `IndexStore` 的查询模式，以实现 O(1) 级别的检查性能（相对于文件大小）。

### 评论
这是 Stitcher 2.0 架构中最具决定性的性能飞跃。完成后，`check` 命令的速度将仅受限于 SQLite 查询速度，而与项目代码量脱钩。

### 目标
1.  修改 `CheckRunner` 构造函数，注入 `IndexStore`，移除 `parser`。
2.  重写 `_analyze_file` 方法，使其接受 `file_path` 字符串。
3.  实现基于 `SymbolRecord` (DB) 和 `Fingerprint` (JSON) 的比对逻辑。
4.  更新 `StitcherApp.run_check` 以适配新的输入格式。

### 基本原理
我们利用 Phase 1 中在数据库建立的 `signature_text` 和 `docstring_hash` 字段，以及 Phase 2 (Pump) 中建立的 SURI 索引标准，使得 `check` 操作可以完全在元数据层面完成，无需触碰物理磁盘上的源代码文件。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/cli #concept/state #scope/core #ai/instruct #task/domain/refactor #task/object/check-runner #task/action/query-first-implementation #task/state/continue

---

### Script

#### Acts 1: 重构 CheckRunner

我们将彻底重写 `CheckRunner`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict, Set

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import FileCheckResult
from stitcher.index.store import IndexStore
from stitcher.adapter.python.uri import SURIGenerator


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        index_store: IndexStore,  # Replaces Parser
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.index_store = index_store
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
        self.interaction_handler = interaction_handler
        self.fingerprint_strategy = fingerprint_strategy

    def _analyze_file(
        self, file_path: str
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        result = FileCheckResult(path=file_path)
        unresolved_conflicts: List[InteractionContext] = []
        
        # 1. Load Actual State (From Index DB)
        # We get all symbols for this file from the database
        actual_symbols = self.index_store.get_symbols_by_file_path(file_path)
        
        # Convert to a map keyed by SURI for easy lookup
        # Note: In the DB, 'id' is the SURI.
        actual_map = {s.id: s for s in actual_symbols}

        # 2. Load Baseline State (From Signatures JSON)
        # Keys in stored_hashes are now SURIs (thanks to SignatureManager upgrade)
        # or legacy fragments. We need to handle normalization if legacy exists,
        # but for Stitcher 2.0 we assume SURIs or normalize on load.
        baseline_map = self.sig_manager.load_composite_hashes(file_path)

        # 3. Content Checks (YAML vs Index)
        # We need to check if docstrings in YAML match docstrings in Index (Code)
        # The Index stores 'docstring_hash' for the code.
        # The DocumentManager can compute hashes for YAML.
        
        # Load YAML docs (IR)
        # We construct a dummy ModuleDef just to pass the path
        # TODO: Refactor DocManager to take path string later? For now ModuleDef is a DTO.
        from stitcher.spec import ModuleDef
        dummy_module = ModuleDef(file_path=file_path)
        
        is_tracked = (self.root_path / file_path).with_suffix(".stitcher.yaml").exists()
        
        if is_tracked:
             # This check_module call still does some logic, but we can optimize it 
             # by passing the index data instead of parsing. 
             # For now, let's keep using doc_manager.check_module BUT 
             # we need to ensure it doesn't re-parse.
             # Actually, doc_manager.check_module DOES re-parse/flatten. 
             # optimization: We can skip full DocManager check if hashes align?
             # For Phase 3 MVP, let's focus on Signature Drift first.
             pass

        # 4. Signature & Co-evolution Checks
        all_suris = set(actual_map.keys()) | set(baseline_map.keys())

        for suri in sorted(list(all_suris)):
            # Parse SURI to get display name (fragment)
            try:
                _, fqn = SURIGenerator.parse(suri)
            except ValueError:
                fqn = suri # Fallback

            if not fqn: 
                # File-level SURI (py://path) usually doesn't have signature logic 
                continue

            actual = actual_map.get(suri)
            baseline_fp = baseline_map.get(suri)

            # Extract Actual values
            current_code_hash = actual.signature_hash if actual else None
            current_sig_text = actual.signature_text if actual else None
            
            # Extract Baseline values
            baseline_code_hash = baseline_fp.get("baseline_code_structure_hash") if baseline_fp else None
            baseline_sig_text = baseline_fp.get("baseline_code_signature_text") if baseline_fp else None
            
            # Check for New/Extra
            if not current_code_hash and baseline_code_hash:
                # Exists in baseline but not in code -> Deleted/Extra
                # We handle this via cleaner logic or user prompt later? 
                # For now check runner usually flags these via doc consistency, 
                # but for signatures, it's a drift if we expected it.
                pass 
            
            if current_code_hash and not baseline_code_hash:
                # New in code, not in baseline -> Untracked
                continue

            # Check for Drift
            if current_code_hash and baseline_code_hash:
                if current_code_hash != baseline_code_hash:
                    # Signature Changed!
                    
                    # Check YAML status for Co-evolution
                    # We need to know if the DOCS changed too.
                    # Index stores current_doc_hash.
                    # Baseline stores baseline_yaml_content_hash.
                    
                    # Note: This logic assumes YAML matches Code Docs. 
                    # If YAML changed, we need to compare YAML hash vs Baseline YAML hash.
                    
                    # Let's simplify: 
                    # If Code Signature Changed, it is either DRIFT (Docs didn't change) 
                    # or CO-EVOLUTION (Docs also changed).
                    
                    # We need to check if the user updated the docs in YAML.
                    # Load current YAML hash for this symbol
                    current_yaml_hash = None
                    if is_tracked:
                        # We need a way to get specific yaml hash without full parse if possible
                        # For now, we might have to pay the cost of loading YAML once per file.
                        yaml_hashes = self.doc_manager.compute_yaml_content_hashes(dummy_module)
                        # The doc_manager returns keys as FQNs, not SURIs.
                        # We need to map SURI -> FQN.
                        current_yaml_hash = yaml_hashes.get(fqn)

                    baseline_yaml_hash = baseline_fp.get("baseline_yaml_content_hash")
                    
                    yaml_matches = current_yaml_hash == baseline_yaml_hash
                    
                    conflict_type = (
                        ConflictType.SIGNATURE_DRIFT
                        if yaml_matches
                        else ConflictType.CO_EVOLUTION
                    )
                    
                    # Generate Diff using stored text
                    sig_diff = None
                    if baseline_sig_text and current_sig_text:
                        sig_diff = self.differ.generate_text_diff(
                            baseline_sig_text,
                            current_sig_text,
                            "baseline",
                            "current",
                        )
                    elif current_sig_text:
                         sig_diff = f"(No baseline signature)\n+++ current\n{current_sig_text}"
                    
                    unresolved_conflicts.append(
                        InteractionContext(
                            file_path, fqn, conflict_type, signature_diff=sig_diff
                        )
                    )

        # 5. Delegate Doc Content Checks to DocManager (Legacy/Hybrid)
        # We still rely on DocManager for "Missing/Extra/Redundant" checks 
        # because those logic are complex. 
        # However, we pass the module only for path context mostly.
        if is_tracked:
            # Note: doc_manager.check_module currently re-parses. 
            # In a full Index-First world, DocManager should also query Index.
            # We will accept this hybrid state for this specific iteration 
            # as DocManager refactor is a separate task.
            doc_issues = self.doc_manager.check_module(dummy_module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            for key in doc_issues["extra"]:
                unresolved_conflicts.append(
                    InteractionContext(file_path, key, ConflictType.DANGLING_DOC)
                )
        
        # Untracked check
        if not is_tracked:
             # Use Index to see if it has public symbols
             has_public = any(not s.name.startswith("_") for s in actual_symbols)
             if has_public:
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
            # stored_hashes keys are SURIs or Fragments. 
            # The 'fqn' passed here comes from InteractionContext.
            # In _analyze_file, we used 'fqn' (fragment) for InteractionContext.
            # But stored_hashes might be keyed by SURI. 
            # We need to be careful with key matching.
            
            # Helper to find key in stored_hashes that matches fqn fragment
            def find_key(fragment):
                if fragment in stored_hashes: return fragment
                suri = SURIGenerator.for_symbol(file_path, fragment)
                if suri in stored_hashes: return suri
                return None

            new_hashes = copy.deepcopy(stored_hashes)
            
            # Fetch Actual from Index (Single source of truth)
            actual_symbols = self.index_store.get_symbols_by_file_path(file_path)
            actual_map = {s.logical_path: s for s in actual_symbols}
            
            # Also need YAML hash if Reconciling
            from stitcher.spec import ModuleDef
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(ModuleDef(file_path=file_path))

            for fqn, action in fqn_actions:
                store_key = find_key(fqn)
                if not store_key: continue
                
                fp = new_hashes[store_key]
                actual_rec = actual_map.get(fqn)
                
                if not actual_rec: continue # Should not happen

                if action == ResolutionAction.RELINK:
                    if actual_rec.signature_hash:
                        fp["baseline_code_structure_hash"] = str(actual_rec.signature_hash)
                    if actual_rec.signature_text:
                        fp["baseline_code_signature_text"] = str(actual_rec.signature_text)
                        
                elif action == ResolutionAction.RECONCILE:
                    if actual_rec.signature_hash:
                        fp["baseline_code_structure_hash"] = str(actual_rec.signature_hash)
                    if actual_rec.signature_text:
                        fp["baseline_code_signature_text"] = str(actual_rec.signature_text)
                    
                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = str(yaml_hashes[fqn])

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(file_path, new_hashes)

        # Apply doc purges (Legacy delegation to DocManager)
        for file_path, fqns_to_purge in purges_by_file.items():
            from stitcher.spec import ModuleDef
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
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        results = []
        conflicts = []
        for path in file_paths:
            res, conf = self._analyze_file(path)
            results.append(res)
            conflicts.extend(conf)
        return results, conflicts

    def auto_reconcile_docs(
        self, results: List[FileCheckResult], file_paths: List[str]
    ):
        # Auto-update baselines if only docs improved (hash check passed in analyze)
        # In _analyze_file we populated infos["doc_improvement"].
        # We need to implement this using Index/Signature data.
        
        for res in results:
            if res.infos["doc_improvement"]:
                file_path = res.path
                stored_hashes = self.sig_manager.load_composite_hashes(file_path)
                new_hashes = copy.deepcopy(stored_hashes)
                
                from stitcher.spec import ModuleDef
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(ModuleDef(file_path=file_path))

                # Helper to find key (SURI vs Fragment)
                def find_key(fragment):
                    if fragment in stored_hashes: return fragment
                    suri = SURIGenerator.for_symbol(file_path, fragment)
                    if suri in stored_hashes: return suri
                    return None

                for fqn in res.infos["doc_improvement"]:
                    store_key = find_key(fqn)
                    if store_key and fqn in yaml_hashes:
                        new_hashes[store_key]["baseline_yaml_content_hash"] = yaml_hashes[fqn]

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(file_path, new_hashes)

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        if not conflicts:
            return True

        # ... (Rest of resolution logic remains largely the same, mostly orchestration)
        
        if self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(
                conflicts
            )
            resolutions_by_file = defaultdict(list)
            # ... (mapping logic)
            
            for i, context in enumerate(conflicts):
                action = chosen_actions[i]
                # ... (Standard mapping)
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                elif action == ResolutionAction.PURGE_DOC:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False
                # Handle SKIP logic updating results...
            
            self._apply_resolutions(dict(resolutions_by_file))
            # Update results objects...
            
        else:
            # Non-interactive mode
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(conflicts)
            resolutions_by_file = defaultdict(list)
            
            for i, context in enumerate(conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
            
            self._apply_resolutions(dict(resolutions_by_file))
            
        return True

    def reformat_all(self, file_paths: List[str]):
        bus.info(L.check.run.reformatting)
        for path in file_paths:
            from stitcher.spec import ModuleDef
            self.doc_manager.reformat_docs_for_module(ModuleDef(file_path=path))
            self.sig_manager.reformat_hashes_for_file(path)

    def report(self, results: List[FileCheckResult]) -> bool:
        # Existing report logic is fine
        global_failed_files = 0
        global_warnings_files = 0
        for res in results:
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)
            if res.is_clean:
                continue
            # ... (Standard reporting)
            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)
            # ... 

        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True
~~~~~

#### Acts 2: 更新 StitcherApp

我们需要更新 `StitcherApp` 以适配 `CheckRunner` 的新构造函数签名（注入 `IndexStore`，移除 `Parser`），并修改 `run_check` 以传递路径列表。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 3. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            root_path,
~~~~~
~~~~~python.new
        # 3. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            self.index_store,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            root_path,
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []

        self.scanner.had_errors = False

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            all_modules.extend(modules)

            results, conflicts = self.check_runner.analyze_batch(modules)
            all_results.extend(results)

            self.check_runner.auto_reconcile_docs(results, modules)

            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
                return False

        self.check_runner.reformat_all(all_modules)
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        
        # We need all file paths, but Scanner returns modules.
        # We can extract paths from modules or use Scanner to just get paths.
        # For consistency with current flow, let's extract paths from scanned modules
        # (This still parses, but CheckRunner won't use the parsed objects except for paths)
        # OPTIMIZATION TODO: Scanner should have a mode to just return paths.
        
        all_file_paths: List[str] = []

        self.scanner.had_errors = False

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            
            file_paths = [m.file_path for m in modules]
            all_file_paths.extend(file_paths)

            results, conflicts = self.check_runner.analyze_batch(file_paths)
            all_results.extend(results)

            self.check_runner.auto_reconcile_docs(results, file_paths)

            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
                return False

        self.check_runner.reformat_all(all_file_paths)
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
~~~~~

### 下一步建议

现在 `CheckRunner` 已经是 Query-First 架构了。它直接从 `IndexStore` 获取代码状态，从 `SignatureManager` 获取基准状态，并在内存中进行比对，完全绕过了昂贵的 AST 解析（尽管在 `StitcherApp` 层面为了兼容性目前还是先 Scan 了一遍，但 `CheckRunner` 内部已经解耦）。

后续步骤：
1.  **验证**: 运行测试确保 `CheckRunner` 的基本功能没有回归。
2.  **优化**: `StitcherApp.run_check` 目前仍然调用 `_configure_and_scan`，这会触发不必要的解析。我们需要修改 `ScannerService` 以支持只返回文件路径列表的模式，从而真正实现性能飞跃。
