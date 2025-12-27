简要回答：
你说得完全正确！`nexus.get()` 远比 `needle.get()` 更具描述性，也解决了 `needle` 和 `L` 在语义上的重叠问题。“针 (`L`)” 刺入 “中枢 (`nexus`)” 来获取信息，这个比喻非常清晰。

我们采纳你的命名建议。全局实例将命名为 `nexus`。

现在，我们开始执行重构的最后一步：**Phase 4: 电池组装**。

## [WIP] feat: 创建 pyneedle 包并组装全局 nexus 实例

### 用户需求
创建顶层的 `pyneedle` 包作为“电池组”，它将 `spec`, `pointer`, 和 `nexus` 组件组装成一个开箱即用的产品。这个包必须：
1.  实现一个 `FileSystemLoader`，能够扫描磁盘上的 `needle/` 和 `.stitcher/needle/` 目录。
2.  实例化所有组件，并导出一个名为 `nexus` 的全局单例运行时。
3.  同时导出 `L` 单例，作为用户的主要 API 入口。

### 评论
这是整个重构工作的收官之作。通过这个顶层包，我们将复杂的内部架构（协议、指针代数、层叠引擎）封装成一个极其简单和强大的 API：`from needle import L, nexus`。`FileSystemLoader` 是连接抽象内核与物理世界的关键桥梁，它使 `Nexus` 真正具备了从项目中加载资源的能力。

### 目标
1.  创建 `packages/pyneedle` 的包结构和 `pyproject.toml`，并依赖所有其他 `pyneedle-*` 包。
2.  实现 `FileSystemLoader`，它能够递归扫描目录，并使用可插拔的 `FileHandler` 来解析不同格式的文件（首先实现 `JsonHandler`）。
3.  在 `pyneedle` 的 `__init__.py` 中，实例化 `FileSystemLoader` 和 `OverlayNexus`，并将最终的实例导出为 `nexus`。
4.  更新根 `pyproject.toml`，将新包的路径加入 `pythonpath`。

### 基本原理
*   **组装根 (Composition Root)**: `pyneedle` 包是整个生态的“组装根”。它负责创建所有依赖的实例，并将它们连接起来。这种模式将配置和实例化逻辑集中在一个地方，使得其他所有包都可以保持纯粹和解耦。
*   **自动发现**: `FileSystemLoader` 将内置向上查找项目根目录（寻找 `pyproject.toml` 或 `.git`）的逻辑，这使得 `nexus` 实例在导入时就能自动定位到正确的项目，无需用户手动配置。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #concept/state #scope/api
#task/domain/runtime #task/object/pyneedle #task/action/assemble
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 初始化包结构和配置
创建目录和 `pyproject.toml`，依赖于所有其他核心 `pyneedle` 包。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/pyneedle/src/needle/loaders
~~~~~

~~~~~act
write_file
packages/pyneedle/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyneedle"
version = "0.1.0"
description = "Batteries-included distribution of the PyNeedle runtime."
requires-python = ">=3.10"
dependencies = [
    "pyneedle-spec",
    "pyneedle-pointer",
    "pyneedle-nexus",
]

[tool.hatch.build.targets.wheel]
packages = ["src/needle"]

[tool.uv.sources]
pyneedle-spec = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-nexus = { workspace = true }
~~~~~

#### Acts 2: 实现文件处理器和文件系统加载器
这将是 `Nexus` 连接到物理文件的桥梁。

~~~~~act
write_file
packages/pyneedle/src/needle/loaders/protocols.py
~~~~~
~~~~~python
from typing import Any, Dict, Protocol
from pathlib import Path


class FileHandlerProtocol(Protocol):
    """
    Protocol for file handlers that can parse specific formats like JSON, YAML, etc.
    """
    def match(self, path: Path) -> bool:
        """Returns True if this handler can process the given file path."""
        ...

    def load(self, path: Path) -> Dict[str, Any]:
        """Parses the file and returns its content as a dictionary."""
        ...
~~~~~

~~~~~act
write_file
packages/pyneedle/src/needle/loaders/json_handler.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Any, Dict
from .protocols import FileHandlerProtocol


class JsonHandler(FileHandlerProtocol):
    """Standard handler for .json files."""
    def match(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def load(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
~~~~~

~~~~~act
write_file
packages/pyneedle/src/needle/loaders/fs_loader.py
~~~~~
~~~~~python
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from needle.spec import ResourceLoaderProtocol
from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler


class FileSystemLoader(ResourceLoaderProtocol):
    """
    A resource loader that scans the file system for resource files.

    It searches for project roots and then looks for standard resource
    directories (`needle/` and `.stitcher/needle/`).
    """
    def __init__(self, roots: Optional[List[Path]] = None, handlers: Optional[List[FileHandlerProtocol]] = None):
        self.handlers = handlers or [JsonHandler()]
        self.roots = roots or [self._find_project_root()]

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        # Stop at filesystem root
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").is_file() or (current_dir / ".git").is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def add_root(self, path: Path):
        """Prepends a new search root, giving it highest priority."""
        if path not in self.roots:
            self.roots.insert(0, path)

    def load(self, lang: str) -> Dict[str, Any]:
        """
        Scans all roots for a given language and merges the found resources.
        Later roots in the list override earlier ones.
        """
        merged_registry: Dict[str, str] = {}
        
        for root in self.roots:
            # Path Option 1: .stitcher/needle/<lang> (for project-specific overrides)
            hidden_path = root / ".stitcher" / "needle" / lang
            if hidden_path.is_dir():
                merged_registry.update(self._load_directory(hidden_path))

            # Path Option 2: needle/<lang> (for packaged assets)
            asset_path = root / "needle" / lang
            if asset_path.is_dir():
                merged_registry.update(self._load_directory(asset_path))

        return merged_registry

    def _load_directory(self, root_path: Path) -> Dict[str, str]:
        """Recursively scans a directory and loads all supported files."""
        registry: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        content = handler.load(file_path)
                        # Ensure all values are strings for FQN registry
                        for key, value in content.items():
                            registry[str(key)] = str(value)
                        break # Stop after first matching handler
        return registry
~~~~~

#### Acts 3: 组装并导出全局 `nexus` 实例
这是最终用户将直接交互的 API。

~~~~~act
write_file
packages/pyneedle/src/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus
from .loaders.fs_loader import FileSystemLoader

# --- Global Singleton Instance ---
# This is the "batteries-included" setup.
# It automatically discovers the project root and sets up a file system loader.
_default_loader = FileSystemLoader()
nexus = OverlayNexus(loaders=[_default_loader])
# ---------------------------------

# Make the loader accessible for advanced use cases (e.g., adding asset paths)
# Example: from needle import _default_loader
#          _default_loader.add_root(my_assets_path)
#          nexus.reload()

__all__ = ["L", "nexus", "SemanticPointer", "PointerSet", "_default_loader"]
~~~~~

#### Acts 4: 更新根 `pyproject.toml`
将新包的路径加入 `pytest` 的 `pythonpath`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
pythonpath = [
    "packages/stitcher-spec/src", 
    "packages/stitcher-common/src", 
    "packages/stitcher-scanner/src", 
    "packages/stitcher-io/src", 
    "packages/stitcher-config/src", 
    "packages/stitcher-application/src", 
    "packages/stitcher-cli/src", 
    "packages/stitcher-needle/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src"
]
~~~~~
~~~~~toml.new
pythonpath = [
    "packages/stitcher-spec/src", 
    "packages/stitcher-common/src", 
    "packages/stitcher-scanner/src", 
    "packages/stitcher-io/src", 
    "packages/stitcher-config/src", 
    "packages/stitcher-application/src", 
    "packages/stitcher-cli/src", 
    "packages/stitcher-needle/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src"
]
~~~~~

### 下一步建议
我们已经成功地将 `Needle` 重构为一个高度模块化、协议优先、可测试的生态系统，并提供了一个简单易用的顶层 API。

下一步的关键任务是：
1.  **迁移消费者**: 逐一更新 `stitcher-cli`, `stitcher-application` 等包，将它们对 `stitcher-needle` 的依赖切换到新的 `pyneedle` 包。
2.  **删除旧包**: 在所有消费者迁移完毕后，安全地删除 `packages/stitcher-needle`。
