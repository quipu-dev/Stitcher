好的，我们开始执行路线图中的 `4.1 实现“观测域”逻辑`。

这个阶段的核心目标是让重构引擎（`stitcher-refactor`）能够“看到”并分析项目中的所有代码，而不仅仅是主源码包。我们将通过增强 `Workspace` 和 `SemanticGraph` 组件，使其能够加载在 `pyproject.toml` 中定义的 `peripheral_paths`（如 `examples/` 或 `scripts/`），从而为全域重构打下基础。

以下是实现此目标的详细计划。

## [WIP] feat: 为重构引擎实现“观测域”逻辑

### 用户需求

根据《Stitcher 重构路线图》v1.0 的第 4.1 节，需要实现“观测域”逻辑，使 `stitcher-refactor` 引擎能够加载并分析 `peripheral_paths` 中定义的代码文件。

### 评论

这是实现“全域重构”愿景的关键一步。它打破了“核心源码”与“周边代码”（如示例、脚本）之间的壁垒，使重构引擎能够将整个项目视为一个统一的语义整体。这将极大地提升大规模重构的准确性和安全性，因为引擎现在可以追踪到跨越不同代码区域的符号引用。

### 目标

1.  **增强 `Workspace`**: 修改 `stitcher-refactor` 的 `Workspace` 类，使其能够明确区分“核心扫描路径”（`scan_paths`）和“周边观测路径”（`peripheral_paths`），并为后续逻辑提供一个查询文件是否属于周边的能力。
2.  **泛化 `SemanticGraph` 加载**: 修改 `SemanticGraph` 类，使其不再只加载特定的包，而是能够从 `Workspace` 获取完整的项目结构，并加载所有核心包和周边路径中的代码文件。
3.  **简化 `RefactorRunner`**: 更新 `RefactorRunner`，使其使用 `SemanticGraph` 新的、统一的加载方法，将加载逻辑的复杂性从运行器中移除，封装到图谱构建层。

### 基本原理

我们将遵循关注点分离的原则：
- `Workspace` 将成为项目物理布局的“真理之源”，负责解析配置并区分不同类型的代码区域。
- `SemanticGraph` 将消费 `Workspace` 提供的信息，负责构建一个覆盖全域代码的、完整的语义模型。它将封装所有与 `griffe` 加载器交互的细节。
- `RefactorRunner` 作为最高层的协调者，其职责被简化为初始化服务并调用 `SemanticGraph` 的高级加载接口，而无需关心加载的具体过程。

### 标签

#intent/build #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/instruct #task/domain/refactoring #task/object/workspace-discovery #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强 Workspace 以区分并管理周边路径

我们将修改 `Workspace` 类。首先，在初始化时添加 `peripheral_source_dirs` 集合。其次，更新 `_build_from_config` 方法以分别处理 `scan_paths` 和 `peripheral_paths`。接着，更新 `get_search_paths` 以确保 Griffe 能够搜索所有相关目录。最后，添加一个新的 `is_peripheral` 方法，为未来的 `Planner` 调整提供支持。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
class Workspace:
    def __init__(self, root_path: Path, config: Optional[StitcherConfig] = None):
        self.root_path = root_path
        self.config = config
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)

        if self.config:
            self._build_from_config()
        else:
            self._discover_packages()

    def _build_from_config(self) -> None:
        if not self.config:
            return

        all_paths_str = self.config.scan_paths + self.config.peripheral_paths
        for path_str in all_paths_str:
            code_dir = self.root_path / path_str
            if code_dir.is_dir():
                import_names = self._get_top_level_importables(code_dir)
                for import_name in import_names:
                    self.import_to_source_dirs[import_name].add(code_dir)
~~~~~
~~~~~python.new
class Workspace:
    def __init__(self, root_path: Path, config: Optional[StitcherConfig] = None):
        self.root_path = root_path
        self.config = config
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)
        self.peripheral_source_dirs: Set[Path] = set()

        if self.config:
            self._build_from_config()
        else:
            self._discover_packages()

    def _build_from_config(self) -> None:
        if not self.config:
            return

        # Process main scan paths
        for path_str in self.config.scan_paths:
            code_dir = self.root_path / path_str
            if code_dir.is_dir():
                import_names = self._get_top_level_importables(code_dir)
                for import_name in import_names:
                    self.import_to_source_dirs[import_name].add(code_dir)

        # Process peripheral paths
        for path_str in self.config.peripheral_paths:
            p_path = self.root_path / path_str
            if p_path.exists():
                self.peripheral_source_dirs.add(p_path)
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
    def get_search_paths(self) -> List[Path]:
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        all_paths.add(self.root_path)
        return sorted(list(all_paths))
~~~~~
~~~~~python.new
    def get_search_paths(self) -> List[Path]:
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        all_paths.update(self.peripheral_source_dirs)
        all_paths.add(self.root_path)
        return sorted(list(all_paths))

    def is_peripheral(self, file_path: Path) -> bool:
        abs_file_path = file_path.resolve()
        for p_dir in self.peripheral_source_dirs:
            # Path.is_relative_to is available in Python 3.9+
            try:
                abs_file_path.relative_to(p_dir.resolve())
                return True
            except ValueError:
                continue
        return False
~~~~~

#### Acts 2: 改造 SemanticGraph 以加载整个工作区

接下来，我们将修改 `SemanticGraph`。原来的 `load` 方法将被一个更强大的 `load_from_workspace` 方法取代。这个新方法将负责加载所有核心包和周边路径中的文件，最后统一解析别名并构建引用注册表。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        # Ensure we are dealing with a Module, not an Alias
        if isinstance(module, griffe.Module):
            self._modules[package_name] = module
            self._griffe_loader.resolve_aliases()
            self._build_registry(module)
~~~~~
~~~~~python.new
    def load_from_workspace(self) -> None:
        # 1. Load all main packages
        for pkg_name in self.workspace.import_to_source_dirs.keys():
            module = self._griffe_loader.load(pkg_name, submodules=True)
            if isinstance(module, griffe.Module):
                self._modules[pkg_name] = module

        # 2. Load all peripheral files/directories
        for p_dir in self.workspace.peripheral_source_dirs:
            if p_dir.is_dir():
                for py_file in p_dir.rglob("*.py"):
                    self._griffe_loader.load(py_file)
            elif p_dir.is_file() and p_dir.suffix == ".py":
                self._griffe_loader.load(p_dir)

        # 3. Resolve all aliases now that everything is loaded
        self._griffe_loader.resolve_aliases()

        # 4. Build usage registry for everything
        for module in self._griffe_loader.modules_collection.values():
            self._build_registry(module)
~~~~~

#### Acts 3: 简化 RefactorRunner 中的加载逻辑

最后，我们更新 `RefactorRunner`，用对 `graph.load_from_workspace()` 的一次调用替换掉原来复杂的包加载循环，使其逻辑更清晰、更符合其作为协调者的角色。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
            graph = SemanticGraph(workspace)

            # Load all packages discovered by the workspace
            pkg_names = list(workspace.import_to_source_dirs.keys())
            bus.debug(L.debug.log.refactor_discovered_packages, packages=pkg_names)
            for pkg_name in pkg_names:
                bus.debug(L.debug.log.refactor_loading_package, package=pkg_name)
                graph.load(pkg_name)

            ctx = RefactorContext(
                workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
            )
~~~~~
~~~~~python.new
            graph = SemanticGraph(workspace)

            # Load all workspace symbols, including main packages and peripherals
            graph.load_from_workspace()

            ctx = RefactorContext(
                workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
            )
~~~~~

### 下一步建议

我们已经成功地让重构引擎能够观测到整个项目。根据路线图，下一个逻辑步骤是 **4.2 调整 Planner 策略**。

具体来说，`Planner` 在处理文件移动或符号重命名时，需要利用我们刚刚在 `Workspace` 中添加的 `is_peripheral` 方法来检查目标文件。如果文件位于周边路径中，`Planner` 应该跳过生成 `SidecarUpdateIntent`，因为这些文件没有 `.stitcher.yaml` 或 `.json` 签名文件。

如果你同意，我将开始制定实现该调整的计划。
