Excellent. Adopting the `.stitcher` convention is a solid architectural decision.

Here is the plan to implement this change across the codebase.

## [WIP] refactor: Rename data directory to .stitcher to prevent namespace shadowing

### 用户需求
将项目根目录下的 `stitcher` 数据目录重命名为 `.stitcher`，以彻底解决与 `stitcher` 命名空间包可能产生的导入冲突（遮蔽效应）。

### 评论
这是一个至关重要的架构改进。采用 `.stitcher` 命名约定不仅完全消除了导入歧义的风险，还使我们的项目遵循了 `git`, `vscode`, `pytest` 等现代开发工具的既定标准。这使得项目结构更加健壮、直观，并为未来工具链的扩展奠定了坚实的基础。

### 目标
1.  更新 `Needle` 运行时，使其在项目根目录下查找 `.stitcher/needle/<lang>/` 路径。
2.  将物理的 `stitcher/` 数据目录重命名为 `.stitcher/`。
3.  更新单元测试，使其在模拟环境中创建和使用 `.stitcher/` 目录。

### 基本原理
我们将首先修改代码（运行时和测试），使其预期新的 `.stitcher` 目录。然后，我们执行一个简单的 `mv` 命令来重命名物理目录。这个“代码先行”的顺序确保了在文件系统变更后，系统立即处于一致和可测试的状态。

### 标签
#intent/refine #intent/architect #flow/ready #priority/high #comp/runtime #scope/core #scope/dx #ai/instruct #task/domain/runtime #task/object/workspace-convention #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 更新 Needle 运行时以查找 `.stitcher`

我们修改 `_ensure_lang_loaded` 方法，将硬编码的路径从 `"stitcher"` 更新为 `".stitcher"`。

~~~~~act
patch_file
packages/stitcher-needle/src/stitcher/needle/runtime.py
~~~~~
~~~~~python.old
    def _ensure_lang_loaded(self, lang: str):
        if lang in self._loaded_langs:
            return

        # NEW SST path: <project_root>/stitcher/needle/<lang>/
        needle_dir = self.root_path / "stitcher" / "needle" / lang
        
        # Load and cache
        self._registry[lang] = self._loader.load_directory(needle_dir)
~~~~~
~~~~~python.new
    def _ensure_lang_loaded(self, lang: str):
        if lang in self._loaded_langs:
            return

        # Final SST path: <project_root>/.stitcher/needle/<lang>/
        needle_dir = self.root_path / ".stitcher" / "needle" / lang
        
        # Load and cache
        self._registry[lang] = self._loader.load_directory(needle_dir)
~~~~~

#### Acts 2: 更新单元测试以使用 `.stitcher`

同样，我们更新测试用例，使其在 `tmp_path` 下创建 `.stitcher` 目录进行测试。

~~~~~act
patch_file
packages/stitcher-needle/tests/test_runtime.py
~~~~~
~~~~~python.old
def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup the FINAL SST structure inside the mock project root
    project_root = tmp_path
    needle_dir = project_root / "stitcher" / "needle"
    
    # English (Default)
    en_dir = needle_dir / "en"
~~~~~
~~~~~python.new
def test_needle_loading_and_fallback(tmp_path: Path):
    # 1. Setup the FINAL SST structure inside the mock project root
    project_root = tmp_path
    needle_dir = project_root / ".stitcher" / "needle"
    
    # English (Default)
    en_dir = needle_dir / "en"
~~~~~

#### Acts 3: 重命名物理目录

最后，我们执行文件系统操作，将现有的 `stitcher` 数据目录重命名为 `.stitcher`。

~~~~~act
run_command
~~~~~
~~~~~
mv stitcher .stitcher
~~~~~
