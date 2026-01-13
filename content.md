好的，我们继续执行路线图。现在进入协议层，对 SURI（Stitcher Uniform Resource Identifier）的生成逻辑进行规范化，确保其绝对遵循我们刚刚建立的全局坐标系。

## [WIP] refactor(lang-python): 重构 SURIGenerator 以强制使用工作区相对路径

### 用户需求

根据“`stitcher.lock` 模式与全局 SURI 架构”路线图，实施 3.2 阶段任务：在 `stitcher-lang-python` 包中，重构 `SURIGenerator`，使其不再依赖任何局部或隐式的路径上下文，而是强制性地、只接受已经计算好的、相对于 Workspace Root 的路径作为输入。

### 评论

这是对系统“本体论正确性”的一次关键校准。旧的 `SURIGenerator` 必须依赖一个 `root_path` 实例变量，这在复杂的 Monorepo 环境中引入了歧义的风险——不同的调用者可能传入不同的 `root_path`，导致同一个文件产生不同的 SURI。

通过将 `SURIGenerator` 重构为一个无状态的工具类，并强制其 API 契约只接受“工作区相对路径”，我们彻底根除了这种“身份假设”（ADAP v1.0），将路径计算的责任唯一地、正确地归于 `Workspace` 服务。这使得 SURI 的生成逻辑变得纯粹、确定且无副作用。

### 目标

1.  将 `SURIGenerator` 类从一个有状态的实例类重构为一个无状态的静态工具类。
2.  移除其 `__init__` 方法和 `root_path` 成员变量。
3.  将其所有方法 (`for_symbol`, `for_file`, `parse`) 修改为 `@staticmethod`。
4.  修改方法签名，将 `file_path: Path` 类型的参数替换为 `workspace_relative_path: str`，明确 API 契约。
5.  移除所有内部进行路径转换（如 `relative_to`）的逻辑。

### 基本原理

软件工程中的许多复杂问题源于职责不清。`SURIGenerator` 的核心职责是**格式化**，而不是**计算**。它应该只负责将给定的路径和片段组合成 `py://<path>#<fragment>` 的标准格式。而路径的计算——即确定一个绝对路径相对于工作区根目录的相对位置——是 `Workspace` 服务的核心职责。

本次重构严格遵循单一职责原则（SRP）。我们将路径计算的逻辑完全从 `SURIGenerator` 中剥离，使其成为一个纯粹的、可预测的格式化工具。这不仅简化了 `SURIGenerator` 本身，也使得系统的依赖关系更加清晰：任何需要生成 SURI 的组件，现在都必须首先从 `Workspace` 服务获取确定性的相对路径，从而在架构层面强制保证了 SURI 的全局唯一性和稳定性。

### 标签

#intent/refine #flow/ready #priority/critical #scope/api #scope/core #ai/instruct #task/domain/architecture #task/object/lock-file #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 SURIGenerator

我将使用 `write_file` 彻底重写 `stitcher/lang/python/uri.py` 文件，以实现上述的无状态、静态工具类设计。

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/uri.py
~~~~~
~~~~~python
from pathlib import Path
from urllib.parse import urlparse, unquote


class SURIGenerator:
    """
    A stateless utility for creating and parsing Stitcher Uniform Resource Identifiers (SURIs).

    SURIs follow the format: `py://<workspace_relative_path>#<fragment>`
    - `workspace_relative_path`: The POSIX-style path of the file relative to the workspace root.
    - `fragment`: The symbol's logical path within the file (e.g., `MyClass.my_method`).
    """

    @staticmethod
    def for_symbol(workspace_relative_path: str, fragment: str) -> str:
        """Creates a SURI for a specific symbol within a file."""
        return f"py://{workspace_relative_path}#{fragment}"

    @staticmethod
    def for_file(workspace_relative_path: str) -> str:
        """Creates a SURI for a file itself, without a symbol fragment."""
        return f"py://{workspace_relative_path}"

    @staticmethod
    def parse(suri: str) -> tuple[str, str]:
        """
        Parses a SURI into its path and fragment components.

        Returns:
            A tuple of (workspace_relative_path, fragment).
            The fragment will be an empty string if not present.
        """
        parsed = urlparse(suri)
        if parsed.scheme != "py":
            raise ValueError(f"Invalid SURI scheme: '{parsed.scheme}'")

        # The path component from urlparse includes the leading '/', which we strip.
        # It also handles URL-encoded characters, which we decode.
        path = unquote(parsed.path).lstrip("/")
        fragment = unquote(parsed.fragment)

        return path, fragment

    @staticmethod
    def from_path(
        root_path: Path, absolute_path: Path, fragment: str | None = None
    ) -> str:
        """
        [DEPRECATED] Creates a SURI from absolute paths.
        Prefer creating workspace-relative paths upstream and using `for_symbol`.
        """
        rel_path = absolute_path.relative_to(root_path).as_posix()
        if fragment:
            return SURIGenerator.for_symbol(rel_path, fragment)
        return SURIGenerator.for_file(rel_path)
~~~~~

### 下一步建议

我们已经成功地在协议层建立了 SURI 的规范。现在，所有之前依赖旧 `SURIGenerator` 的代码都已损坏，这正是我们想要的——架构性断裂变更强制所有消费者进行适配。

下一步是**实施路线图的 3.3 阶段**：进入持久化层，将 `SignatureManager` 从 `stitcher-application` 迁移到 `stitcher-lang-sidecar`，并按照新的 `stitcher.lock` 模式对其进行彻底重写。这将是我们修复 `SURIGenerator` 调用的第一个战场。
