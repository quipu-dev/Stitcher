好的，我们继续执行路线图，开始任务 2.2：统一工作区构建。

这个任务的目标是消除 `stitcher-refactor` 中独立的配置解析逻辑，使其完全依赖于 `stitcher-config` 提供的统一配置模型。这将确保重构引擎看到的文件系统视图与项目中其他部分（如 `scanner`）完全一致。

我将生成一个计划来执行这项重构。

## [WIP] refactor: Unify Workspace construction to use StitcherConfig

### 用户需求

执行路线图中的任务 2.2，统一 `stitcher-refactor` 的工作区构建逻辑。需要修改 `Workspace` 类，使其不再自行解析 `pyproject.toml`，而是通过接收一个 `StitcherConfig` 对象来初始化。同时，需要调整调用链（`StitcherApp` -> `RefactorRunner`）以加载并传递此配置对象。

### 评论

这是一次至关重要的架构对齐。通过让 `Workspace` 依赖于 `StitcherConfig`，我们不仅遵循了 DRY (Don't Repeat Yourself) 原则，消除了重复的配置加载代码，更重要的是，我们确保了整个系统对于“项目包含哪些文件”这个核心问题有了一个单一的、权威的答案。这为后续实现对 `examples/` 等周边路径的重构支持（阶段四）铺平了道路，是架构走向统一和稳健的关键一步。

### 目标

1.  **重构 `Workspace`**: 修改 `stitcher.refactor.engine.workspace.py`，移除其内部的 `pyproject.toml` 发现和解析逻辑。
2.  **更新 `Workspace` 构造函数**: 更改其 `__init__` 方法，使其接受一个 `StitcherConfig` 实例。
3.  **调整 `RefactorRunner`**: 修改 `stitcher.app.runners.refactor.py` 中的 `run_apply` 方法，使其能够接收 `StitcherConfig` 并将其传递给 `Workspace`。
4.  **打通 `StitcherApp`**: 修改 `stitcher.app.core.py` 中的 `run_refactor_apply` 方法，使其在执行重构前加载配置，并将配置传递给 `RefactorRunner`。

### 基本原理

我们将采用自顶向下的方式进行修改：
1.  首先在 `StitcherApp` 的 `run_refactor_apply` 方法中，调用 `_load_configs()` 来获取配置。考虑到一次重构通常针对一个目标，我们将使用找到的第一个配置。
2.  然后，将这个配置对象作为参数传递给 `RefactorRunner.run_apply`。
3.  接着，在 `RefactorRunner` 中，我们将配置对象再传递给 `Workspace` 的构造函数。
4.  最后，对 `Workspace` 类本身进行重构。我们将用一个 `_build_from_config` 的新方法取代旧的 `_discover_packages` 方法。这个新方法将直接从传入的 `StitcherConfig` 对象的 `scan_paths` 和 `peripheral_paths` 字段中读取路径，从而完成工作区文件视图的构建。

### 标签

#intent/refine #flow/ready #priority/high #comp/refactor #comp/application #concept/config #scope/core #ai/instruct #task/domain/architecture #task/object/config-unification #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 Workspace 引擎

我们将彻底重写 `workspace.py`，移除其文件发现逻辑，改为直接消费 `StitcherConfig` 对象。这是一个结构性的大改动，因此使用 `write_file` 是最合适的策略。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/workspace.py
~~~~~
~~~~~python
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from stitcher.config import StitcherConfig

log = logging.getLogger(__name__)


class Workspace:
    def __init__(self, root_path: Path, config: StitcherConfig):
        self.root_path = root_path
        self.config = config
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)
        self._build_from_config()

    def _build_from_config(self) -> None:
        all_paths_str = self.config.scan_paths + self.config.peripheral_paths
        for path_str in all_paths_str:
            code_dir = self.root_path / path_str
            if code_dir.is_dir():
                import_names = self._get_top_level_importables(code_dir)
                for import_name in import_names:
                    # The directory to add to the search path is the code_dir itself
                    self.import_to_source_dirs[import_name].add(code_dir)

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        if not src_path.is_dir():
            return []

        for item in src_path.iterdir():
            # A potential top-level package is a directory whose name is a valid identifier,
            # explicitly excluding special dunders like __pycache__.
            if (
                item.is_dir()
                and item.name.isidentifier()
                and item.name != "__pycache__"
            ):
                names.add(item.name)
            # A potential top-level module is a .py file whose stem is a valid identifier.
            elif (
                item.is_file()
                and item.name.endswith(".py")
                and item.stem.isidentifier()
            ):
                names.add(item.stem)
        return list(names)

    def get_search_paths(self) -> List[Path]:
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        # Also add the root path itself to handle cases where pyproject.toml is nested
        # but top-level modules need to be found.
        all_paths.add(self.root_path)
        return sorted(list(all_paths))
~~~~~

#### Acts 2: 更新 RefactorRunner

现在 `Workspace` 需要一个 `StitcherConfig` 对象，我们需要修改 `RefactorRunner` 来提供它。我们将修改 `run_apply` 方法的签名和实现。

首先，添加必要的 `import` 语句。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
from typing import Callable, Optional
~~~~~
~~~~~python.new
from typing import Callable, Optional
from stitcher.config import StitcherConfig
~~~~~

然后，更新 `run_apply` 方法以接受并使用 `config` 对象。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
    def run_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            workspace = Workspace(self.root_path)
~~~~~
~~~~~python.new
    def run_apply(
        self,
        migration_script: Path,
        config: StitcherConfig,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            workspace = Workspace(self.root_path, config)
~~~~~

#### Acts 3: 更新 StitcherApp

最后一步是打通调用链，让 `StitcherApp` 在调用 `RefactorRunner` 之前加载配置。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_refactor_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        return self.refactor_runner.run_apply(
            migration_script, dry_run, confirm_callback
        )
~~~~~
~~~~~python.new
    def run_refactor_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        configs, _ = self._load_configs()
        if not configs:
            bus.error(L.error.config.not_found)
            return False

        # For refactoring, we use the first available config.
        # This could be extended in the future to allow target selection via CLI.
        config_to_use = configs[0]

        return self.refactor_runner.run_apply(
            migration_script, config_to_use, dry_run, confirm_callback
        )
~~~~~

### 下一步建议

我们已经成功地将 `refactor` 引擎的配置与发现机制与系统其他部分统一起来了。现在，`refactor` 引擎可以“看到”由 `peripheral_paths` 定义的周边文件了。

根据路线图，下一步是进入 **阶段四：全域重构支持**，具体任务是：
-   **任务 4.1：实现“观测域”逻辑**：修改 `SemanticGraph.load()`，使其能够加载并解析 `peripheral_paths` 中定义的脚本文件。
-   **任务 4.2：调整 Planner 策略**：修改 `Planner`，使其在处理位于 `peripheral_paths` 中的文件时，能够跳过 Sidecar 相关的操作，因为这些文件通常没有 `.stitcher.yaml`。

如果你同意，我将开始制定执行任务 4.1 的计划。
