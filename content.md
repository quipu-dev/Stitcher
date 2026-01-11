好的，我们来重构 `cov` 命令，使其充分利用索引带来的性能优势。

这将是一个重要的架构改进，目标是将 `cov` 命令从一个CPU密集型的AST解析任务，转变为一个IO密集型的数据库查询任务，从而大幅提升其执行速度。

我将生成一个计划来实现这一重构。

## [WIP] refactor(cov): 迁移覆盖率 runner 以使用语义索引

### 用户需求

用户要求重构 `cov`（文档覆盖率）命令，使其利用 `stitcher-index` 提供的数据，而不是在每次运行时都实时解析整个项目的抽象语法树（AST）。

### 评论

这是一个非常明智的重构。`cov` 命令的本质是一个只读的分析任务，其所需的所有信息（哪些符号是公开的、哪些已有文档）都已存在于索引中。利用索引是其设计的初衷，这次重构将是展示索引价值的绝佳范例，并能显著改善大型项目中的开发者体验。

### 目标

1.  **解耦 `CoverageRunner`**: 将 `CoverageRunner` 从对 `ModuleDef`（AST 的内存表示）的直接依赖中解耦出来。
2.  **切换数据源**: 修改 `CoverageRunner` 的核心逻辑，使其不再遍历 `ModuleDef`，而是通过文件路径直接查询 `IndexStore` 来获取符号信息。
3.  **优化入口点**: 更新 `StitcherApp.run_cov` 方法，彻底绕过昂贵的 `_configure_and_scan` 全量扫描步骤，直接将文件列表传递给新的 `CoverageRunner`。

### 基本原理

当前的 `cov` 命令为了计算覆盖率，需要为每个源文件执行一次完整的 AST 解析，这是一个非常耗时的过程。然而，`stitcher-index` 本质上就是整个项目 AST 的一个持久化、可查询的缓存。

本次重构的核心思想是：
-   将 `CoverageRunner` 的输入从 `List[ModuleDef]` 更改为 `List[str]`（文件路径列表）。
-   在 `CoverageRunner` 内部，通过 `index_store.get_symbols_by_file_path()` 方法，廉价地获取一个文件的所有符号元数据。
-   基于这些元数据（`logical_path`, `kind`, `docstring_content`），在内存中重建计算覆盖率所需的信息，从而完全避免了对源文件的解析。

这将使 `cov` 命令的速度从分钟级降低到秒级，特别是在大型代码库中。

*注意：为了保持本次重构的专注性和高收益，我们将暂时简化逻辑，使其首先专注于处理物理源文件的覆盖率。对虚拟插件（plugins）的覆盖率计算将在后续迭代中重新引入。*

### 标签

#intent/refine #flow/ready #priority/high #comp/cli #concept/state #scope/core #scope/dx #ai/instruct #task/domain/testing #task/object/coverage #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新 CoverageRunner 以接受 IndexStore

首先，我们需要为 `CoverageRunner` 注入 `IndexStore` 依赖，并相应地在 `StitcherApp` 中更新其构造函数。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/coverage.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
from pathlib import Path
from typing import List
import typer

from stitcher.app.services import DocumentManager
from stitcher.app.types import CoverageResult
from stitcher.spec import ModuleDef
from stitcher.index.store import IndexStore


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        index_store: IndexStore,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.index_store = index_store

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
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)
~~~~~
~~~~~python.new
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(
            root_path, self.doc_manager, self.index_store
        )
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)
~~~~~

#### Acts 2: 实现基于索引的核心分析逻辑

现在，我们将用基于索引的新逻辑替换掉旧的、基于 AST 的分析方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/coverage.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    def _analyze_path_coverage(self, file_path: str) -> CoverageResult:
        # Query index for public, defined symbols
        all_symbols = self.index_store.get_symbols_by_file_path(file_path)
        public_fqns = set()

        # is_documentable check
        has_public_members = False
        module_symbol = next((s for s in all_symbols if s.kind == "module"), None)
        if module_symbol and module_symbol.docstring_content:
            has_public_members = True

        for sym in all_symbols:
            if sym.kind == "alias" or not sym.logical_path:
                continue

            parts = sym.logical_path.split(".")
            is_public = not any(p.startswith("_") and p != "__doc__" for p in parts)
            if is_public:
                public_fqns.add(sym.logical_path)
                has_public_members = True

        if has_public_members and module_symbol:
            public_fqns.add("__doc__")

        documented_fqns = set(self.doc_manager.load_docs_for_path(file_path).keys())

        if module_symbol and module_symbol.docstring_content:
            documented_fqns.add("__doc__")

        total = len(public_fqns)
        documented = len(public_fqns.intersection(documented_fqns))
        missing = total - documented
        coverage = (documented / total * 100) if total > 0 else 100.0

        return CoverageResult(
            path=file_path,
            total_symbols=total,
            documented_symbols=documented,
            missing_symbols=missing,
            coverage=coverage,
        )

    def run_batch(self, file_paths: List[str]) -> List[CoverageResult]:
        results = []
        for file_path in file_paths:
            results.append(self._analyze_path_coverage(file_path))
        return results

    def report(self, results: List[CoverageResult]):
        if not results:
            return
~~~~~

#### Acts 3: 更新 `StitcherApp.run_cov` 以绕过 AST 扫描

最后一步，修改 `run_cov` 的调用流程，使其直接从配置中获取文件列表并传递给新的 `CoverageRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_cov(self) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []

        for config in configs:
            modules = self._configure_and_scan(config)
            results = self.coverage_runner.run_batch(modules)
            all_results.extend(results)

        self.coverage_runner.report(all_results)
        return True
~~~~~
~~~~~python.new
    def run_cov(self) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []

        for config in configs:
            # Bypassing the expensive scan, getting file paths directly
            files_to_process = self.scanner.get_files_from_config(config)
            relative_paths = [
                p.relative_to(self.root_path).as_posix() for p in files_to_process
            ]

            # Note: Plugin coverage is temporarily disabled in this refactor
            # to focus on the performance gain from file-based indexing.
            # It can be re-introduced later as a separate step.
            if not relative_paths:
                continue

            results = self.coverage_runner.run_batch(relative_paths)
            all_results.extend(results)

        self.coverage_runner.report(all_results)
        return True
~~~~~

### 下一步建议

1.  **运行测试**: 运行现有的 `cov` 相关测试，确保重构后的逻辑与旧逻辑在结果上保持一致。可能需要调整测试用例，使其不再依赖 `ModuleDef`，而是直接操作文件和索引。
2.  **性能基准测试**: 在一个中大型代码库上对重构前后的 `stitcher cov` 命令进行基准测试，量化性能提升。
3.  **重新引入插件支持**: 如果需要，可以设计一种混合模式，让 `run_cov` 能够处理来自索引的文件和来自实时解析的插件，将两组 `CoverageResult` 合并后进行报告。
