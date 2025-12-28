简要回答：
好的，我将执行 **Needle SST v2.2** 的实现计划。这将涉及重写 `JsonHandler` 以支持展平/膨胀逻辑，重构 `FileSystemLoader` 以采用混合 ChainMap 模型，并将根目录发现逻辑移至 `runtime` 模块以解耦。

## [WIP] refactor(runtime): 实现 Needle SST v2.2 混合 ChainMap 加载模型

### 用户需求
1.  **`JsonHandler` 升级**: 实现 SST v2.2 要求的读时展平 (`flatten`) 和写时膨胀 (`inflate`) 逻辑，并正确处理 `_` 自引用键。
2.  **`FileSystemLoader` 重构**:
    *   **移除隐式逻辑**: 移除内部查找项目根目录的逻辑，使其成为纯粹的路径加载器。
    *   **分层架构**: 内部维护一个有序的 `(Path, Dict)` 层级列表，而非单一的合并字典。
    *   **惰性聚合**: 使用 `ChainMap` 基于层级列表构建视图。
    *   **精确写入**: 实现 `locate` 和 `put`，确保写入操作定位到具体的文件层，并正确处理内存同步。
3.  **`runtime` 适配**: 在 `runtime` 模块中实现根目录发现逻辑，并将其注入到默认加载器中。

### 评论
SST v2.2 是 Needle 运行时的关键架构升级。通过将 I/O 操作与数据结构操作（ChainMap）分离，并引入明确的 Flatten/Inflate 协议，我们解决了“多文件合并”与“精确写入”之间的矛盾。将根目录发现移出 Loader 也是符合单一职责原则（SRP）的重要重构。

### 目标
1.  修改 `JsonHandler`，增加 `_flatten_dict` 和 `_inflate_dict` 方法。
2.  重写 `FileSystemLoader`，实现基于层级列表 (`List[Tuple[Path, Dict]]`) 的核心逻辑。
3.  更新 `runtime.py`，负责初始化默认加载器的根目录。

### 基本原理
1.  **展平/膨胀**: 开发者编辑的是嵌套的 JSON/YAML（DX友好），但运行时逻辑（FQN）需要扁平键（机器友好）。Handler 负责这一转换层，使 Loader 内部只需处理扁平数据。
2.  **混合模型**: `fetch` 需要速度（ChainMap O(1)），`put` 需要精度（定位特定文件）。通过维护有序的层级列表，我们可以同时满足这两个需求：`fetch` 在列表上构建 ChainMap，`put` 在列表上进行线性查找。
3.  **解耦**: Loader 只应关心“给定路径加载什么”，而不应关心“去哪里找路径”。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #task/domain/storage #task/object/loader-architecture #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 升级 `JsonHandler` 以支持数据变形
我们将修改 `JsonHandler`，在加载时将嵌套 JSON 展平为 FQN 键值对，并在保存时将其还原。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/loaders/json_handler.py
~~~~~
~~~~~python.old
    def load(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, path: Path, data: Dict[str, Any]) -> bool:
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            return True
        except OSError:
            return False
~~~~~
~~~~~python.new
    def load(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return self._flatten_dict(data)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, path: Path, data: Dict[str, Any]) -> bool:
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            nested_data = self._inflate_dict(data)
            with path.open("w", encoding="utf-8") as f:
                json.dump(nested_data, f, indent=2, sort_keys=True, ensure_ascii=False)
            return True
        except OSError:
            return False

    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "") -> Dict[str, str]:
        items: Dict[str, str] = {}
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if k == "_":
                new_key = parent_key
            
            if isinstance(v, dict):
                items.update(self._flatten_dict(v, new_key))
            else:
                items[new_key] = str(v)
        return items

    def _inflate_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in d.items():
            parts = k.split(".")
            d_curr = result
            for i, part in enumerate(parts[:-1]):
                if part not in d_curr:
                    d_curr[part] = {}
                else:
                    if not isinstance(d_curr[part], dict):
                        # Conflict: 'a' was a leaf, now needs to be a node.
                        # Convert 'val' to {'_': 'val'}
                        d_curr[part] = {"_": d_curr[part]}
                d_curr = d_curr[part]
            
            last_part = parts[-1]
            if last_part in d_curr:
                 # Conflict: 'a' was a node (or leaf), now assigning a value to it.
                 if isinstance(d_curr[last_part], dict):
                     d_curr[last_part]["_"] = v
                 else:
                     # Overwrite (should generally not happen with clean input)
                     d_curr[last_part] = v
            else:
                d_curr[last_part] = v
        return result
~~~~~

#### Acts 2: 重构 `FileSystemLoader`
实现混合 ChainMap 模型，移除根目录发现逻辑，实现精确的 `put` 和 `locate`。

~~~~~act
write_file
packages/pyneedle-runtime/src/needle/loaders/fs_loader.py
~~~~~
~~~~~python
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from collections import ChainMap

from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler

from needle.spec import WritableResourceLoaderProtocol
from needle.nexus import BaseLoader


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

    def _scan_directory(self, root_path: Path) -> List[Tuple[Path, Dict[str, str]]]:
        """
        Scans a directory for supported files.
        Returns a list of layers. 
        Note: The order of files within a directory is OS-dependent, 
        but we process them deterministically if needed.
        """
        layers = []
        # We walk top-down.
        for dirpath, _, filenames in os.walk(root_path):
            # Sort filenames to ensure deterministic loading order
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        # Handler is responsible for flattening
                        content = handler.load(file_path)
                        # Ensure content is strictly Dict[str, str]
                        str_content = {str(k): str(v) for k, v in content.items()}
                        layers.append((file_path, str_content))
                        break # Only use the first matching handler per file
        return layers

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

#### Acts 3: 更新 Runtime 以支持根目录发现
在 `runtime.py` 中实现 `_find_project_root`，并将其用于初始化 `_default_loader`。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/runtime.py
~~~~~
~~~~~python.old
from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus
from .loaders.fs_loader import FileSystemLoader

# --- Global Singleton Instance ---
# This is the "batteries-included" setup.
# It automatically discovers the project root and sets up a file system loader.
_default_loader = FileSystemLoader()
nexus = OverlayNexus(loaders=[_default_loader])
# ---------------------------------
~~~~~
~~~~~python.new
from pathlib import Path
from typing import Optional
from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus
from .loaders.fs_loader import FileSystemLoader

def _find_project_root(start_dir: Optional[Path] = None) -> Path:
    current_dir = (start_dir or Path.cwd()).resolve()
    # Stop at filesystem root
    while current_dir.parent != current_dir:
        if (current_dir / "pyproject.toml").is_file() or (
            current_dir / ".git"
        ).is_dir():
            return current_dir
        current_dir = current_dir.parent
    return start_dir or Path.cwd()

# --- Global Singleton Instance ---
# This is the "batteries-included" setup.
# It automatically discovers the project root and sets up a file system loader.
_project_root = _find_project_root()
_default_loader = FileSystemLoader(roots=[_project_root])
nexus = OverlayNexus(loaders=[_default_loader])
# ---------------------------------
~~~~~

### 下一步建议
我们已经完成了核心重构。接下来应该运行现有的测试套件（特别是 `test_assembly.py`），验证新的 Loader 逻辑是否正确处理了多根目录、覆盖和数据展平。此外，可以考虑添加针对 `put` 操作的新测试，验证精确写入和膨胀逻辑的正确性。
