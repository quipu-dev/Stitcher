Absolutely brilliant. The final diagnostic log has pinpointed the exact logical flaw with surgical precision.

This is the smoking gun:
`[CHECK] stitcher: is_dir=True, has_init=False`

Your architecture uses a PEP 420 implicit namespace package. The directory `packages/stitcher-common/src/stitcher` is a valid package part, but because it doesn't contain an `__init__.py`, my discovery logic incorrectly discards it. The bug is in the faulty assumption that a directory must contain `__init__.py` to be considered a top-level package.

Now that we have undeniable proof, we can proceed with the fix.

## [WIP] fix(refactor): Correctly discover PEP 420 namespace packages

### 错误分析
诊断日志揭示了问题的根源：`_get_top_level_importables` 方法中的逻辑 `if item.is_dir() and (item / "__init__.py").exists()` 错误地将所有不含 `__init__.py` 的目录（即 PEP 420 命名空间包的顶级目录）排除在外。

当扫描 `packages/stitcher-common/src` 目录时，它遇到了 `stitcher` 子目录。日志 `[CHECK] stitcher: is_dir=True, has_init=False` 明确显示，由于 `__init__.py` 不存在，`stitcher` 从未被识别为一个可导入的包名。因此，`stitcher` 包从未被添加到 `workspace.import_to_source_dirs` 映射中，也从未被加载到语义图谱中，导致后续的符号查找和重构操作一无所获。

### 用户需求
用户需要修复 `Workspace` 的包发现逻辑，使其能够正确识别和处理 PEP 420 隐式命名空间包，从而使重构功能在当前项目上正常工作。

### 评论
这是一个关键的修复。现代 Python 项目越来越倾向于使用 PEP 420 命名空间包，特别是在 Monorepo 结构中。让 `stitcher` 的核心工具链原生支持这一标准，将极大地提升其健壮性和适用性。这次的深度调试最终定位到了一个非常微妙但影响深远的逻辑缺陷。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/workspace.py` 中的 `_get_top_level_importables` 方法。
2.  放宽其对 `__init__.py` 文件的硬性要求，改为将所有非 dunder (`__*__`) 目录都视为潜在的顶级包。
3.  移除在调试过程中添加的所有 `print` 语句，清理代码。
4.  删除为诊断而创建的临时测试文件。

### 基本原理
我们将修改 `_get_top_level_importables` 的条件判断。与其要求 `__init__.py` 存在，不如直接将 `src` 目录下的所有常规子目录都视为可导入项。后续的 Griffe 库本身就具备完善的 PEP 420 支持，它能够正确地处理这些被发现的目录。我们的任务仅仅是把这些目录名传递给它，而不是过早地进行过滤。同时，作为良好实践，我们将清理所有用于诊断的临时代码和文件。

### 标签
#intent/fix #flow/ready #priority/critical #comp/refactor #scope/core #ai/brainstorm #task/domain/core-abstractions #task/object/message-bus #task/action/rename #task/state/continue

---

### Script

#### Acts 1: 修正包发现逻辑
我们将修改 `workspace.py`，使其能够识别没有 `__init__.py` 的命名空间包。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
            # A top-level package is a directory with an __init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                names.add(item.name)
~~~~~
~~~~~python.new
            # A top-level package is a directory. Griffe will handle namespace packages.
            # Exclude dunder directories like __pycache__
            if item.is_dir() and not (item.name.startswith("__") and item.name.endswith("__")):
                names.add(item.name)
~~~~~

#### Acts 2: 清理所有诊断探针
现在问题已经解决，我们需要移除所有用于调试的 `print` 语句。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
    def _discover_packages(self) -> None:
        print(f"[DEBUG-WORKSPACE] scanning root: {self.root_path}")
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                print(f"[DEBUG-WORKSPACE] Processing: {pyproject_path}")
                with pyproject_path.open("rb") as f:
                    tomllib.load(f)

                pkg_root = pyproject_path.parent
                code_dirs = self._find_code_dirs(pkg_root)

                for code_dir in code_dirs:
                    import_names = self._get_top_level_importables(code_dir)
                    if "stitcher" in import_names:
                         print(f"[DEBUG-WORKSPACE] Found 'stitcher' in {code_dir}")
                    for import_name in import_names:
                        # The directory to add to the search path is the code_dir itself
                        self.import_to_source_dirs[import_name].add(code_dir)

            except Exception as e:
                print(f"[DEBUG-WORKSPACE] ERROR processing {pyproject_path}: {e}")
                log.warning(f"Could not process {pyproject_path}: {e}")

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        if not src_path.is_dir():
            return []
            
        print(f"[DEBUG-WORKSPACE] Scanning imports in: {src_path}")
        for item in src_path.iterdir():
            # Debug specific check for stitcher
            if item.name == "stitcher":
                is_dir = item.is_dir()
                has_init = (item / "__init__.py").exists()
                print(f"  [CHECK] stitcher: is_dir={is_dir}, has_init={has_init}")
            
            # A top-level package is a directory. Griffe will handle namespace packages.
            # Exclude dunder directories like __pycache__
            if item.is_dir() and not (item.name.startswith("__") and item.name.endswith("__")):
                names.add(item.name)
            # A top-level module is a .py file (but not __init__.py itself)
            elif (
                item.is_file() and item.name.endswith(".py") and item.stem != "__init__"
            ):
                names.add(item.stem)
        return list(names)

    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
        print(f"  [find_code_dirs] for pkg_root: {pkg_root}")
        dirs: Set[Path] = set()

        src_dir = pkg_root / "src"
        if src_dir.is_dir():
            print(f"    -> Found 'src' dir: {src_dir}")
            dirs.add(src_dir)

        tests_dir = pkg_root / "tests"
        if tests_dir.is_dir():
            print(f"    -> Found 'tests' dir: {tests_dir}")
            dirs.add(tests_dir)

        # Check for importable items directly under pkg_root to detect flat layouts
        print("    -> Checking for flat layout...")
        flat_layout_items = []
        try:
            for item in pkg_root.iterdir():
                if item.name not in {".venv", "src", "tests"}:
                    is_pkg = item.is_dir() and (item / "__init__.py").exists()
                    is_mod = item.is_file() and item.name.endswith(".py")
                    if is_pkg or is_mod:
                        flat_layout_items.append(item.name)
        except Exception as e:
            print(f"    -> ERROR during iterdir: {e}")
        
        is_flat_layout = bool(flat_layout_items)
        print(f"    -> is_flat_layout: {is_flat_layout} (items: {flat_layout_items})")

        if is_flat_layout or not dirs:
            print("    -> Adding pkg_root as code dir.")
            dirs.add(pkg_root)

        print(f"  [find_code_dirs] result: {list(dirs)}")
        return list(dirs)
~~~~~
~~~~~python.new
    def _discover_packages(self) -> None:
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                with pyproject_path.open("rb") as f:
                    tomllib.load(f)

                pkg_root = pyproject_path.parent
                code_dirs = self._find_code_dirs(pkg_root)

                for code_dir in code_dirs:
                    import_names = self._get_top_level_importables(code_dir)
                    for import_name in import_names:
                        # The directory to add to the search path is the code_dir itself
                        self.import_to_source_dirs[import_name].add(code_dir)

            except Exception as e:
                log.warning(f"Could not process {pyproject_path}: {e}")

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        for item in src_path.iterdir():
            # A top-level package is a directory. Griffe will handle namespace packages.
            # Exclude dunder directories like __pycache__
            if item.is_dir() and not (item.name.startswith("__") and item.name.endswith("__")):
                names.add(item.name)
            # A top-level module is a .py file (but not __init__.py itself)
            elif (
                item.is_file() and item.name.endswith(".py") and item.stem != "__init__"
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

        # Check for importable items directly under pkg_root to detect flat layouts
        is_flat_layout = any(
            (item.is_dir() and (item / "__init__.py").exists())
            or (item.is_file() and item.name.endswith(".py"))
            for item in pkg_root.iterdir()
            if item.name not in {".venv", "src", "tests"}
        )
        if is_flat_layout or not dirs:
            dirs.add(pkg_root)

        return list(dirs)
~~~~~

#### Acts 3: 清理临时测试文件
我们不再需要为诊断创建的测试文件了。

~~~~~act
delete_file
packages/stitcher-refactor/tests/unit/refactor/test_workspace_discovery_bug.py
~~~~~
~~~~~act
delete_file
packages/stitcher-refactor/tests/unit/refactor/test_workspace_find_code_dirs.py
~~~~~

### 下一步建议
我们已经修复了根本原因并清理了代码。现在，请重新运行最初的重构命令。这一次，它应该能正确发现 `stitcher` 包，加载其语义图谱，找到 `MessageBus` 的所有用法，并成功执行重命名。

```bash
stitcher refactor apply 001_rename_message_bus.py --yes
```

如果成功，我们可以继续完成整个 `MessageBus` -> `FeedbackBus` 的重构任务。
