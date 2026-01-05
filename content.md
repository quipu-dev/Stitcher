## [WIP] fix: 增强 Workspace 调试探针以诊断 importables 扫描

### 错误分析
之前的诊断信息显示 `glob` 扫描是工作的（因为发现了 `needle` 和其他测试包），但核心的 `stitcher` 命名空间包神秘消失了。这只可能发生在 `_get_top_level_importables` 方法内部：它要么没有遍历到 `stitcher` 目录，要么判定其不是一个包（例如认为 `__init__.py` 不存在）。

### 用户需求
用户需要更详细的内部执行日志来破解“stitcher 包消失之谜”。

### 评论
我们必须深入到 `iterdir` 循环内部。这就像在显微镜下观察细胞分裂一样，我们需要看到每一个文件系统的判断结果。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/workspace.py`。
2.  取消注释 `pyproject.toml` 的处理日志。
3.  在 `_get_top_level_importables` 中添加详细的遍历日志，打印每个 `item` 的名称以及 `is_dir` 和 `has_init` 的检查结果。

### 基本原理
通过直接打印 `item.is_dir()` 和 `(item / "__init__.py").exists()` 的结果，我们将排除所有猜测，获得确凿的证据。

### 标签
#intent/fix #flow/ready #priority/high #comp/refactor #scope/core #ai/instruct #task/domain/diagnostics #task/object/workspace #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 增强 Workspace 探针

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
    def _discover_packages(self) -> None:
        print(f"[DEBUG-WORKSPACE] scanning root: {self.root_path}")
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                # print(f"[DEBUG-WORKSPACE] Processing: {pyproject_path}")
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

    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
~~~~~
~~~~~python.new
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
            
            # A top-level package is a directory with an __init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                names.add(item.name)
            # A top-level module is a .py file (but not __init__.py itself)
            elif (
                item.is_file() and item.name.endswith(".py") and item.stem != "__init__"
            ):
                names.add(item.stem)
        return list(names)

    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
~~~~~

### 下一步建议
请再次运行命令（带 `-v`），这一次我们应该能看到关于 `src` 目录扫描的详细信息。

```bash
stitcher -v refactor apply 001_rename_message_bus.py --yes
```
