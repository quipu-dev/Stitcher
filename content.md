You're right, my apologies. The traceback clearly shows I made a mistake in the file system handling logic. The `mkdir` call is missing the `parents=True` argument, which is required to create nested directories like `stubs/src/my_app` when `stubs/src` might not exist yet.

I will fix this immediately.

## [WIP] fix(application): Fix FileNotFoundError in stub package generation

### 错误分析
测试 `test_generate_with_stub_package_creates_correct_structure` 失败的根本原因是 `StitcherApp._generate_stubs` 方法中的 `pathlib.Path.mkdir` 调用缺少 `parents=True` 参数。

代码尝试创建 `.../stubs/src/my_app` 目录，但其父目录 `.../stubs/src` 在该执行点尚未被创建，导致 `os.mkdir`（由 `Path.mkdir` 在内部调用）抛出 `FileNotFoundError`。

### 用户需求
修复在 `stub_package` 模式下因目录不存在而导致的 `FileNotFoundError`，使新添加的集成测试能够通过。

### 评论
这是一个典型的文件系统操作疏忽。在处理可能不存在的多级路径时，必须确保使用能够递归创建目录的选项。修复此问题将使存根包的脚手架逻辑更加健壮。

### 目标
1.  定位 `stitcher.app.core.StitcherApp._generate_stubs` 方法中失败的 `mkdir` 调用。
2.  为其添加 `parents=True` 参数，以确保所有必要的父目录都能被自动创建。

### 基本原理
`pathlib.Path.mkdir(parents=True, exist_ok=True)` 是一个幂等操作，它能确保目标目录及其所有父目录都存在，无论它们之前是否存在。这是创建嵌套目录结构最安全、最直接的方法。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/broken-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `mkdir` 调用

我们将为 `top_level_pkg_dir.mkdir` 添加 `parents=True` 参数。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                    if top_level_pkg_dir not in created_py_typed:
                        top_level_pkg_dir.mkdir(exist_ok=True)
                        (top_level_pkg_dir / "py.typed").touch(exist_ok=True)
                        created_py_typed.add(top_level_pkg_dir)
~~~~~
~~~~~python.new
                    if top_level_pkg_dir not in created_py_typed:
                        top_level_pkg_dir.mkdir(parents=True, exist_ok=True)
                        (top_level_pkg_dir / "py.typed").touch(exist_ok=True)
                        created_py_typed.add(top_level_pkg_dir)
~~~~~
