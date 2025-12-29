## [WIP] fix(config): 同步 pytest 的 pythonpath 与 pyright 的 extraPaths

### 用户需求
修复除 `pyright` 之外的静态分析工具报告的 `missing-import` 错误，确保项目的所有工具都能正确解析 `needle` 模块的导入路径。

### 评论
这是一个常见的 Monorepo 配置陷阱。项目依赖于多个工具，而这些工具各自有独立的路径配置，导致不一致。同步这些配置是确保开发者体验 (DX) 和 CI/CD 流程稳定性的关键一步。

### 目标
1.  在 `pyproject.toml` 文件中定位 `[tool.pytest.ini_options].pythonpath` 配置。
2.  将 `needle-stubs` 包的源码路径添加到该配置列表中。

### 基本原理
`pyright` 使用 `[tool.pyright].extraPaths` 来解析额外的导入路径，而 `pytest` 及其生态中的其他工具（如 `ruff`）则依赖 `[tool.pytest.ini_options].pythonpath`。由于后者缺少指向 `needle-stubs` 包的路径 (`packages/needle-stubs/src`)，导致这些工具无法找到 `needle` 模块。通过将该路径添加到 `pythonpath` 列表中，我们确保了所有工具都使用同一套完整的搜索路径，从而解决了导入错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/config-consistency #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 更新 pyproject.toml 中的 pythonpath

我们将修改 `pyproject.toml` 文件，在 `[tool.pytest.ini_options].pythonpath` 列表的末尾，添加 `needle-stubs` 的 `src` 路径。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/pyneedle/src",
    "packages/stitcher-test-utils/src"
]

[tool.stitcher.targets.stitcher]
scan_paths = [
~~~~~
~~~~~toml.new
    "packages/pyneedle/src",
    "packages/stitcher-test-utils/src",
    "packages/needle-stubs/src"
]

[tool.stitcher.targets.stitcher]
scan_paths = [
~~~~~

### 下一步建议
应用此变更后，请重新运行之前报错的静态分析工具。`missing-import` 错误现在应该已经完全解决了。这是一个 `[COMMIT]` 的好时机，因为它代表了一个完整的、逻辑独立的修复。如果你同意，我可以在下一步为你生成提交计划。
