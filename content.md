好的，你再次发现了问题的关键。`uv` 的错误信息非常精确：我们在上一步中将 `pyneedle` 包添加到了根项目的 `[dev]` 依赖中，但没有在根项目的 `[tool.uv.sources]` 部分告诉 `uv` 这个包是工作区的一部分。

虽然每个 `pyneedle-*` 包自己的 `pyproject.toml` 文件都正确地声明了 *它们自己* 的依赖关系，但当根项目将它们作为依赖项时，根项目也必须声明在哪里可以找到它们。

我们将为根 `pyproject.toml` 补全这些缺失的声明。

## [WIP] fix(deps): 在根配置中声明 pyneedle-* 工作区源

### 错误分析
`uv pip install -e .[dev]` 命令失败，并报错 `pyneedle is included as a workspace member, but is missing an entry in tool.uv.sources`。

这是因为上一步操作虽然将 `pyneedle` 系列包加入了 `[project.optional-dependencies].dev` 列表，但没有同步更新根 `pyproject.toml` 中的 `[tool.uv.sources]` 部分。`uv` 在解析 `dev` 依赖项时，虽然通过 `[tool.uv.workspace].members` 知道 `pyneedle` 是一个工作区成员，但没有在 `[tool.uv.sources]` 中找到一个显式的映射规则，因此无法确认如何处理这个依赖，从而导致解析失败。

### 用户需求
修正根 `pyproject.toml` 文件，使其包含所有 `pyneedle-*` 包的 `uv.sources` 声明，以便 `uv pip install -e .[dev]` 命令可以成功执行。

### 评论
这是 `uv` 工作区规范的一个核心特性。任何时候一个工作区包被另一个包（包括根项目本身）依赖时，依赖方都必须在其 `[tool.uv.sources]` 中明确声明该依赖来自工作区 (`{ workspace = true }`)。这是一个保证依赖解析正确性和确定性的关键步骤。

### 目标
1.  在根 `pyproject.toml` 文件的 `[tool.uv.sources]` 部分，为 `pyneedle`、`pyneedle-nexus`、`pyneedle-pointer` 和 `pyneedle-spec` 添加 `{ workspace = true }` 声明。

### 基本原理
通过在根 `pyproject.toml` 的 `[tool.uv.sources]` 中添加缺失的条目，我们为 `uv` 解析器提供了完整的上下文。当它在 `dev` 依赖项中看到 `pyneedle` 时，会查询 `[tool.uv.sources]`，找到对应的 `{ workspace = true }` 规则，并将其正确地解析为本地的 `packages/pyneedle` 目录，而不是去 PyPI 查找。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/testing #task/object/config #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 更新根 `pyproject.toml` 的 `uv.sources`

我们将把所有 `pyneedle-*` 包添加到 `[tool.uv.sources]` 列表。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-scanner = { workspace = true }
stitcher-io = { workspace = true }
stitcher-config = { workspace = true }
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }
stitcher-needle = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~
~~~~~new
[tool.uv.sources]
pyneedle = { workspace = true }
pyneedle-nexus = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-spec = { workspace = true }
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-scanner = { workspace = true }
stitcher-io = { workspace = true }
stitcher-config = { workspace = true }
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }
stitcher-needle = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~

### 下一步建议
1.  应用此变更。
2.  再次运行 `uv pip install -e .[dev]`。这次它应该可以成功解析并安装所有工作区包了。
