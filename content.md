## [WIP] fix: 为 Workspace 注入 Print 调试以诊断包发现问题

### 错误分析
尽管我们创建的复现测试 `test_workspace_discovery_bug.py` 成功通过了，但 CLI 在实际运行中仍然无法发现 `stitcher` 包。这表明问题的根源不在于 `Workspace` 处理 Monorepo 结构的逻辑本身，而在于实际运行环境中的某些特定因素（如文件系统权限、未捕获的异常、或者 `glob` 的行为差异）。

由于单元测试环境是合成的（Synthetic），它无法完全模拟实际环境的所有变量。为了即时诊断问题，我们需要在 `Workspace._discover_packages` 内部注入直接的 `print` 调试语句，绕过可能未配置输出的 `logging` 系统。

### 用户需求
用户需要诊断为什么 `stitcher refactor` 在实际运行时找不到 `stitcher` 包。

### 评论
这是一种“探针”式的调试方法。虽然在生产代码中插入 `print` 不优雅，但在复杂的环境问题诊断中，它是最直接、最诚实的方法。我们将在诊断完成后移除这些代码。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/workspace.py`。
2.  在 `_discover_packages` 方法中注入打印语句：
    *   打印正在扫描的 `pyproject.toml` 路径。
    *   打印在每个路径下发现的 `import_names`。
    *   如果在处理某个 `pyproject.toml` 时发生异常，直接打印异常详情。

### 基本原理
通过对比 `pyneedle`（被成功发现）和 `stitcher-common`（未被发现）在扫描过程中的日志差异，我们将能迅速定位问题所在。

### 标签
#intent/fix #flow/ready #priority/high #comp/refactor #scope/core #ai/instruct #task/domain/diagnostics #task/object/workspace #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 在 Workspace 中注入探针

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议
请再次运行 `refactor` 命令（带有 `-v`）：

```bash
stitcher -v refactor apply 001_rename_message_bus.py --yes
```

请仔细检查输出中以 `[DEBUG-WORKSPACE]` 开头的行，特别是关于 `packages/stitcher-common/pyproject.toml` 的处理情况。
