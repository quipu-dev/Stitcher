## [WIP] feat: 实现基于接口的资源加载器与 Needle 运行时

### 用户需求
实现 `stitcher-needle` 的资源加载与运行时逻辑。必须采用“接口先行”的设计模式，定义抽象的文件处理接口，以支持未来扩展（如 YAML 支持）。同时实现默认的 JSON 处理器、SST 目录扫描逻辑以及具有优雅降级能力的运行时核心。

### 评论
采用接口模式是极具前瞻性的决策。它不仅解耦了具体的解析逻辑，还允许我们在保持核心包“零依赖”的同时，通过可选扩展（Extras）引入重型依赖（如 PyYAML）。SST (物理分片语义分类法) 的扫描逻辑将确保文件系统结构能正确映射为内存中的 FQN (全限定名) 字典。

### 目标
1.  定义 `FileHandler` 协议，规范 `match` 和 `load` 行为。
2.  实现内置的 `JsonHandler`。
3.  实现 `Loader`，负责扫描 `stitcher/needle/<lang>` 目录，利用 Handler 加载文件，并将嵌套字典展平为 FQN 键值对。
4.  实现 `Needle` 运行时类，封装加载逻辑并提供带有三级降级策略的 `get` 方法。
5.  在包入口导出 `Needle` 实例，并编写综合测试。

### 基本原理
*   **接口隔离**: 使用 `typing.Protocol` 定义接口，无需继承即可实现多态。
*   **展平逻辑**: 为了 O(1) 的查找速度，我们在加载阶段将嵌套的 JSON 结构（如 `{"a": {"b": "val"}}`）展平为一维字典（`{"a.b": "val"}`）。
*   **优雅降级**: 运行时的健壮性来自于“身份即内容”的哲学。当所有查找失败时，返回 Key 本身保证了程序永远不会因为缺翻译而崩溃。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/needle-loader #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 定义文件处理接口与 JSON 实现

首先定义 `FileHandler` 协议，并实现标准的 JSON 处理器。

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/interfaces.py
~~~~~
~~~~~python
from typing import Any, Dict, Protocol
from pathlib import Path


class FileHandler(Protocol):
    """
    Protocol for file handlers that can parse specific formats.
    """

    def match(self, path: Path) -> bool:
        """Returns True if this handler can process the given file."""
        ...

    def load(self, path: Path) -> Dict[str, Any]:
        """Parses the file and returns a dictionary."""
        ...
~~~~~

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/handlers.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Any, Dict
from .interfaces import FileHandler


class JsonHandler:
    """Standard handler for JSON files."""

    def match(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def load(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
~~~~~

#### Acts 2: 实现 Loader (SST 扫描与展平)

Loader 负责遍历目录，调用匹配的 Handler，并将结果展平。

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/loader.py
~~~~~
~~~~~python
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .interfaces import FileHandler
from .handlers import JsonHandler


def _flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "."
) -> Dict[str, str]:
    """
    Recursively flattens a nested dictionary into a single-level dictionary
    with dot-separated keys.
    """
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v)))
    return dict(items)


class Loader:
    def __init__(self, handlers: Optional[List[FileHandler]] = None):
        # Default to JsonHandler if none provided
        self.handlers = handlers or [JsonHandler()]

    def _load_file(self, path: Path) -> Dict[str, Any]:
        for handler in self.handlers:
            if handler.match(path):
                try:
                    return handler.load(path)
                except Exception:
                    # In a robust system we might log this, but Needle aims to be silent/resilient
                    return {}
        return {}

    def load_directory(self, root_path: Path) -> Dict[str, str]:
        """
        Scans a directory following Stitcher SST rules and returns a flattened registry.
        
        SST Structure:
        root/
          __init__.json  -> keys mapped as "key"
          category/
            __init__.json -> keys mapped as "category.key"
            file.json     -> keys mapped as "category.file.key"
        """
        registry: Dict[str, str] = {}

        if not root_path.exists():
            return registry

        # Walk the directory
        for dirpath, _, filenames in os.walk(root_path):
            dir_path_obj = Path(dirpath)
            
            # Calculate the relative path parts to determine namespace
            # e.g., /app/stitcher/needle/en/cli/ui -> parts=("cli", "ui")
            try:
                rel_parts = dir_path_obj.relative_to(root_path).parts
            except ValueError:
                continue

            for filename in filenames:
                file_path = dir_path_obj / filename
                
                # Load content
                content = self._load_file(file_path)
                if not content:
                    continue

                # Determine the prefix based on file position
                # 1. Root __init__.json -> prefix=""
                if not rel_parts and filename.startswith("__init__"):
                    prefix = ""
                # 2. Subdir __init__.json -> prefix="category."
                elif rel_parts and filename.startswith("__init__"):
                    prefix = ".".join(rel_parts)
                # 3. Regular file -> prefix="category.filename." (without suffix)
                else:
                    file_stem = file_path.stem
                    # Combine directory parts and filename
                    prefix_parts = rel_parts + (file_stem,)
                    prefix = ".".join(prefix_parts)

                # Flatten and merge
                flattened = _flatten_dict(content, parent_key=prefix)
                registry.update(flattened)

        return registry
~~~~~

#### Acts 3: 实现 Needle 运行时

集成 Loader，实现三级降级查找。

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/runtime.py
~~~~~
~~~~~python
import os
from pathlib import Path
from typing import Dict, Optional, Union

from .loader import Loader
from .pointer import SemanticPointer


class Needle:
    """
    The runtime kernel for semantic addressing.
    """

    def __init__(self, root_path: Optional[Path] = None, default_lang: str = "en"):
        self.root_path = root_path or self._find_project_root()
        self.default_lang = default_lang
        self._registry: Dict[str, Dict[str, str]] = {}  # lang -> {fqn: value}
        self._loader = Loader()
        self._loaded_langs: set = set()

    def _find_project_root(self) -> Path:
        """
        Simple heuristic to find where 'stitcher' directory might be.
        Defaults to current working directory.
        """
        return Path.cwd()

    def _ensure_lang_loaded(self, lang: str):
        if lang in self._loaded_langs:
            return

        # SST path: project_root/stitcher/needle/<lang>/
        needle_dir = self.root_path / "stitcher" / "needle" / lang
        
        # Load and cache
        self._registry[lang] = self._loader.load_directory(needle_dir)
        self._loaded_langs.add(lang)

    def get(
        self, 
        pointer: Union[SemanticPointer, str], 
        lang: Optional[str] = None
    ) -> str:
        """
        Resolves a semantic pointer to a string value with graceful fallback.
        
        Lookup Order:
        1. Target Language
        2. Default Language (en)
        3. Identity (the key itself)
        """
        key = str(pointer)
        target_lang = lang or os.getenv("STITCHER_LANG", self.default_lang)

        # 1. Try target language
        self._ensure_lang_loaded(target_lang)
        val = self._registry.get(target_lang, {}).get(key)
        if val is not None:
            return val

        # 2. Try default language (if different)
        if target_lang != self.default_lang:
            self._ensure_lang_loaded(self.default_lang)
            val = self._registry.get(self.default_lang, {}).get(key)
            if val is not None:
                return val

        # 3. Fallback to Identity
        return key

# Global Runtime Instance
needle = Needle()
~~~~~

#### Acts 4: 导出与测试

更新 `__init__.py` 导出新组件，并编写集成测试。

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .pointer import L, SemanticPointer
from .runtime import needle, Needle
from .loader import Loader
from .interfaces import FileHandler

__all__ = ["L", "SemanticPointer", "needle", "Needle", "Loader", "FileHandler"]
~~~~~

~~~~~act
write_file
packages/stitcher-needle/tests/test_runtime.py
~~~~~
~~~~~python
import json
from pathlib import Path
from stitcher.needle import Needle, L

def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup SST structure
    root = tmp_path
    needle_dir = root / "stitcher" / "needle"
    
    # English (Default)
    en_dir = needle_dir / "en"
    en_dir.mkdir(parents=True)
    
    # en/cli.json
    (en_dir / "cli.json").write_text(json.dumps({
        "hello": "Hello World",
        "only_en": "I am English"
    }))
    
    # en/auth/login.json
    (en_dir / "auth").mkdir()
    (en_dir / "auth" / "login.json").write_text(json.dumps({
        "fail": "Login Failed"
    }))

    # Chinese (Target)
    zh_dir = needle_dir / "zh"
    zh_dir.mkdir(parents=True)
    
    # zh/cli.json
    (zh_dir / "cli.json").write_text(json.dumps({
        "hello": "你好世界"
    }))

    # 2. Initialize Runtime
    rt = Needle(root_path=root, default_lang="en")

    # 3. Test: Target Language Hit
    # L.cli.hello -> "你好世界" (in zh)
    assert rt.get(L.cli.hello, lang="zh") == "你好世界"

    # 4. Test: Fallback to Default Language
    # L.cli.only_en -> "I am English" (missing in zh, fallback to en)
    assert rt.get(L.cli.only_en, lang="zh") == "I am English"

    # 5. Test: Namespace Flattening
    # L.auth.login.fail -> "Login Failed"
    assert rt.get(L.auth.login.fail) == "Login Failed"

    # 6. Test: Ultimate Identity Fallback
    # L.unknown.key -> "unknown.key"
    assert rt.get(L.unknown.key) == "unknown.key"
~~~~~
