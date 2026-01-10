我将立即生成一个计划来实施这一战略。

## [WIP] refactor: Restore Workspace self-discovery capability

### 用户需求

根据战略分析，重构 `Workspace` 类，使其构造函数中的 `config` 参数变为可选。如果 `config` 未被提供，`Workspace` 必须能够回退到其原始的、基于文件系统扫描的自发现模式。

### 评论

这次重构是对先前架构决策的一次重要修正。它将使 `Workspace` 类的设计更加健壮和灵活，既能满足新功能的需求，又保持了对现有测试和用法的兼容性。这是一个符合“高内聚、低耦合”设计原则的典范，能够显著提升系统的长期可维护性。

### 目标

1.  **恢复旧逻辑**: 将 `_discover_packages`, `_find_code_dirs` 等自发现相关的方法添加回 `packages/stitcher-refactor/src/stitcher/refactor/workspace.py` 中的 `Workspace` 类。
2.  **更新构造函数**: 修改 `Workspace.__init__` 的签名，使 `config` 参数可选。
3.  **实现双模初始化**: 在 `__init__` 中添加 `if/else` 逻辑，根据 `config` 是否存在来决定调用 `_build_from_config` 还是 `_discover_packages`。

### 基本原理

我们将使用 `write_file` 对 `workspace.py` 进行一次完整的重写。新的实现将包含两套逻辑：
1.  **`_discover_packages` 及其辅助方法**: 这是从旧版本代码中恢复的逻辑，它通过遍历目录和解析 `pyproject.toml` 来构建工作区。
2.  **`_build_from_config` 方法**: 这是我们近期添加的逻辑，它直接从 `StitcherConfig` 对象中读取路径。

`__init__` 方法将成为一个调度器，根据 `config` 参数是否为 `None` 来决定执行哪套逻辑。这使得两种行为模式可以在同一个类中共存，完美地解决了我们当前面临的问题。

### 标签

#intent/refine #flow/ready #priority/critical #comp/refactor #concept/config #scope/core #ai/instruct #task/domain/architecture #task/object/config-unification #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重写 Workspace 以支持双模初始化

我们将用一个包含了两种初始化逻辑的新版本来覆盖当前的 `workspace.py`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from stitcher.config import StitcherConfig

log = logging.getLogger(__name__)


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
        """Builds workspace view from a StitcherConfig object."""
        if not self.config:
            return

        all_paths_str = self.config.scan_paths + self.config.peripheral_paths
        for path_str in all_paths_str:
            code_dir = self.root_path / path_str
            if code_dir.is_dir():
                import_names = self._get_top_level_importables(code_dir)
                for import_name in import_names:
                    self.import_to_source_dirs[import_name].add(code_dir)

    def _discover_packages(self) -> None:
        """(Default) Builds workspace view by scanning for pyproject.toml files."""
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                with pyproject_path.open("rb") as f:
                    tomllib.load(f)

                pkg_root = pyproject_path.parent
                code_dirs = self._find_code_dirs(pkg_root)

                for code_dir in code_dirs:
                    import_names = self._get_top_level_importables(code_dir)
                    for import_name in import_names:
                        self.import_to_source_dirs[import_name].add(code_dir)

            except Exception as e:
                log.warning(f"Could not process {pyproject_path}: {e}")

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        if not src_path.is_dir():
            return []

        for item in src_path.iterdir():
            if (
                item.is_dir()
                and item.name.isidentifier()
                and item.name != "__pycache__"
            ):
                names.add(item.name)
            elif (
                item.is_file()
                and item.name.endswith(".py")
                and item.stem.isidentifier()
            ):
                names.add(item.stem)
        return list(names)

    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
        dirs: Set[Path] = set()
        src_dir = pkg_root / "src"
        if src_dir.is_dir():
            dirs.add(src_dir)
        tests_dir = pkg_root / "tests"
        if tests_dir.is_dir():
            dirs.add(tests_dir)
        is_flat_layout = any(
            (item.is_dir() and (item / "__init__.py").exists())
            or (item.is_file() and item.name.endswith(".py"))
            for item in pkg_root.iterdir()
            if item.name not in {".venv", "src", "tests"}
        )
        if is_flat_layout or not dirs:
            dirs.add(pkg_root)
        return list(dirs)

    def get_search_paths(self) -> List[Path]:
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        all_paths.add(self.root_path)
        return sorted(list(all_paths))
~~~~~

### 下一步建议

我们已经实施了战略性的修复。现在，请再次运行完整的测试套件。

我非常有信心，这次修改将解决所有 27 个 `TypeError` 失败，并且我们为诊断问题而创建的 `test_refactor_internals.py` 现在也应该能够成功通过。

执行测试，让我们确认系统已恢复健康，并准备好继续推进路线图。

====


您的分析完全正确，这是一个更高层次的战略性观察，揭示了我之前修复方案中的一个根本性缺陷。我为之前那个“一刀切”的方案道歉，它虽然解决了 `refactor` 命令的问题，但却以破坏 `Workspace` 类的核心契约为代价，导致了更大范围的连锁失败。

您指出的方向是绝对正确的：**`StitcherConfig` 应该是一个增强选项，而不是一个硬性依赖。** 核心组件应当具备自洽的、无需外部配置就能工作的默认行为。

我将根据您的指示，进行一次彻底的战略分析。

### 战略分析报告：`Workspace` 依赖注入与契约破坏

#### 1. 摘要 (Executive Summary)

我们当前面临的大规模测试失败（27个失败用例）并非孤立的 Bug，而是一个典型的**架构契约破坏**事件。根本原因在于，我将 `Workspace` 类的初始化从**自发现模式 (Self-Discovery Mode)** 强制更改为**注入模式 (Injection Mode)**，使其构造函数必须接收一个 `StitcherConfig` 对象。

这个改动虽然满足了 `refactor apply` 命令的特定需求（即从顶层应用加载配置），但它破坏了 `Workspace` 类与大量内部测试用例之间的一个隐性契约：**`Workspace` 应当能够独立地、从零开始地分析一个文件目录结构。**

**战略决策：** 我们必须恢复 `Workspace` 的双模能力。它必须能够：
1.  **（默认）自发现模式**：在没有 `StitcherConfig` 的情况下，通过扫描文件系统中的 `pyproject.toml` 文件来独立构建其对工作区的理解。
2.  **（可选）注入模式**：在提供了 `StitcherConfig` 对象时，跳过文件系统扫描，直接使用该配置来构建工作区视图。

这将使 `Workspace` 既能满足 `refactor` 命令的顶层配置需求，又能恢复对内部测试和其他潜在用例的向后兼容性，使组件更加健壮和解耦。

#### 2. 根本原因分析 (Root Cause Analysis)

1.  **初始状态**: `Workspace(root_path)` 的职责是：给定一个根目录，自己去找到所有的 `pyproject.toml` 文件，并构建出一个 `import_to_source_dirs` 的映射。这是它的核心能力和价值。
2.  **我的错误变更**: 为了让 `refactor` 命令能感知到 `peripheral_paths`，我将构造函数修改为 `Workspace(root_path, config)`。这在逻辑上将“构建工作区视图”的责任**完全转嫁**给了调用者。
3.  **连锁反应**: `stitcher-refactor` 包内的大量集成测试，其目的正是为了验证 `Workspace` 在各种复杂项目结构（如 flat-layout, src-layout, monorepo）下的**自发现能力**。这些测试因此**故意不提供** `StitcherConfig`，它们通过 `Workspace(tmp_path)` 来实例化 `Workspace`，然后断言其内部状态是否符合预期。
4.  **最终结果**: 我的变更使得 `Workspace(tmp_path)` 调用因缺少 `config` 参数而直接抛出 `TypeError`，导致了这 27 个测试用例的集体失败。

#### 3. 识别出的战略缺陷

我的方法存在一个核心的战略缺陷：**为了战术上的便利，牺牲了组件的内聚性和核心契约**。

-   **违反了“高内聚”原则**: `Workspace` 的核心职责是“理解工作区结构”。我的改动削弱了它的这个能力，使其变得依赖外部信息才能工作。一个真正内聚的 `Workspace` 应该能够独立完成它的核心任务。
-   **违反了“依赖倒置”原则**: 我让一个低层的基础设施组件 (`Workspace`) 强依赖于一个高层的配置数据结构 (`StitcherConfig`)。正确的做法应该是，`Workspace` 定义一个它能接受的接口（或数据），而高层应用去适配它，而不是反过来。
-   **触发了 ADAP 协议中的“契约假设”**: 我无意中做出了一个假设：“所有 `Workspace` 的使用者都会、且都应该提供一个 `StitcherConfig` 对象”。测试的失败证明了这个假设是错误的。

#### 4. 提出的战略解决方案：恢复双模能力

我们将对 `Workspace` 类进行重构，使其支持可选的配置注入，从而恢复其自发现能力。

1.  **修改 `__init__` 签名**:
    -   将 `__init__(self, root_path: Path, config: StitcherConfig)`
    -   修改为 `__init__(self, root_path: Path, config: Optional[StitcherConfig] = None)`。

2.  **实现条件初始化逻辑**:
    -   在 `__init__` 方法中，我们将检查 `config` 参数是否存在。
    -   **If `config` is provided**: 调用新的、基于配置的构建方法 (`_build_from_config`)。
    -   **Else (`config` is `None`)**: 调用旧的、基于文件系统扫描的构建方法 (`_discover_packages`)。

3.  **恢复旧的实现**:
    -   我需要将之前被我删除的 `_discover_packages`、`_find_code_dirs` 等方法**恢复**到 `Workspace` 类中，作为其默认行为。

这个方案的优势是显而易见的：
-   **向后兼容**: 所有 27 个失败的测试用例将立即恢复正常，无需对它们进行任何修改。
-   **功能保留**: `refactor apply` 命令仍然可以通过传入 `config` 对象来使用新的、更强大的功能。
-   **架构稳健**: `Workspace` 组件变得更加通用和强大。它既可以独立工作，也可以被高层应用所配置，这使得它在未来的应用场景中更具弹性。

---

