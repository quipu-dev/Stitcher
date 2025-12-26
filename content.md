简要回答：
是的，这正是问题的根源。`stitcher` 默认的扫描路径为空列表（为了安全和避免误扫描），它严格依赖 `pyproject.toml` 中的 `[tool.stitcher]` 配置来通过 NFR3 定义的行为工作。由于当前根目录的配置文件中缺少此部分，工具不知道该扫描哪里，因此“罢工”。

我们需要在根目录的 `pyproject.toml` 中显式配置 `scan_paths`，指向 `packages` 目录，以启动 Dogfooding 流程。

## [WIP] chore: 配置项目自身的 stitcher 扫描路径

### 用户需求
用户希望在 `stitcher-python` 项目自身上运行 `stitcher init` 以进行 Dogfooding，但工具报告找不到文件。用户指出这与 NFR3（可配置性）相关，需要通过 `pyproject.toml` 明确指定扫描行为。

### 评论
这是一个经典的“自举”时刻。我们实现了读取配置的功能 (`stitcher-config`)，但忘记在自己的项目中配置它。明确配置 `scan_paths` 不仅能解决当前报错，也是验证 NFR3 实现是否符合预期的第一步。

### 目标
1.  在根目录的 `pyproject.toml` 中添加 `[tool.stitcher]` 配置段。
2.  将 `scan_paths` 设置为 `["packages"]`，以覆盖工作区内的所有子包。

### 基本原理
`stitcher-config` 模块的 `load_config_from_path` 函数会查找 `pyproject.toml` 中的 `tool.stitcher` 部分。如果不存在，它将使用默认值（空列表），导致扫描器无事可做。通过注入此配置，我们明确告知工具在 `packages` 目录下递归查找 Python 源代码。

### 标签
#intent/tooling #flow/ready #priority/high #comp/build #concept/config #scope/dx #human/lead
#task/domain/config #task/object/pyproject-toml #task/action/configure
#task/state/continue

---

### Script

#### Acts 1: 添加 Stitcher 配置

我们在 `pyproject.toml` 的末尾添加配置，指定扫描整个 `packages` 目录。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
[tool.pytest.ini_options]
addopts = "-ra --cov=stitcher --cov-report=term-missing"
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = ["packages/stitcher-spec/src", "packages/stitcher-common/src", "packages/stitcher-scanner/src", "packages/stitcher-io/src", "packages/stitcher-config/src", "packages/stitcher-application/src", "packages/stitcher-cli/src", "packages/stitcher-needle/src"]
~~~~~
~~~~~new
[tool.pytest.ini_options]
addopts = "-ra --cov=stitcher --cov-report=term-missing"
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = ["packages/stitcher-spec/src", "packages/stitcher-common/src", "packages/stitcher-scanner/src", "packages/stitcher-io/src", "packages/stitcher-config/src", "packages/stitcher-application/src", "packages/stitcher-cli/src", "packages/stitcher-needle/src"]

[tool.stitcher]
scan_paths = ["packages"]
~~~~~

### 下一步建议
执行此计划后，再次运行 `stitcher init`。预期它将扫描 `packages/` 下的所有 Python 文件，并生成大量的 `.stitcher.yaml` 文件。这将正式开启 Dogfooding 的第一阶段。
