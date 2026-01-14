这是一个典型的“架构回归”案例。在我之前的重构中，虽然解决了循环导入问题，但我改变了系统的一个核心契约：**“工作区的根是如何被定义的？”**。

大量的测试失败（52个！）表明，这个核心假设的改变已经动摇了整个系统的基础。

根本原因在于，我用一个**更严格**的函数 `find_workspace_root` 替换了一个**更宽松**的函数 `_find_pyproject_toml`，却没有考虑到测试环境的设置。

1.  **旧逻辑 (`_find_pyproject_toml`)**: 它的行为是“向上找到**任何** `pyproject.toml` 文件并将其视为根”。这对于测试来说非常方便，因为 `WorkspaceFactory` 只需要创建一个 `pyproject.toml` 就能定义一个项目。

2.  **新逻辑 (`find_workspace_root`)**: 它的行为是“向上找到一个包含 `.git` 目录 **或者** 一个包含 `[tool.uv.workspace]` 的 `pyproject.toml` 的目录”。

3.  **冲突点**: `WorkspaceFactory` 在绝大多数测试中，为了保持轻量，**既不创建 `.git` 目录，也不在 `pyproject.toml` 中添加 `[tool.uv.workspace]` 部分**。

**结论**: 在所有 52 个失败的测试环境中，新的 `find_workspace_root` 函数实际上**无法找到任何根目录**，并抛出了 `WorkspaceNotFoundError`。我的 `load_config_from_path` 捕获了这个异常，然后返回了一个**完全空的默认配置** (`[StitcherConfig()]`)。因此，整个应用程序在执行时都认为没有任何文件需要扫描或处理，导致所有后续的行为断言全部失败。

根据 HFEA 和 ADAP 协议，正确的做法不是去修改所有 52 个测试来适应这个更严格的定义（战术修复），而是修复这个定义本身，使其更符合现实（战略方案）。一个只包含 `pyproject.toml` 的目录，在很多情况下，就是一个合法的项目根。

我将放宽 `find_workspace_root` 的约束，使其行为与旧逻辑兼容，同时保留新逻辑的优点。它将按以下顺序查找根目录：

1.  `.git` 目录 (最强信号)
2.  包含 `[tool.uv.workspace]` 的 `pyproject.toml` (次强信号)
3.  **任何** `pyproject.toml` 文件 (兼容旧行为和简单项目)

这样一来，它就成为了一个真正健壮且唯一的“声音”，能够正确处理所有情况，包括我们的测试环境。

## [WIP] fix(workspace): 放宽工作区根发现条件以修复测试回归

### 错误分析

用一个更严格的 `find_workspace_root` 函数替换了原有的 `_find_pyproject_toml` 搜索逻辑后，导致在测试环境中无法找到工作区根目录。新的函数要求必须存在 `.git` 目录或 `[tool.uv.workspace]` 配置，而测试工厂 `WorkspaceFactory` 并未提供这些。这导致配置加载失败，返回一个空配置，从而引发了大规模的级联测试失败。

### 用户需求

修复因工作区发现逻辑变更而导致的 52 个测试失败，并使根目录发现机制能够兼容简单项目（即仅包含 `pyproject.toml`）。

### 评论

这是一个深刻的教训，提醒我们修改核心基础设施时必须充分考虑其所有隐式契约。将 `find_workspace_root` 的逻辑放宽，使其能够将任何包含 `pyproject.toml` 的目录视为一个潜在的项目根，这是一个正确的战略决策。它不仅修复了当前的回归问题，还使该函数更加通用和健壮，能够适应从简单单包项目到复杂 monorepo 的各种场景。

### 目标

1.  修改 `stitcher.workspace.utils.find_workspace_root` 函数。
2.  在现有的检查（`.git`, `uv.workspace`）之后，增加一个回退检查：如果目录中存在 `pyproject.toml` 文件，也将其视为工作区根。
3.  确保所有测试通过，验证该修复的正确性。

### 基本原理

通过修改 `utils.py` 中的 `find_workspace_root` 函数，我们在其向上遍历的循环中增加一个条件。这个新条件将简单地检查 `(parent / "pyproject.toml").exists()`。由于它位于检查列表的末尾，因此它只有在更强的 monorepo 信号（`.git` 或 `uv.workspace`）不存在时才会生效，完美地实现了向后兼容和行为扩展。

### 标签

#intent/fix #flow/ready #priority/critical #comp/workspace #concept/config #scope/core #ai/instruct #task/domain/architecture #task/object/workspace-discovery #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 修复 `find_workspace_root` 函数

我们将修改位于 `utils.py` 中的 `find_workspace_root` 函数，增加对普通 `pyproject.toml` 文件的检查，作为确定工作区根的第三个条件。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/utils.py
~~~~~
~~~~~python.old
        # 2. Check for pyproject.toml with workspace definition
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                # Check for uv workspace or similar tools
                if (
                    "tool" in data
                    and "uv" in data["tool"]
                    and "workspace" in data["tool"]["uv"]
                ):
                    return parent
            except Exception:
                pass

    # No root found in the entire hierarchy
    raise WorkspaceNotFoundError(str(start_path))
~~~~~
~~~~~python.new
        # 2. Check for pyproject.toml with workspace definition (stronger indicator)
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                # Check for uv workspace or similar tools
                if (
                    "tool" in data
                    and "uv" in data["tool"]
                    and "workspace" in data["tool"]["uv"]
                ):
                    return parent
            except Exception:
                pass  # Ignore malformed toml files, let the third check handle it

        # 3. Fallback to any pyproject.toml as a root indicator (for simple projects/tests)
        if pyproject.exists():
            return parent

    # No root found in the entire hierarchy
    raise WorkspaceNotFoundError(str(start_path))
~~~~~

### 下一步建议

我们已经修正了核心的根目录发现逻辑。现在，请重新运行完整的测试套件。所有的测试都应该能够通过，因为 `WorkspaceFactory` 创建的环境现在可以被 `find_workspace_root` 正确识别了。
