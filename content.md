## [WIP] feat: Relocate locales to root and implement robust discovery

### 用户需求
将 `locales` 数据目录从 `stitcher-common` 包内移动到项目根目录下的 `stitcher/needle/` 结构中，以实现数据与代码的解耦和高内聚。同时，重构 `Needle` 运行时，使其能够通过向上遍历文件系统来自动发现项目根目录。

### 评论
这是一个关键的架构修正，它将 `stitcher` 的配置和数据提升为项目的一等公民，而不是特定Python包的实现细节。通过实现健壮的根目录发现机制，`stitcher-needle` 变得更加独立和可移植，完全符合其作为微内核的设计哲学。

### 目标
1.  **重构 `Needle` 运行时**:
    *   实现一个 `_find_project_root` 方法，该方法通过向上查找 `pyproject.toml` 或 `.git` 来确定项目根目录。
    *   更新资源加载路径，使其指向新位置：`<root>/stitcher/needle/<lang>/`。
2.  **迁移物理文件**:
    *   创建顶级的 `stitcher/` 目录。
    *   将 `packages/stitcher-common/src/stitcher/common/locales/` 的内容移动到 `stitcher/needle/`。
3.  **修复单元测试**: 更新 `test_runtime.py` 以匹配新的文件系统结构和根目录发现逻辑。

### 基本原理
新的根目录发现逻辑将使 `Needle` 的行为在任何子目录中运行时都保持一致和可预测。将数据文件移出 `packages/` 目录，明确了它们作为项目级资产的地位，而不是某个可安装包的一部分。测试的修复将确保我们对这个新的、更健壮的行为有充分的信心。

### 标签
#intent/architect #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/sst-migration #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 实现健壮的项目根目录发现

我们首先更新 `Needle` 运行时，赋予它自动发现项目根目录的能力。

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

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        """
        Finds the project root by searching upwards for common markers.
        Search priority: pyproject.toml -> .git
        """
        current_dir = (start_dir or Path.cwd()).resolve()
        while current_dir.parent != current_dir:  # Stop at filesystem root
            # Priority 1: pyproject.toml (strongest Python project signal)
            if (current_dir / "pyproject.toml").is_file():
                return current_dir
            # Priority 2: .git directory (strong version control signal)
            if (current_dir / ".git").is_dir():
                return current_dir
            current_dir = current_dir.parent
        # Fallback to the starting directory if no markers are found
        return start_dir or Path.cwd()

    def _ensure_lang_loaded(self, lang: str):
        if lang in self._loaded_langs:
            return

        # NEW SST path: <project_root>/stitcher/needle/<lang>/
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

#### Acts 2: 迁移 `locales` 目录到项目根

现在，我们物理上移动这些文件，并清理旧的目录结构。

~~~~~act
run_command
~~~~~
~~~~~
# Create the new root structure
mkdir -p stitcher/needle/en/generate
mkdir -p stitcher/needle/en/error
mkdir -p stitcher/needle/en/cli
mkdir -p stitcher/needle/en/warning

# Move files
mv packages/stitcher-common/src/stitcher/common/locales/en/generate/main.json stitcher/needle/en/generate/main.json
mv packages/stitcher-common/src/stitcher/common/locales/en/error/main.json stitcher/needle/en/error/main.json
mv packages/stitcher-common/src/stitcher/common/locales/en/cli/command.json stitcher/needle/en/cli/command.json
mv packages/stitcher-common/src/stitcher/common/locales/en/warning/main.json stitcher/needle/en/warning/main.json

# Clean up old empty directories
rm -rf packages/stitcher-common/src/stitcher/common/locales
~~~~~

#### Acts 3: 修复单元测试以匹配新结构

最后，我们再次更新测试用例，以反映最终的、正确的目录结构。

~~~~~act
patch_file
packages/stitcher-needle/tests/test_runtime.py
~~~~~
~~~~~python.old
def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup SST structure according to the NEW specification
    root = tmp_path
    locales_dir = root / "locales"
    
    # English (Default)
    en_dir = locales_dir / "en"
    (en_dir / "cli").mkdir(parents=True)
    (en_dir / "auth").mkdir()

    (en_dir / "cli" / "main.json").write_text(json.dumps({
        "cli.hello": "Hello World",
        "cli.only_en": "I am English"
    }))
    
    (en_dir / "auth" / "login.json").write_text(json.dumps({
        "auth.login.fail": "Login Failed"
    }))

    # Chinese (Target)
    zh_dir = locales_dir / "zh"
    (zh_dir / "cli").mkdir(parents=True)
    
    (zh_dir / "cli" / "main.json").write_text(json.dumps({
        "cli.hello": "你好世界"
    }))

    # 2. Initialize Runtime
    # The runtime will look for a `locales` dir inside the provided root_path
    rt = Needle(root_path=root, default_lang="en")

    # 3. Test: Target Language Hit
~~~~~
~~~~~python.new
def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup the FINAL SST structure inside the mock project root
    project_root = tmp_path
    needle_dir = project_root / "stitcher" / "needle"
    
    # English (Default)
    en_dir = needle_dir / "en"
    (en_dir / "cli").mkdir(parents=True)
    (en_dir / "auth").mkdir()

    (en_dir / "cli" / "main.json").write_text(json.dumps({
        "cli.hello": "Hello World",
        "cli.only_en": "I am English"
    }))
    
    (en_dir / "auth" / "login.json").write_text(json.dumps({
        "auth.login.fail": "Login Failed"
    }))

    # Chinese (Target)
    zh_dir = needle_dir / "zh"
    (zh_dir / "cli").mkdir(parents=True)
    
    (zh_dir / "cli" / "main.json").write_text(json.dumps({
        "cli.hello": "你好世界"
    }))

    # 2. Initialize Runtime
    # The runtime should now automatically find the `stitcher` dir within the root_path
    rt = Needle(root_path=project_root, default_lang="en")

    # 3. Test: Target Language Hit
~~~~~
