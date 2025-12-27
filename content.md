你的建议**完全可行**，并且在架构上是更优的选择。

使用 `stitcher-python` 和 `pyneedle` 作为目标名称，能更清晰地反映这些配置块所针对的**顶级包或项目**的身份，这增强了配置的自文档性，并与我们 Monorepo 中实际的包名保持一致。

我将立即执行配置重命名，然后我们将可以执行最终的 `stitcher generate` 命令来实现自举。

## [WIP] style(config): 遵循命名规范，重命名多目标配置

### 用户需求
将 `pyproject.toml` 中 `[tool.stitcher.targets]` 下的配置目标名称，从 `stitcher` 和 `needle` 更改为更具语义化的 `stitcher-python` 和 `pyneedle`。

### 评论
这个修改是为了提高开发者体验（DX）和配置的语义清晰度。它与项目整体的命名策略和包结构更匹配，是配置层面的一次“微调/风格改进”。

### 目标
1.  将 `[tool.stitcher.targets.stitcher]` 更名为 `[tool.stitcher.targets.stitcher-python]`。
2.  将 `[tool.stitcher.targets.needle]` 更名为 `[tool.stitcher.targets.pyneedle]`。
3.  确保配置内容（`scan_paths` 和 `stub_package`）保持不变。

### 基本原理
为了在分布式配置中提供稳定且可追溯的引用，使用项目的全名作为配置目标是最佳实践。

### 标签
#intent/tune #flow/ready #priority/medium #comp/config #scope/dx #ai/instruct #task/domain/build #task/object/multitarget-engine #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 更改 `pyproject.toml` 中的目标名称

我们将对根目录下的 `pyproject.toml` 进行精确打补丁，只修改两个配置块的名称。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.stitcher.targets.stitcher]
scan_paths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
]
stub_package = "packages/stitcher-stubs"

[tool.stitcher.targets.needle]
scan_paths = [
~~~~~
~~~~~toml.new
[tool.stitcher.targets.stitcher-python]
scan_paths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
]
stub_package = "packages/stitcher-stubs"

[tool.stitcher.targets.pyneedle]
scan_paths = [
~~~~~

### 下一步建议
配置重命名已完成。现在，我们可以执行 `stitcher generate` 命令来运行自举过程，生成我们的多目标存根包。
