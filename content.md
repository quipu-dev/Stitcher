这是一个针对 `pyrefly` 配置错误的修复计划。

根据错误日志分析：
1.  工具输出了 `[missing-import]` 错误，这是 Pyright 典型的错误代码，表明 `pyrefly` 极有可能是 Pyright 的封装或变体。
2.  警告信息 `WARN ...: Extra keys found in config: extra_paths` 表明 `pyrefly` 读取了 `[tool.pyrefly]` 配置块，但不识别 `extra_paths` 这个键名。
3.  Pyright 的标准 TOML 配置键名为驼峰式 `extraPaths`（如 `[tool.pyright]` 块所示），而用户在 `[tool.pyrefly]` 中使用了蛇形命名 `extra_paths`。

因此，解决方案是将 `pyproject.toml` 中 `[tool.pyrefly]` 下的 `extra_paths` 更正为 `extraPaths`，以对齐 Pyright 的配置规范，从而使静态分析工具能够正确解析 Monorepo 中的子包路径。

## [WIP] fix(build): 修正 pyproject.toml 中 pyrefly 的配置键名

### 错误分析
用户执行 `pyrefly check` 时遇到了大量的 `[missing-import]` 错误，导致无法解析 `needle.*` 命名空间下的模块。同时，工具输出了警告 `Extra keys found in config: extra_paths`。

这表明 `pyrefly`（推测基于 Pyright）无法识别配置中的 `extra_paths` 键，导致它没有将 `src` 目录加入搜索路径。由于 Pyright 使用驼峰命名法（CamelCase）作为配置标准（例如 `extraPaths`），当前配置中的蛇形命名（snake_case）是无效的。

### 用户需求
修正配置错误，使 `pyrefly` 能够正确识别项目的 `extraPaths`，从而消除 `[missing-import]` 错误并顺利通过静态检查。

### 评论
这是一个简单的配置键名拼写错误修正，但对于多包（Monorepo）结构的 Python 项目至关重要，因为显式指定 `extraPaths` 是让静态分析工具理解 Namespace Packages 布局的关键。

### 目标
1.  在 `pyproject.toml` 中，将 `[tool.pyrefly]` 部分的 `extra_paths` 重命名为 `extraPaths`。

### 基本原理
通过将配置键名对齐到 Pyright 的标准 schema (`extraPaths`)，我们确保 `pyrefly` 能够正确加载这些路径。一旦路径被加载，工具就能正确解析 `packages/*/src` 下的模块，从而解决 `needle.nexus` 等模块无法找到的问题。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #concept/config #scope/dx
#task/domain/testing #task/object/config #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正 pyproject.toml 配置

我们将把 `[tool.pyrefly]` 下的 `extra_paths` 替换为 `extraPaths`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
[tool.pyrefly]
extra_paths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
~~~~~
~~~~~new
[tool.pyrefly]
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
~~~~~

### 下一步建议
配置修正后，建议再次运行 `pyrefly check` 以验证 `[missing-import]` 错误是否已消除。如果问题依然存在，可能需要进一步检查是否需要同步更新 `pyrightconfig.json` 或检查 `pyrefly` 是否有其他特定的配置要求。
