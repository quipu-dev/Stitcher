简要回答
上次的修复因为 `patch_file` 操作导致了 `pump.py` 结构严重损坏（不同阶段的代码块错位），引发了 `UnboundLocalError`。同时，`test_pump_state_integrity.py` 的修复并未正确应用到有问题的代码块。

本次计划将采取 **Write File** 策略重写 `pump.py` 以彻底修复其结构和逻辑错误，并重新正确 Patch 测试文件。

## [WIP] fix(pump): 重构损坏的 PumpRunner 并修复测试数据

### 错误分析
1.  **`pump.py` 结构损坏**: `pump.py` 在之前的修改中，Analysis 阶段代码被错误替换为了 Stripping 阶段代码，导致 `strip_jobs` 变量在使用前未定义 (`UnboundLocalError`)。且 Phase 1 逻辑完全丢失。
2.  **测试数据未修复**: `test_pump_state_integrity.py` 中用于生成测试文件的代码使用了错误的转义字符 (`\\n`)，导致生成的 Python 文件非法。上一次修复尝试定位了错误的上下文（定位到了另一个测试函数），导致修复失败。

### 用户需求
恢复 `pump` 命令的正常功能，消除 `UnboundLocalError`，并使相关集成测试通过。

### 评论
使用 `write_file` 重写 `pump.py` 是最安全、最直接的恢复手段，能确保代码结构的完整性和顺序的正确性。

### 目标
1.  **重写 `pump.py`**: 恢复正常的执行流：Analysis (force/reconcile=False) -> Decision -> Execution -> Stripping -> Signature Refresh -> Reporting。
2.  **修复测试用例**: 修正 `test_pump_state_integrity.py` 中 `test_pump_is_atomic_per_file` 函数内的字符串转义问题。

### 基本原理
按照标准的 Quipu 执行模型，`pump` 流程应当是线性的。我们需要确保：
1.  **Analysis**: 先做一次"预演"，不带任何副作用地检测冲突。
2.  **Execution**: 应用变更，并收集需要 Strip 的文件列表。
3.  **Stripping**: 处理 Strip 列表，并发出相应的 `strip.file.success` 消息。
4.  **Reporting**: 综合统计各类操作结果，给出最终报告。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests
#concept/state #scope/core
#ai/instruct
#task/domain/testing #task/object/pump-runner #task/action/recovery #task/state/continue

---

### Script

#### Acts 1: 重构 `pump.py`

我们将完整重写 `packages/stitcher-application/src/stitcher/app/runners/pump.py`，确保各阶段逻辑顺序正确且完整。

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
        # Scan all files and identify conflicts WITHOUT applying changes
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            if not modules: continue
            all_modules.extend(modules)

            for module in modules:
                # IMPORTANT: dry_run=True, force=False, reconcile=False
                # We want to see the RAW conflicts first so we can decide on them.
                res = self.doc_manager.hydrate_module(module, force=False, reconcile=False, dry_run=True)
                if not res["success"]:
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)
                    for key in res["conflicts"]:
                        doc_diff = self._generate_diff(yaml_docs.get(key, ""), source_docs.get(key, ""), "yaml", "code")
                        all_conflicts.append(InteractionContext(module.file_path, key, ConflictType.DOC_CONTENT_CONFLICT, doc_diff=doc_diff))

        # --- Phase 2: Decision ---
        # Solve conflicts via InteractionHandler (or NoOp defaults)
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
        # Apply decisions, write files, and record stats
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
                        # If we have a new key, we should try to grab its code hash too if available
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
            total_stripped_files = 0
            for file_path, whitelist in strip_jobs.items():
                source_path = self.root_path / file_path
                if not whitelist: continue
                try:
                    original_content = source_path.read_text("utf-8")
                    stripped_content = self.transformer.strip(original_content, whitelist=whitelist)
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, "utf-8")
                        bus.success(L.strip.file.success, path=source_path.relative_to(self.root_path))
                        total_stripped_files += 1
                except Exception as e:
                    bus.error(L.error.generic, error=e)
            
            if total_stripped_files > 0:
                bus.success(L.strip.run.complete, count=total_stripped_files)
        
        # Phase 6: Ensure Signatures Integrity
        # Refresh all signatures to latest format, even if no docs changed.
        for module in all_modules:
            self.sig_manager.reformat_hashes_for_module(module)
        
        # Final Reporting
        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)
        
        has_activity = (total_updated_keys > 0) or (total_reconciled_keys > 0) or strip_jobs
        
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)

        return PumpResult(success=True, redundant_files=[])
~~~~~

#### Acts 2: 修复测试数据

精确修复 `test_pump_state_integrity.py` 中的 `test_pump_is_atomic_per_file` 方法。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_pump_state_integrity.py
~~~~~
~~~~~python
    # 2. Act: Modify the code to create a mixed state
    (project_root / "src/main.py").write_text(
        'def func_clean():\\n    """New clean doc."""\\n'
        'def func_conflict():\\n    """New conflicting doc."""'
    )
~~~~~
~~~~~python
    # 2. Act: Modify the code to create a mixed state
    (project_root / "src/main.py").write_text(
        'def func_clean():\n    """New clean doc."""\n'
        'def func_conflict():\n    """New conflicting doc."""',
        encoding="utf-8"
    )
~~~~~
