明白，之前的计划在处理 `L` 导入时存在矛盾，且没有彻底解决 `Needle` 全局单例的暴露问题。

核心修复思路：
1.  **修正 `stitcher-common`**: 声明对 `needle` 的物理依赖，并将 `needle` 运行时单例作为 `common` 的核心导出。
2.  **增强 `Needle` 运行时**: 实现 `root_path` 的**懒加载**。这样仅导入模块时不会触发昂贵的磁盘搜索，只有在真正需要加载翻译资源时才进行。
3.  **彻底清理 `stitcher-cli`**: 移除画蛇添足的 `render_to_string_patch`。`MessageBus` 已经正确实现了此功能。
4.  **保留 `L`**: 因为 `L` 用于构造语义路径（如 `L.strip.run.confirm`），这是指令参数所必需的。

---

## [WIP] fix: 修复 CLI 中的抽象泄漏并实现 Needle 懒加载单例

### 错误分析
错误 `TypeError: 'SemanticPointer' object is not callable` 发生在 `L.needle.get(msg_id)` 调用处。
- **原因 1**: `L` 是一个 `SemanticPointer`。访问 `L.needle` 只是得到了一个路径为 `"needle"` 的新指针，它是不可调用的。
- **原因 2**: 开发者误将 `L`（地址构造器）当成了 `needle`（运行时执行器）。
- **原因 3**: `render_to_string_patch` 试图手动实现一个 `MessageBus` 已经包含的功能，造成了严重的抽象泄漏。

### 目标
1.  将 `needle` 运行时单例收纳进 `stitcher-common`。
2.  修改 `Needle` 类，使 `root_path` 的自动发现逻辑变为延迟执行。
3.  移除 `stitcher-cli` 中所有错误的补丁逻辑。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/cli #comp/common #comp/needle #scope/core #ai/refine #task/domain/messaging #task/object/needle-singleton #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正 `stitcher-common` 依赖与统一单例导出

确保 `common` 包是系统的“中枢”，通过它访问 `bus` 和 `needle`。

~~~~~act
patch_file
packages/stitcher-common/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = []

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-needle",
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make core singletons easily accessible
from .messaging.bus import bus

__all__ = ["bus"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make core singletons easily accessible
from stitcher.needle import needle
from .messaging.bus import bus

__all__ = ["bus", "needle"]
~~~~~

#### Acts 2: 优化 `Needle` 为懒加载模式

通过将 `root_path` 改为 `property`，我们确保了只有在真正进行 I/O 操作时才去寻找项目根目录。

~~~~~act
patch_file
packages/stitcher-needle/src/stitcher/needle/runtime.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
class Needle:
    """
    The runtime kernel for semantic addressing.
    """

    def __init__(self, root_path: Optional[Path] = None, default_lang: str = "en"):
        self._explicit_root = root_path
        self._discovered_root: Optional[Path] = None
        self.default_lang = default_lang
        self._registry: Dict[str, Dict[str, str]] = {}  # lang -> {fqn: value}
        self._loader = Loader()
        self._loaded_langs: set = set()

    @property
    def root_path(self) -> Path:
        if self._explicit_root:
            return self._explicit_root
        if not self._discovered_root:
            self._discovered_root = self._find_project_root()
        return self._discovered_root

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
~~~~~

#### Acts 3: 彻底清理 CLI 中的错误补丁

移除 `main.py` 中多余的逻辑，恢复 `MessageBus` 的原生调用。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_eject()


# Helper needed for typer.confirm, as it prints directly
# We need to render message to a string first
def render_to_string_patch(self, msg_id, **kwargs):
    template = L.needle.get(msg_id)
    return template.format(**kwargs)


bus.render_to_string = render_to_string_patch.__get__(bus)


if __name__ == "__main__":
~~~~~
~~~~~python.new
@app.command()
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_eject()


if __name__ == "__main__":
~~~~~

### 下一步建议
- **执行测试**: 运行 `stitcher strip` 命令。现在它将调用原生的 `MessageBus.render_to_string`，而该方法内部通过 `needle.get()` 正确解析 `L.strip.run.confirm` 指针。
- **性能确认**: 通过日志观察，在不调用消息指令的情况下，是否还存在 `_find_project_root` 的磁盘扫描行为。
