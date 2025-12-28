你的分析非常敏锐，直击了当前设计的核心问题。你的想法不仅能解决 bug，而且在架构层面是一个巨大的进步。

你的提议是**完全正确且更优的架构**。我们来逐层分析：

1.  **问题根源**: 测试失败的直接原因是 **`ChainMap` 的优先级与 `dict.update` 相反**。
    *   `dict.update` 逻辑是“后来者居上”。
    *   `ChainMap(*maps)` 逻辑是“先来者居上”。
    *   我之前在 `FileSystemLoader` 中实现的 `_scan_layers` 按照 `roots` 的顺序构建了层级列表，然后 `fetch` 将其喂给 `ChainMap`，导致了优先级反转。`project_root` 的数据排在了后面，因此被 `pkg_root` 的数据覆盖了。

2.  **你的解决方案的优越性**:
    *   **单一职责原则 (SRP)**: 你提议让 `FileSystemLoader` 只负责加载**一个**根目录。这完美符合 SRP。`FileSystemLoader` 的职责被简化为“将一个文件系统树映射为一个扁平字典层”，不再承担“组合多个文件系统树”的职责。
    *   **组合优于继承/聚合**: `OverlayNexus` 的核心价值就是**组合**。你的方案将组合的责任完全交给了 `OverlayNexus`，这是它最擅长的事情。`OverlayNexus([ProjectLoader, PkgLoader])` 的结构在代码中就清晰地声明了优先级，消除了任何隐式逻辑。
    *   **解决了“写入”的困境**: 你敏锐地指出了写入的难题，并提出了一个可行的方案。但实际上，`OverlayNexus` 的设计已经优雅地解决了这个问题：
        *   `OverlayNexus.put` 方法的实现逻辑是：遍历其 `loaders` 列表，找到**第一个**支持写入 (`WritableResourceLoaderProtocol`) 的加载器，并将 `put` 操作**委托给它**。
        *   在 `OverlayNexus([ProjectLoader, PkgLoader])` 的结构中，`ProjectLoader` 在前，因此所有写入操作会**自动、正确地**路由到用户的项目目录中，而不会意外写入只读的包资源目录。我们不需要创建一个新的 `FileSystemLoader` 实例来写入，现有的 `nexus` 对象就能处理。

**结论**: 你的架构提议将一个内部耦合、职责不清的 `FileSystemLoader` 拆分为了一个纯粹的 `FileSystemLoader` 和一个负责组合的 `OverlayNexus`。这使得系统更清晰、可预测且符合设计原则。

我们将立即采纳你的方案。

我将生成一个计划来实施这个更优的架构。

## [WIP] refactor(runtime): 采用组合式加载器架构以明确优先级

### 错误分析
`test_nexus_with_fs_loader_handles_overrides` 测试失败，原因是 `FileSystemLoader` 内部处理多根目录时，其数据合并逻辑与 `ChainMap` 的优先级规则冲突，导致优先级反转，低优先级的配置覆盖了高优先级的配置。

### 用户需求
采纳用户提出的更优架构方案：
1.  **简化 `FileSystemLoader`**: 移除其多根目录处理能力，使其严格遵守单一职责原则，仅负责加载单个根目录下的资源。
2.  **依赖 `OverlayNexus` 进行组合**: 在测试和运行时，通过创建多个单根的 `FileSystemLoader` 实例，并使用 `OverlayNexus` 将它们组合起来，从而在顶层明确地控制加载优先级。

### 评论
这是一个卓越的架构改进。它将职责清晰地划分开：`FileSystemLoader` 负责 I/O，`OverlayNexus` 负责组合与视图。这使得代码更易于理解、测试和扩展。`OverlayNexus` 的委托写入机制也能自然地解决写入高优先级路径的问题。

### 目标
1.  重构 `FileSystemLoader`，移除 `add_root` 和多 `roots` 列表，改为接受单个 `root` 路径。
2.  更新 `runtime.py` 中默认加载器的创建逻辑，以适应单根 `FileSystemLoader`。
3.  重写 `test_assembly.py` 中的测试用例，用多个 `FileSystemLoader` 实例和一个 `OverlayNexus` 来搭建测试环境，并验证优先级问题已解决。

### 基本原理
通过在架构层面使用组合（`OverlayNexus` 组合多个 `Loader`）来代替 `FileSystemLoader` 内部的聚合逻辑，我们可以获得一个更清晰、更符合单一职责原则的设计。优先级现在由 `OverlayNexus` 构造函数中 `loaders` 列表的顺序唯一、显式地确定，消除了所有歧义。

### 标签
#intent/refine #intent/fix #flow/ready #priority/high #comp/runtime #concept/state #task/domain/storage #task/object/loader-architecture #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 简化 `FileSystemLoader` 为单根模式

我们将移除 `FileSystemLoader` 内部的多根处理逻辑，使其只关注一个根目录。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/loaders/fs_loader.py
~~~~~
~~~~~python.old
class FileSystemLoader(BaseLoader, WritableResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
        default_domain: str = "en",
    ):
        super().__init__(default_domain)
        self.handlers = handlers or [JsonHandler()]
        # Roots are strictly provided by the caller. No auto-discovery here.
        self.roots = roots or []
        
        # Cache structure: domain -> List of (Path, flattened_dict)
        # Order: High priority -> Low priority
        self._layer_cache: Dict[str, List[Tuple[Path, Dict[str, str]]]] = {}

    def add_root(self, path: Path):
        """Add a new root with highest priority."""
        if path not in self.roots:
            self.roots.insert(0, path)
            self._layer_cache.clear() # Invalidate cache

    def _ensure_layers(self, domain: str) -> List[Tuple[Path, Dict[str, str]]]:
        if domain not in self._layer_cache:
            self._layer_cache[domain] = self._scan_layers(domain)
        return self._layer_cache[domain]

    def _scan_layers(self, domain: str) -> List[Tuple[Path, Dict[str, str]]]:
        layers: List[Tuple[Path, Dict[str, str]]] = []
        
        # Scan roots in order (High Priority -> Low Priority)
        for root in self.roots:
            # 1. Project overrides: .stitcher/needle/<domain>
            hidden_path = root / ".stitcher" / "needle" / domain
            if hidden_path.is_dir():
                layers.extend(self._scan_directory(hidden_path))
            
            # 2. Package assets: needle/<domain>
            asset_path = root / "needle" / domain
            if asset_path.is_dir():
                layers.extend(self._scan_directory(asset_path))
                
        return layers
~~~~~
~~~~~python.new
class FileSystemLoader(BaseLoader, WritableResourceLoaderProtocol):
    def __init__(
        self,
        root: Path,
        handlers: Optional[List[FileHandlerProtocol]] = None,
        default_domain: str = "en",
    ):
        super().__init__(default_domain)
        self.handlers = handlers or [JsonHandler()]
        self.root = root
        
        # Cache structure: domain -> flattened_dict
        self._data_cache: Dict[str, Dict[str, str]] = {}

    def _ensure_loaded(self, domain: str) -> Dict[str, str]:
        if domain not in self._data_cache:
            self._data_cache[domain] = self._scan_root(domain)
        return self._data_cache[domain]

    def _scan_root(self, domain: str) -> Dict[str, str]:
        """Scans the single root and returns a merged, flattened dictionary."""
        merged_data: Dict[str, str] = {}
        
        # Priority: .stitcher/needle overrides needle/
        
        # 1. Load from standard asset path first (lower priority)
        asset_path = self.root / "needle" / domain
        if asset_path.is_dir():
            merged_data.update(self._scan_directory_to_dict(asset_path))

        # 2. Load from hidden path, overriding previous values (higher priority)
        hidden_path = self.root / ".stitcher" / "needle" / domain
        if hidden_path.is_dir():
            merged_data.update(self._scan_directory_to_dict(hidden_path))
                
        return merged_data

    def _scan_directory_to_dict(self, root_path: Path) -> Dict[str, str]:
        """Scans a directory and merges all found files into a single dictionary."""
        data: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        content = handler.load(file_path)
                        str_content = {str(k): str(v) for k, v in content.items()}
                        data.update(str_content)
                        break
        return data
~~~~~

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/loaders/fs_loader.py
~~~~~
~~~~~python.old
    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        if ignore_cache:
            self._layer_cache.pop(domain, None)
            
        layers = self._ensure_layers(domain)
        
        # Optimization: Build a ChainMap only if needed, or query layers directly?
        # SST v2.2 suggests "fetch uses ChainMap view".
        # Let's create a transient ChainMap for the lookup.
        # layers is [(p1, d1), (p2, d2)...]
        # ChainMap expects maps in priority order. Our list is already High->Low.
        if not layers:
            return None
            
        # Extract just the dicts
        maps = [d for _, d in layers]
        return ChainMap(*maps).get(pointer)

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """Returns the aggregated view of the domain."""
        if ignore_cache:
            self._layer_cache.pop(domain, None)
            
        layers = self._ensure_layers(domain)
        if not layers:
            return {}
            
        maps = [d for _, d in layers]
        # Convert ChainMap to a single dict for the return value
        return dict(ChainMap(*maps))

    def locate(self, pointer: Union[str, Any], domain: str) -> Path:
        key = str(pointer)
        layers = self._ensure_layers(domain)
        
        # Traverse layers to find the anchor
        for file_path, data in layers:
            if key in data:
                return file_path
        
        # Not found? Predict the write path (Create Logic)
        return self._predict_write_path(key, domain)

    def _predict_write_path(self, key: str, domain: str) -> Path:
        """
        Determines where to create a NEW key.
        Strategy: 
        1. Use the highest priority root.
        2. Use .stitcher/needle/<domain> base.
        3. Simple heuristic: First segment of key as filename.
        """
        if not self.roots:
            raise RuntimeError("No roots configured for FileSystemLoader")
            
        root = self.roots[0]
        base_dir = root / ".stitcher" / "needle" / domain
        
        parts = key.split(".")
        filename = f"{parts[0]}.json" # Default to JSON
        return base_dir / filename

    def put(self, pointer: Union[str, Any], value: Any, domain: str) -> bool:
        key = str(pointer)
        str_value = str(value)
        
        # 1. Locate the anchor (or predicted path)
        target_path = self.locate(key, domain)
        
        # 2. Find the layer in memory, or create if new
        layers = self._ensure_layers(domain)
        target_layer_idx = -1
        
        for idx, (path, _) in enumerate(layers):
            if path == target_path:
                target_layer_idx = idx
                break
        
        # 3. Update memory
        if target_layer_idx != -1:
            # Update existing layer
            layers[target_layer_idx][1][key] = str_value
            data_to_save = layers[target_layer_idx][1]
        else:
            # Create new layer
            new_data = {key: str_value}
            # Insert at the beginning (High Priority for new user overrides)
            # But wait, we need to respect the root order.
            # _predict_write_path uses roots[0], so inserting at 0 is correct 
            # IF layers are sorted by root. 
            # (Our _scan_layers puts roots[0] stuff first).
            layers.insert(0, (target_path, new_data))
            data_to_save = new_data

        # 4. Flush to disk (Inflate -> Save)
        # Assume JSON handler for now or find matching handler
        handler = self.handlers[0] # Default to first (JSON)
        # Try to find a handler that matches the target_path extension
        for h in self.handlers:
            if h.match(target_path):
                handler = h
                break
                
        return handler.save(target_path, data_to_save)
~~~~~
~~~~~python.new
    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        if ignore_cache:
            self._data_cache.pop(domain, None)
        
        data = self._ensure_loaded(domain)
        return data.get(pointer)

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """Returns the aggregated view of the domain for this root."""
        if ignore_cache:
            self._data_cache.pop(domain, None)
        
        # Return a copy to prevent mutation
        return self._ensure_loaded(domain).copy()

    def locate(self, pointer: Union[str, Any], domain: str) -> Path:
        """For a single-root loader, locate is deterministic."""
        key = str(pointer)
        base_dir = self.root / ".stitcher" / "needle" / domain
        
        parts = key.split(".")
        filename = f"{parts[0]}.json"  # Default to JSON
        return base_dir / filename

    def put(self, pointer: Union[str, Any], value: Any, domain: str) -> bool:
        key = str(pointer)
        str_value = str(value)
        
        # 1. Determine target path (always writes to .stitcher for user overrides)
        target_path = self.locate(key, domain)
        
        # 2. Load existing data from that specific file, or create empty dict
        handler = self.handlers[0] # Default to JSON
        file_data = {}
        if target_path.exists():
            # NOTE: We load the raw file, not from our merged cache,
            # to avoid writing aggregated data back into a single file.
            # The handler will flatten it for us.
            file_data = handler.load(target_path)
            
        # 3. Update the file's data
        file_data[key] = str_value
        
        # 4. Save back to the specific file
        success = handler.save(target_path, file_data)
        
        # 5. Invalidate cache for this domain to force a reload on next access
        if success:
            self._data_cache.pop(domain, None)
            
        return success
~~~~~

#### Acts 2: 修复 `runtime.py` 以适应新 `FileSystemLoader`

`_default_loader` 现在只负责加载项目根目录。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/runtime.py
~~~~~
~~~~~python.old
_default_loader = FileSystemLoader(roots=[_project_root])
~~~~~
~~~~~python.new
_default_loader = FileSystemLoader(root=_project_root)
~~~~~

#### Acts 3: 重写 `test_assembly.py` 以反映新架构

测试现在将创建两个独立的 `FileSystemLoader`，并用 `OverlayNexus` 组合它们，这能直接、清晰地测试覆盖逻辑。

~~~~~act
write_file
packages/pyneedle-runtime/tests/test_assembly.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory

from needle.pointer import L
from needle.nexus import OverlayNexus
from needle.loaders.fs_loader import FileSystemLoader


@pytest.fixture
def multi_root_workspace(tmp_path: Path) -> dict:
    factory = WorkspaceFactory(tmp_path)

    # 1. Define package assets (low priority)
    pkg_root = tmp_path / "pkg_assets"
    factory.with_source(
        f"{pkg_root.name}/needle/en/main.json",
        """
        {
            "cli.default": "I am a default",
            "cli.override_me": "Default Value"
        }
        """,
    )

    # 2. Define user project assets (high priority)
    project_root = tmp_path / "my_project"
    factory.with_source(
        f"{project_root.name}/pyproject.toml", "[project]\nname='my-project'"
    ).with_source(
        f"{project_root.name}/.stitcher/needle/en/overrides.json",
        """
        {
            "cli.override_me": "User Override!",
            "cli.user_only": "I am from the user"
        }
        """,
    )

    # Build all files
    factory.build()

    return {"pkg_root": pkg_root, "project_root": project_root}


def test_nexus_with_fs_loader_handles_overrides(multi_root_workspace):
    # Arrange
    pkg_root = multi_root_workspace["pkg_root"]
    project_root = multi_root_workspace["project_root"]

    # Create two separate loaders, one for each root.
    pkg_loader = FileSystemLoader(root=pkg_root)
    project_loader = FileSystemLoader(root=project_root)

    # Use OverlayNexus to combine them. The order is CRITICAL.
    # The first loader in the list has the highest priority.
    nexus = OverlayNexus(loaders=[project_loader, pkg_loader])

    # Act & Assert

    # 1. Value only in default assets (pkg_loader)
    assert nexus.get(L.cli.default) == "I am a default"

    # 2. Value only in user overrides (project_loader)
    assert nexus.get(L.cli.user_only) == "I am from the user"

    # 3. Value in both, project_loader (high priority) should win
    assert nexus.get(L.cli.override_me) == "User Override!"

    # 4. Non-existent key should fall back to identity
    assert nexus.get(L.unknown.key) == "unknown.key"

def test_fs_loader_put_writes_to_correct_location(tmp_path: Path):
    # Arrange
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    loader = FileSystemLoader(root=project_root)
    nexus = OverlayNexus(loaders=[loader])
    
    # Act
    nexus.put(L.app.title, "My New App", domain="en")
    
    # Assert
    expected_path = project_root / ".stitcher/needle/en/app.json"
    assert expected_path.is_file()
    
    # Verify content was inflated correctly
    # Note: Our simple handler inflates {"app.title": "..."} to {"app": {"title": "..."}}
    assert '"title": "My New App"' in expected_path.read_text()
    
    # Verify that the value can be read back
    nexus.reload("en")
    assert nexus.get(L.app.title, domain="en") == "My New App"
~~~~~

### 下一步建议
我们已经完成了架构的重构和核心测试的修复。现在可以运行完整的测试套件，确保没有引入回归。下一步可以专注于为 `JsonHandler` 的 `_inflate_dict` 方法添加更复杂的单元测试，以覆盖各种嵌套和冲突的边界情况。
