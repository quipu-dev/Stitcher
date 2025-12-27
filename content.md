## [WIP] fix: 统一 needle 命名空间包定义并修复 pyrefly 配置

3.  **错误分析**
    *   **现象**: `pyrefly` 报告找不到 `needle.pointer` 和 `needle.nexus`，尽管路径已配置。同时警告配置文件中存在无效键 `extraPaths`。
    *   **根因**:
        1.  **命名空间遮蔽**: `packages/pyneedle/src/needle` 包含 `__init__.py`（显式命名空间），而其他包（如 `pyneedle-pointer`）的 `needle` 目录没有 `__init__.py`（隐式命名空间）。静态分析工具（如 Pyright/Pyrefly）通常无法处理这种混合模式，一旦找到显式的 `__init__.py`，就会认为这是该包的唯一来源，从而忽略其他路径下的内容。
        2.  **配置无效**: `pyproject.toml` 中的 `[tool.pyrefly]` 部分包含了 `extraPaths`，但根据警告，这是不被支持的配置项（通常仅属于 `[tool.pyright]`）。
    *   **解决**: 为所有 `needle` 子包添加基于 `pkgutil` 的 `__init__.py`，使其成为标准的显式命名空间包；同时清理 `pyproject.toml`。

4.  **用户需求**
    *   修复 `pyrefly check` 的报错。
    *   确保 monorepo 中的 `needle` 命名空间能被静态分析工具正确解析。

5.  **评论**
    这是一个在 Python Monorepo 中非常经典的“混合命名空间”问题。虽然 Python 运行时（尤其是在 `uv` 处理的 editable 模式下）能容忍这种情况，但静态分析工具要求更高的严格性。统一使用 `pkgutil` 风格是目前兼容性最好的方案。

6.  **目标**
    *   在 `pyneedle-pointer`, `pyneedle-nexus`, `pyneedle-spec` 的 `src/needle` 目录下创建 `__init__.py`。
    *   移除 `pyproject.toml` 中无效的 `[tool.pyrefly]` 配置项。

7.  **基本原理**
    通过在所有分包的根目录 (`needle/`) 添加包含 `__path__ = __import__("pkgutil").extend_path(__path__, __name__)` 的 `__init__.py`，我们明确声明这是一个跨多个目录的命名空间包。这消除了隐式/显式冲突，强制工具合并所有路径。

8.  **标签**
    #intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/dx #task/object/static-analysis #task/action/fix #task/state/begin

9.  **分隔符**
    ---

10. **脚本**
    ### Script

#### Acts 1: 创建命名空间声明文件
为三个缺失 `__init__.py` 的子包创建该文件，内容仅包含标准的 `pkgutil` 扩展指令。

~~~~~act
write_file
packages/pyneedle-pointer/src/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/pyneedle-spec/src/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 2: 修复 pyproject.toml 配置
移除 `[tool.pyrefly]` 下引发警告的 `extraPaths` 配置块。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.pyrefly]
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src",
]
~~~~~
~~~~~toml.new
[tool.pyrefly]
~~~~~

11. **下一步建议**
    执行计划后，请再次运行 `pyrefly check`。如果问题解决，建议提交代码 (`[COMMIT]`)。如果仍有其他模块（如 `stitcher`）出现类似问题，可能需要对该命名空间应用相同的策略（尽管 `stitcher` 目前看起来是纯隐式的，应该没问题）。
