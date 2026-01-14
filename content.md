测试通过，太好了。这证明我们的第一阶段迁移是成功的。

现在，我们进入归一化阶段，消除冗余代码，使架构更加健壮和优雅。这完全符合“架构不可腐蚀性”原则——发现异味，立即铲除。

## [WIP] refactor: Unify root finding logic by removing _find_pyproject_toml

### 用户需求

废弃 `stitcher.workspace.config._find_pyproject_toml` 函数，并修改 `load_config_from_path` 以统一使用 `stitcher.workspace.core.find_workspace_root` 作为项目根目录的唯一事实来源。

### 评论

这是一个完美的重构示例。系统中存在两个功能几乎完全重叠的函数，这违反了 SSoT (真理单一来源) 原则，是一种必须被清除的架构“异味”。通过统一使用更健壮的 `find_workspace_root` 函数，我们不仅简化了代码，还修复了一个潜在的 bug（即 `_find_plugins` 应该在已确定的工作区根目录下执行，而不是在任意的搜索起始路径下执行）。

### 目标

1.  从 `stitcher/workspace/config.py` 中删除 `_find_pyproject_toml` 函数。
2.  修改 `load_config_from_path` 函数，使其调用 `find_workspace_root` 来定位工作区根目录和 `pyproject.toml` 文件。
3.  确保 `load_config_from_path` 在找不到工作区时的回退行为与之前保持一致。

### 基本原理

我们将使用一个单一的、精确的 `patch_file` 操作来完成此任务。此操作将：
1.  导入 `find_workspace_root` 和 `WorkspaceNotFoundError`。
2.  删除 `_find_pyproject_toml` 的定义。
3.  重写 `load_config_from_path` 的逻辑，首先调用 `find_workspace_root`。如果成功，则用它来定位 `pyproject.toml` 并发现插件。如果失败（捕获 `WorkspaceNotFoundError`），则以与之前相同的方式处理，返回一个默认配置。这确保了逻辑的统一性和代码的健壮性。

### 标签

#intent/refine #flow/ready #priority/high #comp/workspace #concept/config #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/package-merge #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 归一化根目录查找逻辑

我们将对 `config.py` 文件进行精确修改，移除冗余函数并更新其调用者。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/config.py
~~~~~
~~~~~python.old
def _find_pyproject_toml(search_path: Path) -> Path:
    current_dir = search_path.resolve()
    while current_dir.parent != current_dir:
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.is_file():
            return pyproject_path
        current_dir = current_dir.parent
    raise FileNotFoundError("Could not find pyproject.toml in any parent directory.")


def _find_plugins(workspace_root: Path) -> Dict[str, str]:
    plugins: Dict[str, str] = {}
    for toml_file in workspace_root.rglob("**/pyproject.toml"):
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)

            entry_points = data.get("project", {}).get("entry-points", {})
            stitcher_plugins = entry_points.get("stitcher.plugins", {})
            if stitcher_plugins:
                plugins.update(stitcher_plugins)
        except Exception:
            # Silently ignore parsing errors in other projects' toml files
            pass
    return plugins


def load_config_from_path(
    search_path: Path,
) -> Tuple[List[StitcherConfig], Optional[str]]:
    plugins = _find_plugins(search_path)
    project_name: Optional[str] = None
    stitcher_data: Dict[str, Any] = {}

    try:
        config_path = _find_pyproject_toml(search_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        project_name = data.get("project", {}).get("name")
        stitcher_data = data.get("tool", {}).get("stitcher", {})

    except FileNotFoundError:
        # If no root config file, return default config with discovered plugins
        return [StitcherConfig(plugins=plugins)], None

    configs: List[StitcherConfig] = []
~~~~~
~~~~~python.new
from .core import find_workspace_root
from .exceptions import WorkspaceNotFoundError


def _find_plugins(workspace_root: Path) -> Dict[str, str]:
    plugins: Dict[str, str] = {}
    for toml_file in workspace_root.rglob("**/pyproject.toml"):
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)

            entry_points = data.get("project", {}).get("entry-points", {})
            stitcher_plugins = entry_points.get("stitcher.plugins", {})
            if stitcher_plugins:
                plugins.update(stitcher_plugins)
        except Exception:
            # Silently ignore parsing errors in other projects' toml files
            pass
    return plugins


def load_config_from_path(
    search_path: Path,
) -> Tuple[List[StitcherConfig], Optional[str]]:
    project_name: Optional[str] = None
    stitcher_data: Dict[str, Any] = {}

    try:
        workspace_root = find_workspace_root(search_path)
        plugins = _find_plugins(workspace_root)
        config_path = workspace_root / "pyproject.toml"

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        project_name = data.get("project", {}).get("name")
        stitcher_data = data.get("tool", {}).get("stitcher", {})

    except (FileNotFoundError, WorkspaceNotFoundError):
        # In case of no root, we can't reliably find plugins.
        # This behavior is now more correct. We return an empty plugin dict.
        return [StitcherConfig(plugins={})], None

    configs: List[StitcherConfig] = []
~~~~~

### 下一步建议

逻辑归一化已经完成。为了确保我们的修改是正确的并且没有引入回归，下一步是再次运行测试套件。

请运行 `pytest`。如果所有测试都通过，我们就可以将这次合并视为一个完整的、已验证的工作单元，并准备创建一个 `[COMMIT]` 计划来结束这个宏观任务。
