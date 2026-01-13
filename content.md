简要回答
执行 SURI 全局化架构重构的阶段 3：手术式替换 (The Great Switch)。

## [WIP] feat: 切换至 LockFileManager 并移除 SignatureManager

### 用户需求
1.  **移除旧组件**: 删除 `SignatureManager` 及其相关引用。
2.  **核心重构**: 修改 `StitcherApp` 以注入 `LockFileManager`, `PythonURIGenerator` 和 `Workspace`。
3.  **Runner 适配**: 重写 `InitRunner`, `PumpRunner`, 和 `CheckRunner` (及其辅助类 `Subject`, `Resolver`, `Executor`)，使其逻辑从操作分散的签名文件转变为操作包级 `stitcher.lock` 文件。

### 评论
这是本次重构中工作量最大、风险最高的一步。我们将彻底改变系统读写指纹的方式。原本基于文件路径的隐式查找将被基于 SURI 和 Workspace 坐标的显式查找所取代。这一步完成后，系统的 IO 模式将发生质变。

### 目标
1.  更新 `LockFileManager` 以支持序列化字符串输出（适配事务写入）。
2.  删除 `SignatureManager`。
3.  重构 `StitcherApp`。
4.  重写 `InitRunner`。
5.  重写 `PumpRunner` 及 `PumpExecutor`。
6.  重写 `CheckRunner` 及 `CheckResolver`, `SubjectAdapter`。

### 基本原理
-   **包级聚合**: 所有 Runner 现在必须先通过 `workspace.find_owning_package()` 找到操作对象所属的包根目录，然后加载对应的 Lock 文件。
-   **SURI 查找**: 在 `Check` 阶段，不再通过文件路径拼接 JSON 路径，而是直接通过 `uri_gen` 生成 SURI（或从 Index 获取 SURI），在 Lock 数据中进行 O(1) 查找。
-   **事务性 Lock**: `PumpRunner` 在写入时，将序列化后的 Lock 内容放入 `TransactionManager`，保持操作的事务性。

### 标签
#intent/refactor #flow/ready #priority/critical #comp/application #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/suri-lockfile #task/action/phase-3-switch #task/state/continue

---

### Script

#### Acts 1: 增强 `LockFileManager` 并清理旧组件

首先，我们为 `LockFileManager` 添加 `serialize` 方法，以便 Runner 可以获取内容字符串进行事务写入。然后删除旧的 `SignatureManager`。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/lock_manager.py
~~~~~
~~~~~python.old
        with lock_path.open("w", encoding="utf-8") as f:
            json.dump(lock_content, f, indent=2, sort_keys=True)
            f.write("\n")  # Ensure trailing newline
~~~~~
~~~~~python.new
        with lock_path.open("w", encoding="utf-8") as f:
            json.dump(lock_content, f, indent=2, sort_keys=True)
            f.write("\n")  # Ensure trailing newline

    def serialize(self, data: Dict[str, Fingerprint]) -> str:
        """
        Serializes the fingerprint data to a formatted JSON string representing
        the stitcher.lock content.
        """
        serializable_data = {
            suri: fp.to_dict() for suri, fp in data.items()
        }

        lock_content = {
            "version": "1.0",
            "fingerprints": serializable_data,
        }
        
        return json.dumps(lock_content, indent=2, sort_keys=True) + "\n"
~~~~~

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python.old
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .scanner import ScannerService
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "ScannerService",
    "DocstringMerger",
]
~~~~~
~~~~~python.new
from .doc_manager import DocumentManager
from .scanner import ScannerService
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "ScannerService",
    "DocstringMerger",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/managers.py
~~~~~
~~~~~python.old
    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str: ...


class SignatureManagerProtocol(Protocol):
    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]: ...

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None: ...

    def reformat_hashes_for_file(self, file_path: str) -> bool: ...

    # Used by PumpRunner for centralized serialization
    def serialize_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> str: ...

    def get_signature_path(self, file_path: str) -> Path: ...
~~~~~
~~~~~python.new
    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str: ...
~~~~~

#### Acts 2: 重构 `StitcherApp` (`stitcher-application`)

更新核心应用类，注入新依赖。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.stubgen import StubgenService
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    DocstringMerger,
)
from stitcher.common.services import Differ
from stitcher.spec.interaction import InteractionHandler
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.executor import PumpExecutor
from stitcher.analysis.engines import create_pump_engine
from stitcher.common.transaction import TransactionManager
from typing import Callable
from stitcher.analysis.schema import FileCheckResult
from .types import PumpResult, CoverageResult
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python import PythonAdapter
from stitcher.workspace import Workspace
from stitcher.lang.python.docstring import (
    get_docstring_codec,
    get_docstring_serializer,
)
from stitcher.spec.interaction import InteractionContext


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        self.fingerprint_strategy = fingerprint_strategy
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 2. Indexing Subsystem (Must be initialized before runners that use it)
~~~~~
~~~~~python.new
from stitcher.stubgen import StubgenService
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    ScannerService,
    DocstringMerger,
)
from stitcher.common.services import Differ
from stitcher.spec.interaction import InteractionHandler
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.executor import PumpExecutor
from stitcher.analysis.engines import create_pump_engine
from stitcher.common.transaction import TransactionManager
from typing import Callable
from stitcher.analysis.schema import FileCheckResult
from .types import PumpResult, CoverageResult
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python import PythonAdapter
from stitcher.workspace import Workspace
from stitcher.lang.python.docstring import (
    get_docstring_codec,
    get_docstring_serializer,
)
from stitcher.spec.interaction import InteractionContext
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python import PythonURIGenerator


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        self.fingerprint_strategy = fingerprint_strategy
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.lock_manager = LockFileManager()
        self.uri_generator = PythonURIGenerator()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 2. Indexing Subsystem (Must be initialized before runners that use it)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 3. Runners (Command Handlers)
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
            differ=self.differ,
            resolver=check_resolver,
            reporter=check_reporter,
            root_path=self.root_path,
        )

        pump_engine = create_pump_engine(differ=self.differ)
        pump_executor = PumpExecutor(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.merger,
            self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            pump_engine=pump_engine,
            executor=pump_executor,
            interaction_handler=interaction_handler,
            # Pass dependencies needed for subject creation
            doc_manager=self.doc_manager,
            sig_manager=self.sig_manager,
            fingerprint_strategy=self.fingerprint_strategy,
        )

        self.init_runner = InitRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            fingerprint_strategy=self.fingerprint_strategy,
        )
~~~~~
~~~~~python.new
        # 3. Runners (Command Handlers)
        check_resolver = CheckResolver(
            root_path,
            self.workspace,
            parser,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            interaction_handler,
            self.fingerprint_strategy,
        )
        check_reporter = CheckReporter()
        self.check_runner = CheckRunner(
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            self.fingerprint_strategy,
            self.index_store,
            self.workspace,
            differ=self.differ,
            resolver=check_resolver,
            reporter=check_reporter,
            root_path=self.root_path,
        )

        pump_engine = create_pump_engine(differ=self.differ)
        pump_executor = PumpExecutor(
            root_path,
            self.workspace,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            transformer,
            self.merger,
            self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            pump_engine=pump_engine,
            executor=pump_executor,
            interaction_handler=interaction_handler,
            # Pass dependencies needed for subject creation
            doc_manager=self.doc_manager,
            lock_manager=self.lock_manager,
            uri_generator=self.uri_generator,
            workspace=self.workspace,
            fingerprint_strategy=self.fingerprint_strategy,
        )

        self.init_runner = InitRunner(
            root_path,
            self.workspace,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            fingerprint_strategy=self.fingerprint_strategy,
        )
~~~~~

#### Acts 3: 重写 `InitRunner`

将 `InitRunner` 转换为包级 Lock 操作。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    Fingerprint,
    ModuleDef,
    FingerprintStrategyProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.workspace import Workspace


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.fingerprint_strategy = fingerprint_strategy

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            # Include the class itself
            fingerprints[cls.name] = self.fingerprint_strategy.compute(cls)
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def run_batch(self, modules: List[ModuleDef]) -> List[Path]:
        created_files: List[Path] = []
        
        # 1. Group modules by their owning package (lock file boundary)
        # This reduces I/O by loading each lock file only once per batch.
        grouped_modules: Dict[Path, List[ModuleDef]] = defaultdict(list)
        for module in modules:
            if not module.file_path:
                continue
            abs_path = self.root_path / module.file_path
            pkg_root = self.workspace.find_owning_package(abs_path)
            grouped_modules[pkg_root].append(module)

        # 2. Process each group
        for pkg_root, pkg_modules in grouped_modules.items():
            # Load existing lock or create empty
            lock_data = self.lock_manager.load(pkg_root)
            lock_updated = False

            for module in pkg_modules:
                output_path = self.doc_manager.save_docs_for_module(module)
                
                # Compute logical/relative paths for SURI generation
                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

                computed_fingerprints = self._compute_fingerprints(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

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

                    # Generate global SURI
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    lock_data[suri] = fp
                    lock_updated = True

                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    created_files.append(output_path)
            
            # Save lock file for the package
            if lock_updated:
                self.lock_manager.save(pkg_root, lock_data)

        return created_files
~~~~~

#### Acts 4: 重写 `PumpExecutor` 和 `PumpRunner`

适配 `PumpRunner` 以支持包级 Lock 事务。

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
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.app.types import PumpResult
from stitcher.common.transaction import TransactionManager
from stitcher.workspace import Workspace


class PumpExecutor:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        transformer: LanguageTransformerProtocol,
        merger: DocstringMergerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
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

        # Group modules by package for Lock file batching
        grouped_modules: Dict[Path, List[ModuleDef]] = defaultdict(list)
        for module in modules:
            if not module.file_path:
                continue
            abs_path = self.root_path / module.file_path
            pkg_root = self.workspace.find_owning_package(abs_path)
            grouped_modules[pkg_root].append(module)

        for pkg_root, pkg_modules in grouped_modules.items():
            # Load Lock Data once per package
            current_lock_data = self.lock_manager.load(pkg_root)
            new_lock_data = copy.deepcopy(current_lock_data)
            lock_updated = False

            for module in pkg_modules:
                source_docs = self.doc_manager.flatten_module_docs(module)
                file_plan = self._generate_execution_plan(
                    module, decisions, strip, source_docs
                )
                current_yaml_docs = self.doc_manager.load_docs_for_module(module)
                current_fingerprints = self._compute_fingerprints(module)

                new_yaml_docs = current_yaml_docs.copy()
                
                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

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

                    # Generate SURI for lock lookup
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    fp = new_lock_data.get(suri) or Fingerprint()
                    
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

                    if plan.update_doc_fingerprint and fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            fp["baseline_yaml_content_hash"] = (
                                self.doc_manager.compute_ir_hash(ir_to_save)
                            )
                            fqn_was_updated = True

                    if fqn_was_updated:
                        new_lock_data[suri] = fp
                        lock_updated = True

                    if (
                        fqn in decisions
                        and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                    ):
                        reconciled_keys_in_file.append(fqn)
                    if plan.strip_source_docstring:
                        strip_jobs[module.file_path].append(fqn)
                    if fqn in source_docs and not plan.strip_source_docstring:
                        file_has_redundancy = True

                if not file_has_errors:
                    if file_had_updates:
                        raw_data = self.doc_manager.load_raw_data(module.file_path)
                        for fqn, ir in new_yaml_docs.items():
                            raw_data[fqn] = self.doc_manager.serialize_ir(ir)

                        doc_path = (self.root_path / module.file_path).with_suffix(
                            ".stitcher.yaml"
                        )
                        yaml_content = self.doc_manager.dump_raw_data_to_string(raw_data)
                        tm.add_write(
                            str(doc_path.relative_to(self.root_path)), yaml_content
                        )

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

            if lock_updated:
                # To maintain transactionality, we write to the lock file via TM
                # using the serialize() method we added to LockFileManager
                lock_content = self.lock_manager.serialize(new_lock_data)
                lock_path = pkg_root / self.lock_manager.LOCK_FILE_NAME
                tm.add_write(str(lock_path.relative_to(self.root_path)), lock_content)

        if strip_jobs:
            self._execute_strip_jobs(strip_jobs, tm)

        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)

        has_activity = (total_updated_keys > 0) or strip_jobs
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)
        return PumpResult(success=True, redundant_files=redundant_files_list)

    def _execute_strip_jobs(
        self, strip_jobs: Dict[str, List[str]], tm: TransactionManager
    ):
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
                    relative_path = source_path.relative_to(self.root_path)
                    tm.add_write(str(relative_path), stripped_content)
                    bus.success(L.strip.file.success, path=relative_path)
                    total_stripped_files += 1
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if total_stripped_files > 0:
            bus.success(L.strip.run.complete, count=total_stripped_files)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump/runner.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    FingerprintStrategyProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionHandler
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager
from stitcher.analysis.engines import PumpEngine
from .protocols import PumpExecutorProtocol
from ..check.subject import ASTCheckSubjectAdapter


class PumpRunner:
    def __init__(
        self,
        pump_engine: PumpEngine,
        executor: PumpExecutorProtocol,
        interaction_handler: InteractionHandler | None,
        # Dependencies required for subject creation
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.pump_engine = pump_engine
        self.executor = executor
        self.interaction_handler = interaction_handler
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy

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
        all_conflicts = []
        # The runner is responsible for adapting ModuleDefs to AnalysisSubjects
        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                tm.root_path,
            )
            conflicts = self.pump_engine.analyze(subject)
            all_conflicts.extend(conflicts)
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    FingerprintStrategyProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.spec.interaction import InteractionHandler
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager
from stitcher.analysis.engines import PumpEngine
from .protocols import PumpExecutorProtocol
from ..check.subject import ASTCheckSubjectAdapter
from stitcher.workspace import Workspace


class PumpRunner:
    def __init__(
        self,
        pump_engine: PumpEngine,
        executor: PumpExecutorProtocol,
        interaction_handler: InteractionHandler | None,
        # Dependencies required for subject creation
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        workspace: Workspace,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.pump_engine = pump_engine
        self.executor = executor
        self.interaction_handler = interaction_handler
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.workspace = workspace
        self.fingerprint_strategy = fingerprint_strategy

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
        all_conflicts = []
        # The runner is responsible for adapting ModuleDefs to AnalysisSubjects
        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.lock_manager,
                self.uri_generator,
                self.workspace,
                self.fingerprint_strategy,
                tm.root_path,
            )
            conflicts = self.pump_engine.analyze(subject)
            all_conflicts.extend(conflicts)
~~~~~

### 下一步建议
我们已经完成了核心 Runner (`Init`, `Pump`) 的迁移。
接下来的重点是 **Check 子系统** 的重写。这是一个较大的任务，因为它涉及到 `SubjectAdapter` 的逻辑变更（从文件哈希到 SURI 查找）以及 `Resolver` 的冲突解决逻辑。

建议将 Check 子系统的迁移拆分为以下步骤：
1.  重写 `stitcher-application/src/stitcher/app/runners/check/subject.py`。
2.  重写 `stitcher-application/src/stitcher/app/runners/check/resolver.py`。
3.  重写 `stitcher-application/src/stitcher/app/runners/check/runner.py`。
