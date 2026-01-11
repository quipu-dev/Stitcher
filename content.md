好的，我们来执行这个关键的解耦步骤。

这个重构的核心思想是将 `SignatureManager` 的职责单一化，让它只负责 **读/写** 基线签名文件 (`.json`)，而不再关心签名的 **计算** 过程。计算的职责将暂时转移到需要它的各个 Runner 中，为下一步 `CheckRunner` 完全依赖索引数据铺平道路。

## [WIP] refactor(app): 将 SignatureManager 解耦为纯 I/O 服务

### 用户需求
重构 `SignatureManager`，使其不再依赖重量级的 `ModuleDef` AST 对象，而是基于简单的 `file_path` 进行操作。同时，移除其内部的指纹计算逻辑。

### 评论
这是一个经典的“关注点分离”重构。`SignatureManager` 的新角色是 `.stitcher/signatures` 目录的“仓库管理员”，只负责存取，不负责生产。这使得它的 API 变得非常清晰和稳定。指纹计算的逻辑（暂时由各个 Runner 承担）是易变的，并将在后续步骤中被索引查询所取代，因此将它移出 `SignatureManager` 是一个非常正确的方向。

### 目标
1.  **重构 `SignatureManager`**:
    *   移除 `fingerprint_strategy` 依赖和 `compute_fingerprints` 方法。
    *   将其所有公共方法的输入从 `ModuleDef` 对象改为 `file_path: str` 字符串。
2.  **调整依赖注入**:
    *   在 `StitcherApp` 中，更新 `SignatureManager` 的实例化方式。
    *   将 `FingerprintStrategyProtocol` 实例直接注入到需要它的 `CheckRunner`, `InitRunner`, 和 `PumpRunner` 中。
3.  **适配消费者 (Runners)**:
    *   更新 `CheckRunner`, `InitRunner`, 和 `PumpRunner` 以适应 `SignatureManager` 的新 API。
    *   将原有的指纹计算逻辑从 `SignatureManager` 迁移至这三个 Runner 内部。

### 基本原理
通过将 `SignatureManager` 改造为一个纯粹的数据访问层（Data Access Layer），我们显著降低了它的复杂性和耦合度。虽然指纹计算的逻辑暂时在三个 Runner 中重复，但这是一种有意的、临时的策略。这种“战术性重复”是为了保证本次重构的原子性，并且这些重复代码将在下一个重构步骤（`CheckRunner` 切换到索引查询）中被自然地消除。

### 标签
#intent/refactor #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/app #task/object/stitcher-app #task/action/integrate-index #task/state/continue

---

### Script

#### Acts 1: 重构 SignatureManager 为纯粹的 I/O 服务

我们将完全重写 `signature_manager.py`，移除所有计算逻辑和对 `ModuleDef` 的依赖。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Dict

from stitcher.spec import (
    Fingerprint,
    InvalidFingerprintKeyError,
)
from stitcher.common.services import AssetPathResolver


class SignatureManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)

    def _get_sig_path(self, file_path: str) -> Path:
        return self.resolver.get_signature_path(file_path)

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None:
        if not hashes:
            sig_path = self._get_sig_path(file_path)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(file_path)
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        serialized_data = {fqn: fp.to_dict() for fqn, fp in hashes.items()}

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(serialized_data, f, indent=2, sort_keys=True)

    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]:
        sig_path = self._get_sig_path(file_path)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                result = {}
                for fqn, fp_data in data.items():
                    result[fqn] = Fingerprint.from_dict(fp_data)
                return result
        except (json.JSONDecodeError, OSError, InvalidFingerprintKeyError):
            return {}

    def reformat_hashes_for_file(self, file_path: str) -> bool:
        sig_path = self._get_sig_path(file_path)
        if not sig_path.exists():
            return False

        hashes = self.load_composite_hashes(file_path)
        if not hashes:
            return False

        self.save_composite_hashes(file_path, hashes)
        return True
~~~~~

#### Acts 2: 更新 StitcherApp 核心以注入新依赖

现在 `SignatureManager` 不需要 `fingerprint_strategy` 了，但 Runners 需要。我们将修改 `StitcherApp` 来处理这个依赖关系的变化。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

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
        self.init_runner = InitRunner(root_path, self.doc_manager, self.sig_manager)
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
~~~~~
~~~~~python.new
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

        # 2. Runners (Command Handlers)
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
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
        )
        self.init_runner = InitRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            fingerprint_strategy=self.fingerprint_strategy,
        )
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
~~~~~

#### Acts 3: 适配 CheckRunner、InitRunner 和 PumpRunner

最后，我们将指纹计算逻辑移入 Runners 并更新它们对 `SignatureManager` 的调用。

##### `check.py`

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
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
    Differ,
)
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
        self.root_path = root_path
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
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
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        for file_path, fqn_actions in sig_updates_by_file.items():
            stored_hashes = self.sig_manager.load_composite_hashes(file_path)
            new_hashes = copy.deepcopy(stored_hashes)

            full_module_def = self.parser.parse(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            computed_fingerprints = self._compute_fingerprints(full_module_def)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

        # Apply doc purges
        for file_path, fqns_to_purge in purges_by_file.items():
            module_def = ModuleDef(file_path=file_path)
            docs = self.doc_manager.load_docs_for_module(module_def)
            original_len = len(docs)
~~~~~
~~~~~python.new
            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(file_path, new_hashes)

        # Apply doc purges
        for file_path, fqns_to_purge in purges_by_file.items():
            module_def = ModuleDef(file_path=file_path)
            docs = self.doc_manager.load_docs_for_module(module_def)
            original_len = len(docs)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ):
        for res in results:
            if res.infos["doc_improvement"]:
                module_def = next((m for m in modules if m.file_path == res.path), None)
                if not module_def:
                    continue

                stored_hashes = self.sig_manager.load_composite_hashes(module_def)
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module_def
                )
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)

    def resolve_conflicts(
~~~~~
~~~~~python.new
                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(
                        module_def.file_path, new_hashes
                    )

    def resolve_conflicts(
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check.py
~~~~~
~~~~~python.old
    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_module(module)
~~~~~
~~~~~python.new
    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_file(module.file_path)
~~~~~

##### `init.py`

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
from stitcher.spec import Fingerprint, ModuleDef
from stitcher.app.services import DocumentManager, SignatureManager
~~~~~
~~~~~python.new
from typing import Dict
from stitcher.spec import Fingerprint, ModuleDef, FingerprintStrategyProtocol
from stitcher.app.services import DocumentManager, SignatureManager
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
class InitRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
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

    def run_batch(self, modules: List[ModuleDef]) -> List[Path]:
        created_files: List[Path] = []
        for module in modules:
            output_path = self.doc_manager.save_docs_for_module(module)

            # Use the new unified compute method
            computed_fingerprints = self._compute_fingerprints(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]

                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
~~~~~
~~~~~python.new
                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]

                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module.file_path, combined)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
~~~~~

##### `pump.py`

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
)
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.differ = differ
        self.merger = merger
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
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
        for module in modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)

            source_docs = self.doc_manager.flatten_module_docs(module)
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module)
            current_fingerprints = self.sig_manager.compute_fingerprints(module)
~~~~~
~~~~~python.new
        for module in modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)

            source_docs = self.doc_manager.flatten_module_docs(module)
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module.file_path)
            current_fingerprints = self._compute_fingerprints(module)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if signatures_need_save:
                    sig_path = self.sig_manager.get_sig_path(module)
                    if not new_hashes:
                        if sig_path.exists():
                            tm.add_delete_file(
                                str(sig_path.relative_to(self.root_path))
                            )
                    else:
                        serialized_data = {
                            fqn: fp.to_dict() for fqn, fp in new_hashes.items()
                        }
                        sig_content = json.dumps(
                            serialized_data, indent=2, sort_keys=True
                        )
                        tm.add_write(
                            str(sig_path.relative_to(self.root_path)), sig_content
                        )
~~~~~
~~~~~python.new
                if signatures_need_save:
                    if not new_hashes:
                        sig_path = self.sig_manager._get_sig_path(module.file_path)
                        if sig_path.exists():
                            tm.add_delete_file(
                                str(sig_path.relative_to(self.root_path))
                            )
                    else:
                        self.sig_manager.save_composite_hashes(
                            module.file_path, new_hashes
                        )
                        # The save logic is complex, let's defer to the manager.
                        # We need to write the content via the TM.
                        serialized_data = {
                            fqn: fp.to_dict() for fqn, fp in new_hashes.items()
                        }
                        sig_content = json.dumps(
                            serialized_data, indent=2, sort_keys=True
                        )
                        sig_path = self.sig_manager._get_sig_path(module.file_path)
                        tm.add_write(
                            str(sig_path.relative_to(self.root_path)), sig_content
                        )
~~~~~

### 下一步建议
我们已经成功地将 `SignatureManager` 瘦身为一个纯粹的存储访问层。现在，`CheckRunner` 仍然在进行昂贵的实时文件解析和哈希计算。

下一步是完成我们的核心目标：**将 `CheckRunner` 改造为 "Query-First" 模式**。它将：
1.  从 `stitcher-index` 数据库中查询“当前状态”的指纹。
2.  从（已重构的）`SignatureManager` 中加载“基线状态”的指纹。
3.  在内存中对这两个字典进行比对，从而完全消除实时文件 I/O 和 AST 解析的开销。
