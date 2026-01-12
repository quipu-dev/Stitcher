分析显示，为了保持 Monorepo 结构的连贯性，我们需要对 `stitcher-python-adapter` 和 `stitcher-stubgen` 的配置进行针对性修正。

主要变动包括：
1.  **清理**: 在 `stitcher-python-adapter` 中移除了不存在的 `stitcher-python-analysis` 依赖项（该功能已并入 adapter 包）。
2.  **映射补全**: 在 `tool.uv.sources` 中为这两个包增加了 `stitcher-test-utils` 的映射，以支持各自目录下的测试运行。
3.  **对齐**: 确保所有在 `dependencies` 中声明的内部包都在 `tool.uv.sources` 中有对应的 `{ workspace = true }` 条目。

以下是更新计划：

## [WIP] refactor: 同步 stitcher-python-adapter 与 stitcher-stubgen 的依赖关系

### 用户需求
更新 `stitcher-python-adapter` 和 `stitcher-stubgen` 的 `pyproject.toml` 文件，确保其内部依赖关系与当前的目录结构完全一致。

### 评论
在 UV 驱动的 Monorepo 环境中，正确配置 `tool.uv.sources` 是实现跨包调用和增量构建的前提。此外，为了支持包内测试（In-package tests），必须确保测试工具包在工作区中可见。

### 目标
1.  修正 `stitcher-python-adapter` 的依赖列表，移除无效项。
2.  补全两个包的 `tool.uv.sources` 声明。
3.  建立测试辅助工具的链接映射。

### 基本原理
基于“显式依赖”原则，我们将 `stitcher-python-analysis` 从 adapter 的依赖中移除，因为它已不再作为一个独立的内部包存在。同时，为了遵循我们的测试架构规范，我们将 `stitcher-test-utils` 加入到这两个包的源码映射中，这样在这些包的目录下运行 `pytest` 时可以正确加载共享的测试夹具。

### 标签
#intent/refine #flow/ready #comp/build #concept/config #scope/dx #ai/instruct #task/domain/build #task/object/pyproject-dependencies #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 更新 `stitcher-python-adapter` 的依赖配置

我们将移除无效的 `stitcher-python-analysis` 并同步源码映射。

~~~~~act
patch_file
packages/stitcher-python-adapter/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-python-analysis",
    "stitcher-spec",
    "stitcher-common",
    "stitcher-index",
    "libcst",
    "griffe",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-python-analysis = { workspace = true }
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-index",
    "libcst",
    "griffe",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~

#### Acts 2: 更新 `stitcher-stubgen` 的依赖配置

补全其测试所需的源码映射。

~~~~~act
patch_file
packages/stitcher-stubgen/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~

### 下一步建议

- **刷新工作区**: 建议在根目录执行 `uv sync`，这会自动重新链接所有包并更新 `uv.lock`。
- **环境一致性检查**: 检查 `stitcher-common` 是否已在其依赖中包含 `pyneedle`，因为它是整个系统的底层通讯基础。
- **运行集成测试**: 尝试运行 `packages/stitcher-python-adapter/tests/integration/` 下的测试，验证依赖项是否已正确识别。
