## [WIP] refactor: 改造 StitcherApp 支持协议级依赖注入

### 用户需求
修改 `StitcherApp` 及其内部服务（`SignatureManager`, `DocumentManager`），使其不再硬编码依赖具体的实现类，而是通过构造函数接收符合 `stitcher-spec` 协议的接口实例。

### 评论
这是架构解耦的“手术”阶段。我们将打破 `stitcher-application` 对 `stitcher-scanner` 和 `stitcher-io` 的直接依赖链。`StitcherApp` 将变成纯粹的业务逻辑编排器，完全不知道它正在处理的是 Python 还是其他语言。

### 目标
1.  重构 `SignatureManager`：注入 `FingerprintStrategyProtocol`，替换掉内部对 `entity.compute_fingerprint()` 的直接调用。
2.  重构 `DocumentManager`：注入 `DocumentAdapterProtocol`（这部分已部分实现，需确认），并确保它与语言无关。
3.  重构 `StitcherApp`：
    *   移除 `stitcher.scanner` 和 `stitcher.io` 的直接导入。
    *   在 `__init__` 中注入 `parser`, `transformer`, `stub_generator`。
    *   更新所有业务方法（`_scan_files`, `run_pump` 等）使用注入的协议实例。

### 基本原理
通过依赖注入，我们将控制反转。`StitcherApp` 不再负责“创建”工具，只负责“使用”工具。这使得我们在单元测试中可以轻松传入 Mock 对象，而不需要复杂的文件系统 Fixture。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/architecture #task/object/stitcher-app #task/action/dependency-injection #task/state/continue

---

### Script

#### Acts 1: 重构 SignatureManager 以使用策略
`SignatureManager` 需要知道如何计算指纹，但它不再应该调用实体上的硬编码方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python.old
from typing import Dict

from stitcher.spec import ModuleDef, Fingerprint, InvalidFingerprintKeyError


class SignatureManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.sig_root = root_path / ".stitcher" / "signatures"

    def _get_sig_path(self, module: ModuleDef) -> Path:
        rel_path = Path(module.file_path)
        return self.sig_root / rel_path.with_suffix(".json")

    def compute_code_structure_hashes(self, module: ModuleDef) -> Dict[str, str]:
        hashes = {}
        for func in module.functions:
            hashes[func.name] = func.compute_fingerprint()
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                hashes[fqn] = method.compute_fingerprint()
        return hashes

    def extract_signature_texts(self, module: ModuleDef) -> Dict[str, str]:
        texts = {}
        for func in module.functions:
            texts[func.name] = func.get_signature_string()
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                texts[fqn] = method.get_signature_string()
        return texts

    def save_composite_hashes(
        self, module: ModuleDef, hashes: Dict[str, Fingerprint]
~~~~~
~~~~~python.new
from typing import Dict

from stitcher.spec import ModuleDef, Fingerprint, InvalidFingerprintKeyError, FingerprintStrategyProtocol


class SignatureManager:
    def __init__(self, root_path: Path, fingerprint_strategy: FingerprintStrategyProtocol):
        self.root_path = root_path
        self.sig_root = root_path / ".stitcher" / "signatures"
        self.fingerprint_strategy = fingerprint_strategy

    def _get_sig_path(self, module: ModuleDef) -> Path:
        rel_path = Path(module.file_path)
        return self.sig_root / rel_path.with_suffix(".json")

    def compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        """
        Computes the complete fingerprints for all entities in the module
        using the injected strategy.
        """
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def save_composite_hashes(
        self, module: ModuleDef, hashes: Dict[str, Fingerprint]
~~~~~

#### Acts 2: 更新 DocumentManager 导入
`DocumentManager` 已经有了 adapter 的概念，只需确保其协议导入正确即可。目前看来 `DocumentAdapter` 已经在 `stitcher.io` 中定义了，暂时不需要大改，但在后续它应该迁移到 `stitcher-spec`。鉴于本次聚焦于语言核心解耦，暂时保留 IO 依赖，仅确保其与主逻辑兼容。

#### Acts 3: 重构 StitcherApp 注入依赖
这是重头戏。我们需要注入 Parser, Transformer, StubGenerator, FingerprintStrategy。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.scanner import (
    parse_source_code,
    parse_plugin_entry,
    InspectionError,
    strip_docstrings,
    inject_docstrings,
)
from stitcher.io import StubGenerator

from stitcher.spec import ModuleDef, ConflictType, ResolutionAction, Fingerprint
from stitcher.common import bus
from needle.pointer import L
~~~~~
~~~~~python.new
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.scanner import (
    parse_plugin_entry,
    InspectionError,
)

from stitcher.spec import (
    ModuleDef, 
    ConflictType, 
    ResolutionAction, 
    Fingerprint,
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.common import bus
from needle.pointer import L
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)
        self.stub_pkg_manager = StubPackageManager()
        self.interaction_handler = interaction_handler

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules
~~~~~
~~~~~python.new
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
        self.root_path = root_path
        self.parser = parser
        self.transformer = transformer
        self.generator = stub_generator
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.interaction_handler = interaction_handler

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = self.parser.parse(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules
~~~~~

#### Acts 4: 更新 run_init 使用 FingerprintStrategy
因为 `SignatureManager` 的 API 变了，我们需要更新 `run_init`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)
                code_hashes = self.sig_manager.compute_code_structure_hashes(module)
                code_texts = self.sig_manager.extract_signature_texts(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

                combined: Dict[str, Fingerprint] = {}
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                for fqn in all_fqns:
                    fp = Fingerprint()
                    if fqn in code_hashes:
                        fp["baseline_code_structure_hash"] = code_hashes[fqn]
                    if fqn in code_texts:
                        fp["baseline_code_signature_text"] = code_texts[fqn]
                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                    combined[fqn] = fp

                self.sig_manager.save_composite_hashes(module, combined)
                if output_path and output_path.name:
~~~~~
~~~~~python.new
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
                    # This mapping is critical: what we just computed is now the baseline
                    if "current_code_structure_hash" in fp:
                        fp["baseline_code_structure_hash"] = fp["current_code_structure_hash"]
                        del fp["current_code_structure_hash"]
                    
                    if "current_code_signature_text" in fp:
                        fp["baseline_code_signature_text"] = fp["current_code_signature_text"]
                        del fp["current_code_signature_text"]

                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                    
                    combined[fqn] = fp

                self.sig_manager.save_composite_hashes(module, combined)
                if output_path and output_path.name:
~~~~~

#### Acts 5: 更新 _analyze_file 逻辑
同样需要更新 `_analyze_file`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )
        current_code_map = self.sig_manager.compute_code_structure_hashes(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        current_sig_texts = self.sig_manager.extract_signature_texts(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(current_code_map.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            code_hash = current_code_map.get(fqn)
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
~~~~~
~~~~~python.new
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )
        
        computed_fingerprints = self.sig_manager.compute_fingerprints(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(computed_fingerprints.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            computed_fp = computed_fingerprints.get(fqn, Fingerprint())
            
            # Extract standard keys using O(1) access from Fingerprint object
            code_hash = computed_fp.get("current_code_structure_hash")
            current_sig_text = computed_fp.get("current_code_signature_text")
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                # Signature changed (either Drift or Co-evolution)
                sig_diff = None
                if baseline_sig_text and fqn in current_sig_texts:
                    sig_diff = self._generate_diff(
                        baseline_sig_text,
                        current_sig_texts[fqn],
                        "baseline",
                        "current",
                    )
                elif fqn in current_sig_texts:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_texts[fqn]}"

                conflict_type = (
                    ConflictType.SIGNATURE_DRIFT
~~~~~
~~~~~python.new
            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                # Signature changed (either Drift or Co-evolution)
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
~~~~~

#### Acts 6: 更新 _apply_resolutions
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            # We need the current hashes again to apply changes
            full_module_def = parse_source_code(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            current_code_map = self.sig_manager.compute_code_structure_hashes(
                full_module_def
            )
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    if action == ResolutionAction.RELINK:
                        if fqn in current_code_map:
                            fp["baseline_code_structure_hash"] = current_code_map[fqn]
                    elif action == ResolutionAction.RECONCILE:
                        if fqn in current_code_map:
                            fp["baseline_code_structure_hash"] = current_code_map[fqn]
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]
~~~~~
~~~~~python.new
            # We need the current hashes again to apply changes
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
                            fp["baseline_code_structure_hash"] = current_code_hash
                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = current_code_hash
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]
~~~~~

#### Acts 7: 更新 run_pump
你需要更新 `run_pump` 使用 `transformer`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            else:
                # If we are NOT stripping now, we check if there are docs in code
                # that are redundant (meaning they are safe to strip later)
                # We check this by seeing if the file content would change if stripped
                source_path = self.root_path / module.file_path
                try:
                    original = source_path.read_text(encoding="utf-8")
                    stripped = strip_docstrings(original)
                    if original != stripped:
                        redundant_files.append(source_path)
                except Exception:
                    pass

        # 4. Strip Phase (Immediate)
        if files_to_strip_now:
            stripped_count = 0
            for module in files_to_strip_now:
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    stripped_content = strip_docstrings(original_content)
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, encoding="utf-8")
                        stripped_count += 1
                        relative_path = source_path.relative_to(self.root_path)
~~~~~
~~~~~python.new
            else:
                # If we are NOT stripping now, we check if there are docs in code
                # that are redundant (meaning they are safe to strip later)
                # We check this by seeing if the file content would change if stripped
                source_path = self.root_path / module.file_path
                try:
                    original = source_path.read_text(encoding="utf-8")
                    stripped = self.transformer.strip(original)
                    if original != stripped:
                        redundant_files.append(source_path)
                except Exception:
                    pass

        # 4. Strip Phase (Immediate)
        if files_to_strip_now:
            stripped_count = 0
            for module in files_to_strip_now:
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    stripped_content = self.transformer.strip(original_content)
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, encoding="utf-8")
                        stripped_count += 1
                        relative_path = source_path.relative_to(self.root_path)
~~~~~

#### Acts 8: 更新 run_pump 中的 SignatureManager 调用
在 `run_pump` 中也有 `compute_code_structure_hashes` 的调用，需要更新。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            # Update signatures if successful
            code_hashes = self.sig_manager.compute_code_structure_hashes(module)
            code_texts = self.sig_manager.extract_signature_texts(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())

            combined: Dict[str, Fingerprint] = {}
            for fqn in all_fqns:
                fp = Fingerprint()
                if fqn in code_hashes:
                    fp["baseline_code_structure_hash"] = code_hashes[fqn]
                if fqn in code_texts:
                    fp["baseline_code_signature_text"] = code_texts[fqn]
                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)
~~~~~
~~~~~python.new
            # Update signatures if successful
            computed_fingerprints = self.sig_manager.compute_fingerprints(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

            combined: Dict[str, Fingerprint] = {}
            for fqn in all_fqns:
                fp = computed_fingerprints.get(fqn, Fingerprint())
                
                # Convert 'current' to 'baseline'
                if "current_code_structure_hash" in fp:
                    fp["baseline_code_structure_hash"] = fp["current_code_structure_hash"]
                    del fp["current_code_structure_hash"]
                
                if "current_code_signature_text" in fp:
                    fp["baseline_code_signature_text"] = fp["current_code_signature_text"]
                    del fp["current_code_signature_text"]

                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)
~~~~~

#### Acts 9: 更新 run_strip 和 run_inject
最后更新 `run_strip` 和 `run_inject`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        for file_path in files_to_process:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = strip_docstrings(original_content)
                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    all_modified_files.append(file_path)
~~~~~
~~~~~python.new
        for file_path in files_to_process:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = self.transformer.strip(original_content)
                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    all_modified_files.append(file_path)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = inject_docstrings(original_content, docs)
                    if original_content != injected_content:
                        source_path.write_text(injected_content, encoding="utf-8")
                        all_modified_files.append(source_path)
~~~~~
~~~~~python.new
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = self.transformer.inject(original_content, docs)
                    if original_content != injected_content:
                        source_path.write_text(injected_content, encoding="utf-8")
                        all_modified_files.append(source_path)
~~~~~

### 下一步建议
我们已经完成了 `StitcherApp` 内部的改造。现在，任何试图实例化 `StitcherApp` 的代码（如 CLI 和测试）都会因为参数缺失而失败。下一步必须是：
1.  修改 `stitcher-cli/factories.py`，在这里实例化 `PythonParser`, `PythonTransformer` 等，并注入到 App。
2.  修改集成测试中的 `WorkspaceFactory` 或相关辅助函数，确保测试也能正确构造 App。
