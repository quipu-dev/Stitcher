让我们采取最后一步，也是最决定性的一步调试：我们将把**两个方法的调试日志合并在一起**，以观察它们在同一次运行中的交互。

## [WIP] fix: 合并 Workspace 调试探针以进行最终诊断

### 错误分析
独立的单元测试都通过了，但集成在一起的 CLI 行为却失败了。这表明问题出在组件的交互或环境的特定状态上。`_find_code_dirs` 在测试中表现正常，但在 `_discover_packages` 的真实循环中却没有产生预期的输出。我们需要同时观察这两个方法的内部状态，以捕捉它们交互时的异常行为。

### 用户需求
用户需要最终的、最详细的诊断信息，以彻底解决 `Workspace` 的包发现问题。

### 评论
这是调试的最后手段。通过将两个相关方法的日志交织在一起，我们可以构建出一个完整的、按时间顺序排列的执行轨迹。任何逻辑上的不匹配或状态异常都将无处遁形。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/workspace.py`。
2.  在 `_find_code_dirs` 方法中注入详细的 `print` 语句，以显示其内部决策过程（检查 `src` 和 `tests` 目录，以及扁平布局检测的结果）。
3.  确保这些日志与 `_discover_packages` 的现有日志一起输出，以便进行对比分析。

### 基本原理
我们将把探针插入到 `_find_code_dirs` 内部的每一个逻辑分支中。当 `_discover_packages` 循环处理到 `stitcher-common` 时，我们将能够精确地看到 `_find_code_dirs` 是如何判断其目录结构的，从而揭示失败的根本原因。

### 标签
#intent/fix #flow/ready #priority/critical #comp/refactor #scope/core #ai/instruct #task/domain/diagnostics #task/object/workspace #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 植入最终的合并探针

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
        dirs: Set[Path] = set()

        src_dir = pkg_root / "src"
        if src_dir.is_dir():
            dirs.add(src_dir)

        tests_dir = pkg_root / "tests"
        if tests_dir.is_dir():
            dirs.add(tests_dir)

        # Check for importable items directly under pkg_root to detect flat layouts
        # or top-level test suites.
        is_flat_layout = any(
            (item.is_dir() and (item / "__init__.py").exists())
            or (item.is_file() and item.name.endswith(".py"))
            for item in pkg_root.iterdir()
            if item.name not in {".venv", "src", "tests"}
        )
        if is_flat_layout or not dirs:
            dirs.add(pkg_root)

        return list(dirs)

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        for item in src_path.iterdir():
            # A top-level package is a directory with an __init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                names.add(item.name)
            # A top-level module is a .py file (but not __init__.py itself)
            elif (
                item.is_file() and item.name.endswith(".py") and item.stem != "__init__"
            ):
                names.add(item.stem)
        return list(names)
~~~~~
~~~~~python.new
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
            
            # A top-level package is a directory with an __init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                names.add(item.name)
            # A top-level module is a .py file (but not __init__.py itself)
            elif (
                item.is_file() and item.name.endswith(".py") and item.stem != "__init__"
            ):
                names.add(item.stem)
        return list(names)
~~~~~

### 下一步建议
这是决胜局。请最后一次运行命令：

```bash
stitcher -v refactor apply 001_rename_message_bus.py --yes
```

请将完整的、带有 `[DEBUG-WORKSPACE]` 和 `[find_code_dirs]` 标记的输出提供给我。这次，我们一定能找到问题。
