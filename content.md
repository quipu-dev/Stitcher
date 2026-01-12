你提出了一个非常好的观点。

优先重构 `CheckRunner` 是一项更具战略意义的举措。它将在 `application` 和 `analysis` 两个核心包之间建立起一个端到端的“钢缆 (steel thread)”。这使我们能够立即验证两者之间的核心契约，并利用现有的 `check` 命令测试来驱动和验证整个重构过程。

我将立即调整计划，优先执行 `CheckRunner` 的集成。

## [WIP] refactor: 将 ConsistencyEngine 集成到 CheckRunner

### 用户需求

调整原定计划，优先重构 `stitcher.app.runners.check.CheckRunner`，使其不再使用本地的 `CheckAnalyzer`，而是调用新的 `stitcher.analysis.engines.consistency.ConsistencyEngine`。同时，需要适配数据提供者 (`Subject Adapters`) 以符合新的分析契约。

### 评论

这是一个关键的重构步骤，它首次将应用层（负责编排和IO）与分析层（负责规则和判断）连接起来。通过将 `CheckRunner` 改造为一个“适配器+中介者”，它将负责调用分析引擎，然后将分析结果（`Violation` 对象）转换为上游 `Resolver` 和 `Reporter` 所期望的旧数据结构。这是一种务实的、增量式的集成策略，可以在不一次性重构整个调用链的情况下，快速打通核心链路。

### 目标

1.  为 `stitcher-application` 添加对 `stitcher-analysis` 的依赖。
2.  更新 `ASTCheckSubjectAdapter` 和 `IndexCheckSubjectAdapter`，使其符合 `stitcher.analysis.protocols.AnalysisSubject` 协议。
3.  修改 `StitcherApp` 核心，在实例化 `CheckRunner` 时注入 `Differ` 依赖。
4.  重构 `CheckRunner` 的核心逻辑：
    *   移除对 `CheckAnalyzer` 的依赖。
    *   实例化并使用 `ConsistencyEngine`。
    *   实现将 `Violation` 列表转换为旧的 `FileCheckResult` (字典结构) 和 `InteractionContext` 列表的适配器逻辑。
5.  删除已被完全取代的 `stitcher.app.runners.check.analyzer.py` 文件。

### 基本原理

核心变更发生在 `CheckRunner` 中。它将不再包含任何分析逻辑，其新职责是：
1.  **数据准备**: 调用 `SubjectAdapter` 为分析引擎准备好输入数据。
2.  **委托分析**: 将 `Subject` 传递给 `ConsistencyEngine` 并获取分析结果 `FileCheckResult` (其中包含 `Violation` 列表)。
3.  **结果翻译**: 遍历 `Violation` 列表。根据每个 `Violation` 的 `kind` (一个 `SemanticPointer`)：
    *   将其归类到旧版 `FileCheckResult` 的 `errors`, `warnings`, `infos` 字典中。
    *   如果该 `Violation` 是一个需要用户交互的冲突 (如 `signature_drift` 或 `co_evolution`)，则创建一个对应的 `InteractionContext` 对象。
4.  **传递**: 将翻译好的旧版 `FileCheckResult` 和 `InteractionContext` 列表传递给 `Resolver` 和 `Reporter`。

通过这种方式，我们将新旧世界的“阻抗不匹配”问题隔离在了 `CheckRunner` 内部，为后续逐步重构 `Resolver` 和 `Reporter` 创造了条件。

### 标签

#intent/refine #flow/ready #priority/high #comp/application #comp/analysis #concept/architecture #scope/core #ai/brainstorm #task/domain/testing #task/object/check-command #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 为 `stitcher-application` 添加 `stitcher-analysis` 依赖

首先，我们需要在 `pyproject.toml` 中声明新的依赖关系。

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "pyneedle",
]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "stitcher-analysis",
    "pyneedle",
]
~~~~~

#### Acts 2: 更新 `Subject` 适配器以符合新协议

我们将修改 `subject.py`，更新 `SymbolState` 的导入路径，实现 `AnalysisSubject` 协议，并添加 `is_tracked` 属性。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python
from typing import Dict, Optional
from pathlib import Path
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.index import SymbolRecord
from stitcher.analysis.schema import SymbolState
from stitcher.analysis.protocols import AnalysisSubject as CheckSubject


class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStoreProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        root_path: Path,
    ):
        self._file_path = file_path
        self._index_store = index_store
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._root_path = root_path

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def is_tracked(self) -> bool:
        return (self._root_path / self._file_path).with_suffix(".stitcher.yaml").exists()

    def _is_public(self, fqn: str) -> bool:
        # Replicate public visibility logic from AST-based approach
        parts = fqn.split(".")
        return not any(p.startswith("_") and p != "__doc__" for p in parts)

    def is_documentable(self) -> bool:
        symbols = self._index_store.get_symbols_by_file_path(self.file_path)
        if not symbols:
            return False

        for sym in symbols:
            if sym.kind == "module" and sym.docstring_content:
                return True
            if sym.logical_path and self._is_public(sym.logical_path):
                return True
        return False

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load data from all sources
        symbols_from_db = self._index_store.get_symbols_by_file_path(self.file_path)
        yaml_docs = self._doc_manager.load_docs_for_path(self.file_path)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        yaml_content_hashes = {
            fqn: self._doc_manager.compute_ir_hash(ir) for fqn, ir in yaml_docs.items()
        }

        # 2. Map symbols for easy lookup
        symbol_map: Dict[str, SymbolRecord] = {}
        module_symbol: Optional[SymbolRecord] = None
        for sym in symbols_from_db:
            if sym.kind == "module":
                module_symbol = sym
            # CRITICAL: Only consider symbols that are definitions within this file,
            # not aliases (imports).
            elif sym.logical_path and sym.kind != "alias":
                symbol_map[sym.logical_path] = sym

        # 3. Aggregate all unique FQNs
        all_fqns = (
            set(symbol_map.keys()) | set(yaml_docs.keys()) | set(stored_hashes.keys())
        )
        if module_symbol:
            all_fqns.add("__doc__")

        states: Dict[str, SymbolState] = {}

        # 4. Build state for each FQN
        for fqn in all_fqns:
            symbol_rec: Optional[SymbolRecord] = None
            if fqn == "__doc__":
                symbol_rec = module_symbol
            else:
                symbol_rec = symbol_map.get(fqn)

            stored_fp = stored_hashes.get(fqn, Fingerprint())

            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=self._is_public(fqn),
                # Source Code State (from Index)
                exists_in_code=(symbol_rec is not None),
                source_doc_content=symbol_rec.docstring_content if symbol_rec else None,
                signature_hash=symbol_rec.signature_hash if symbol_rec else None,
                signature_text=symbol_rec.signature_text if symbol_rec else None,
                # YAML State
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_content_hashes.get(fqn),
                # Baseline State
                baseline_signature_hash=stored_fp.get("baseline_code_structure_hash"),
                baseline_signature_text=stored_fp.get("baseline_code_signature_text"),
                baseline_yaml_content_hash=stored_fp.get("baseline_yaml_content_hash"),
            )

        return states


class ASTCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        root_path: Path,
    ):
        self._module = module_def
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._fingerprint_strategy = fingerprint_strategy
        self._root_path = root_path

    @property
    def file_path(self) -> str:
        return self._module.file_path

    @property
    def is_tracked(self) -> bool:
        # For virtual modules (plugins), they are conceptually always "tracked"
        # as they don't have a corresponding file to check.
        if not self._module.file_path:
            return True
        return (self._root_path / self.file_path).with_suffix(".stitcher.yaml").exists()

    def _compute_fingerprints(self) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in self._module.functions:
            fingerprints[func.name] = self._fingerprint_strategy.compute(func)
        for cls in self._module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self._fingerprint_strategy.compute(method)
        return fingerprints

    def is_documentable(self) -> bool:
        return self._module.is_documentable()

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())
        # The module docstring key is always valid/present in code context,
        # even if the source file has no docstring.
        code_fqns.add("__doc__")

        fingerprints = self._compute_fingerprints()
        yaml_hashes = self._doc_manager.compute_yaml_content_hashes(self._module)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        all_fqns = code_fqns | set(yaml_docs.keys()) | set(stored_hashes.keys())
        states: Dict[str, SymbolState] = {}

        # 2. Iterate and build the state object for each symbol
        for fqn in all_fqns:
            fp = fingerprints.get(fqn, Fingerprint())
            source_ir = source_docs.get(fqn)
            stored_fp = stored_hashes.get(fqn, Fingerprint())

            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=(fqn in public_fqns),
                exists_in_code=(fqn in code_fqns),
                source_doc_content=source_ir.summary if source_ir else None,
                signature_hash=fp.get("current_code_structure_hash"),
                signature_text=fp.get("current_code_signature_text"),
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_hashes.get(fqn),
                baseline_signature_hash=stored_fp.get("baseline_code_structure_hash"),
                baseline_signature_text=stored_fp.get("baseline_code_signature_text"),
                baseline_yaml_content_hash=stored_fp.get("baseline_yaml_content_hash"),
            )

        return states
~~~~~

#### Acts 3: 更新 `StitcherApp` 以注入 `Differ`

`CheckRunner` 需要 `Differ` 来实例化新的 `ConsistencyEngine`。我们需要修改 `StitcherApp` 来传递这个依赖。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 3. Runners (Command Handlers)
        check_analyzer = CheckAnalyzer(root_path, self.differ)
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
            analyzer=check_analyzer,
            resolver=check_resolver,
            reporter=check_reporter,
        )
~~~~~
~~~~~python.new
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
~~~~~

#### Acts 4: 重构 `CheckRunner`

这是核心步骤，我们将用 `ConsistencyEngine` 替换 `CheckAnalyzer`，并添加适配器逻辑。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python
from typing import List, Tuple
from pathlib import Path

from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
    DifferProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult

from .protocols import (
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter
from stitcher.analysis.engines.consistency import create_consistency_engine


class CheckRunner:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        differ: DifferProtocol,
        resolver: CheckResolverProtocol,
        reporter: CheckReporterProtocol,
        root_path: Path,
    ):
        # Keep services needed by adapter
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store
        self.root_path = root_path

        # Injected sub-components
        self.engine = create_consistency_engine(differ=differ)
        self.resolver = resolver
        self.reporter = reporter

    def _translate_results(
        self, analysis_result: "FileCheckResult"
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        # This is the adapter logic. It translates the new, unified `FileCheckResult`
        # from the analysis engine into the old structures expected by the resolver/reporter.

        legacy_result = FileCheckResult(path=analysis_result.path)
        conflicts: List[InteractionContext] = []

        # Mapping from new Violation 'kind' to old result dict keys
        KIND_TO_LEGACY_MAP = {
            # Errors
            str(L.check.issue.conflict): ("errors", "conflict"),
            str(L.check.state.signature_drift): ("errors", "signature_drift"),
            str(L.check.state.co_evolution): ("errors", "co_evolution"),
            str(L.check.issue.extra): ("errors", "extra"),
            str(L.check.issue.pending): ("errors", "pending"),
            # Warnings
            str(L.check.issue.missing): ("warnings", "missing"),
            str(L.check.issue.redundant): ("warnings", "redundant"),
            str(L.check.file.untracked): ("warnings", "untracked"),
            str(L.check.file.untracked_with_details): ("warnings", "untracked_detailed"),
            # Infos
            str(L.check.state.doc_updated): ("infos", "doc_improvement"),
        }

        # Which violations trigger an interactive context
        INTERACTIVE_VIOLATIONS = {
            str(L.check.state.signature_drift),
            str(L.check.state.co_evolution),
            str(L.check.issue.extra),
            str(L.check.issue.conflict),
        }

        for violation in analysis_result.violations:
            kind_str = str(violation.kind)

            # 1. Populate legacy result dictionaries
            if kind_str in KIND_TO_LEGACY_MAP:
                category, key = KIND_TO_LEGACY_MAP[kind_str]
                target_dict = getattr(legacy_result, category)
                target_dict[key].append(violation.fqn)

            # 2. Create InteractionContext for resolvable conflicts
            if kind_str in INTERACTIVE_VIOLATIONS:
                conflicts.append(
                    InteractionContext(
                        file_path=legacy_result.path,
                        fqn=violation.fqn,
                        violation_type=violation.kind,
                        signature_diff=violation.context.get("signature_diff"),
                        doc_diff=violation.context.get("doc_diff"),
                    )
                )

        return legacy_result, conflicts

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path,
                self.index_store,
                self.doc_manager,
                self.sig_manager,
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            legacy_result, conflicts = self._translate_results(analysis_result)
            all_results.append(legacy_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            legacy_result, conflicts = self._translate_results(analysis_result)
            all_results.append(legacy_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

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

#### Acts 5: 删除旧的 `CheckAnalyzer`

现在 `CheckAnalyzer` 已经完全被 `ConsistencyEngine` 和 `CheckRunner` 中的适配器逻辑取代，可以安全地删除它。

~~~~~act
delete_file
packages/stitcher-application/src/stitcher/app/runners/check/analyzer.py
~~~~~

### 下一步建议

我们已经成功地将分析逻辑的核心链路切换到了新的 `stitcher-analysis` 包。

下一步，我们可以选择：
1.  **提取 Pump 逻辑**: 继续执行原计划，将 `PumpAnalyzer` 迁移到 `stitcher-analysis` 中，以完成所有分析逻辑的物理分离。
2.  **深化 Check 重构**: 重构 `CheckResolver` 和 `CheckReporter`，让它们原生支持 `Violation` 对象，从而移除 `CheckRunner` 中的适配器/翻译逻辑，使代码更加纯粹。

我建议继续**提取 Pump 逻辑**，以完成本次重构的“物理分离”大目标。之后再进行内部的“逻辑提纯”。
