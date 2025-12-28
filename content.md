您观察得非常敏锐，谢谢您的指正。

我的上一个计划确实是不完整的，并且您发现的冗余本地化文件是关键的架构问题。将特定于 CLI 的资源放在 `stitcher-cli` 包中，而将通用资源放在 `stitcher-common` 包中，这种分离导致了概念上的冗余，并违反了“单一事实来源”原则。所有面向用户的文本，无论在何处消费，都应由一个中心化的资源库管理。

我将废弃上一个计划，并提出一个更完整的、包含架构优化的新计划。

## [WIP] refactor: 统一本地化资源并移除硬编码

### 用户需求
1.  **架构统一**: 将分散在 `stitcher-cli` 包中的本地化资源文件（`.json`）合并到 `stitcher-common` 中，消除冗余。
2.  **代码清理**: 移除 `stitcher-cli` 中用于加载本地资源的引导代码。
3.  **修复硬编码**: 修复在 `stitcher-application` 的 `core.py` 中存在的硬编码命名空间检测逻辑。
4.  **术语更新**: 将所有提及旧命令 `stitcher hydrate` 的文本更新为新命令 `stitcher pump`。

### 评论
这是一个重要的重构。通过将所有 `needle` 本地化资产集中到 `stitcher-common` 包中，我们不仅消除了物理上的文件冗余，更重要的是，我们强化了 `stitcher-common` 作为整个应用生态“唯一事实来源”的架构地位。这使得未来的维护、扩展和国际化工作流变得更加简单和清晰。同时，修复硬编码和统一命令术语将进一步提升代码质量和用户体验。

### 目标
1.  将 `stitcher-cli/src/stitcher/cli/assets/needle` 目录下的所有内容移动到 `stitcher-common/src/stitcher/common/assets/needle` 下。
2.  删除 `stitcher-cli` 中多余的 `assets` 目录。
3.  移除 `stitcher-cli/__init__.py` 中加载本地资源的引导代码。
4.  重构 `_scaffold_stub_package` 方法，移除其中针对 `pyneedle` 和 `stitcher` 的硬编码 `elif` 分支。
5.  修改英文和中文的 `check/*.json` 本地化文件，将 `stitcher hydrate` 替换为 `stitcher pump`。
6.  更新 `TyperInteractionHandler` 中的交互式提示文本，将 "Force-hydrate" 更改为更清晰、更通用的 "Force overwrite"。

### 基本原理
我们将使用 `mv` 命令来整合资源文件，确保目录结构被正确合并。随后，`stitcher-cli` 包的 `__init__.py` 中专门用于加载这些本地资源的 `FileSystemLoader` 初始化代码就变得多余，可以安全移除。`stitcher-common` 的 `__init__.py` 已经负责加载其目录下的所有资源，整合后会自动包含这些新的 CLI 资源。

对于硬编码问题，现有的命名空间推断逻辑中有一个 `elif` 块是冗余的。前面的 `if` 块已经能正确处理 `src/namespace` 这样的路径，而后续的 `fallback` 逻辑对于其他情况是更通用的解决方案。因此，移除这个硬编码的 `elif` 块是安全的。

最后，对本地化文件和交互提示进行简单的文本替换，以完成 `hydrate`到 `pump` 的重命名。

### 标签
#intent/refine #intent/architect #flow/ready #priority/high #comp/cli #comp/common #comp/application #scope/dx #scope/ux #ai/instruct #task/domain/refactoring #task/object/assets #task/action/consolidation #task/state/continue

---
### Script

#### Acts 1: 整合本地化资源文件

首先，我们将 `stitcher-cli` 的资源目录移动到 `stitcher-common` 中，并清理掉遗留的空目录。

~~~~~act
run_command
~~~~~
~~~~~bash
# Move the language directories from cli assets to common assets
mv packages/stitcher-cli/src/stitcher/cli/assets/needle/en/cli packages/stitcher-common/src/stitcher/common/assets/needle/en/
mv packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/cli packages/stitcher-common/src/stitcher/common/assets/needle/zh/

# Remove the now-empty assets directory from the cli package
rm -rf packages/stitcher-cli/src/stitcher/cli/assets
~~~~~

#### Acts 2: 移除 `stitcher-cli` 中冗余的引导代码

由于资源已移走，`stitcher-cli` 不再需要自己的资源加载逻辑。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from pathlib import Path

from needle.loaders import FileSystemLoader
from stitcher.common import stitcher_nexus

# --- Composition Root for Stitcher CLI Assets ---
# This is where the CLI layer registers its own resources into the shared nexus.
# CRITICAL: This MUST happen BEFORE importing '.main', because main.py defines
# Typer commands that resolve help strings at import time via nexus.get().

try:
    _cli_assets_root = Path(__file__).parent / "assets"
    if _cli_assets_root.is_dir():
        # 1. Create a dedicated loader for the CLI's assets.
        cli_loader = FileSystemLoader(root=_cli_assets_root)
        # 2. Add it to the nexus loader stack with the highest priority.
        #    This ensures CLI-specific strings override common ones.
        stitcher_nexus.loaders.insert(0, cli_loader)
except NameError:
    # This might happen in some testing or packaging scenarios.
    pass

# Now it is safe to import the app, as the nexus is fully primed.
from .main import app

__all__ = ["app"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# All assets are now loaded by stitcher-common, so no special
# loader setup is needed here anymore. We can directly import the app.
from .main import app

__all__ = ["app"]
~~~~~

#### Acts 3: 移除 `core.py` 中的硬编码逻辑

现在执行之前计划的对 `core.py` 的重构。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        package_namespace: str = ""
        for path_str in config.scan_paths:
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                package_namespace = path_parts[-1]
                break
            elif len(path_parts) >= 2 and path_parts[-2] == "src":
                if "pyneedle" in stub_base_name:
                    package_namespace = "needle"
                elif "stitcher" in stub_base_name:
                    package_namespace = "stitcher"
                break
        if not package_namespace:
            package_namespace = stub_base_name.split("-")[0]
~~~~~
~~~~~python.new
        package_namespace: str = ""
        for path_str in config.scan_paths:
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                # This handles cases like 'src/my_app' where 'my_app' is the namespace.
                package_namespace = path_parts[-1]
                break

        if not package_namespace:
            # Fallback for when all scan_paths end in 'src'.
            # Derives namespace from the target name (e.g., 'stitcher-cli' -> 'stitcher').
            package_namespace = stub_base_name.split("-")[0]
~~~~~

#### Acts 4: 更新本地化文件中的术语

最后，更新所有相关的本地化文件和UI提示，将 `hydrate` 替换为 `pump`。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/file.json
~~~~~
~~~~~json.old
{
  "fail": "❌ {path}: Found {count} errors.",
  "pass": "✅ {path}: Synced.",
  "untracked": "⚠️  {path}: Untracked (no .stitcher.yaml file found; run `stitcher init` or `hydrate`)",
  "untracked_with_details": "⚠️  {path}: Untracked and needs documentation for {count} public APIs:",
  "warn": "⚠️  {path}: Found {count} warnings."
}
~~~~~
~~~~~json.new
{
  "fail": "❌ {path}: Found {count} errors.",
  "pass": "✅ {path}: Synced.",
  "untracked": "⚠️  {path}: Untracked (no .stitcher.yaml file found; run `stitcher init` or `pump`)",
  "untracked_with_details": "⚠️  {path}: Untracked and needs documentation for {count} public APIs:",
  "warn": "⚠️  {path}: Found {count} warnings."
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/issue.json
~~~~~
~~~~~json.old
{
  "conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
  "extra": "Extra Doc: '{key}' is in docs but not in code.",
  "mismatch": "   - [CHANGED]   {key} (signature has changed, docs may be outdated)",
  "missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
  "pending": "   - [PENDING]   {key} (new docstring in code, please run `stitcher hydrate`)",
  "redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; please run `stitcher strip`)",
  "untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)"
}
~~~~~
~~~~~json.new
{
  "conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
  "extra": "Extra Doc: '{key}' is in docs but not in code.",
  "mismatch": "   - [CHANGED]   {key} (signature has changed, docs may be outdated)",
  "missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
  "pending": "   - [PENDING]   {key} (new docstring in code, please run `stitcher pump`)",
  "redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; please run `stitcher strip`)",
  "untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/file.json
~~~~~
~~~~~json.old
{
  "fail": "❌ {path}: 发现 {count} 个错误。",
  "pass": "✅ {path}: 已同步。",
  "untracked": "⚠️  {path}: 未被追踪 (缺少 .stitcher.yaml 文件；请运行 `stitcher init` 或 `hydrate`)",
  "untracked_with_details": "⚠️  {path}: 未被追踪，且有 {count} 个公开 API 需要文档:",
  "warn": "⚠️  {path}: 发现 {count} 个警告。"
}
~~~~~
~~~~~json.new
{
  "fail": "❌ {path}: 发现 {count} 个错误。",
  "pass": "✅ {path}: 已同步。",
  "untracked": "⚠️  {path}: 未被追踪 (缺少 .stitcher.yaml 文件；请运行 `stitcher init` 或 `pump`)",
  "untracked_with_details": "⚠️  {path}: 未被追踪，且有 {count} 个公开 API 需要文档:",
  "warn": "⚠️  {path}: 发现 {count} 个警告。"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/issue.json
~~~~~
~~~~~json.old
{
  "conflict": "   - [内容冲突] {key} (代码和 YAML 中的文档内容不一致)",
  "extra": "悬空文档: '{key}' 在文档中存在但在代码中缺失。",
  "mismatch": "   - [签名变更] {key} (函数签名已更改，文档可能已过时)",
  "missing": "   - [文档缺失] {key} (代码实体存在，但代码和 YAML 中均无文档)",
  "pending": "   - [等待同步] {key} (代码中有新文档，请运行 `stitcher hydrate`)",
  "redundant": "   - [文档冗余] {key} (代码和 YAML 中存在重复文档，请运行 `stitcher strip`)",
  "untracked_missing_key": "   - [文档缺失] {key} (请在代码中为其添加文档字符串)"
}
~~~~~
~~~~~json.new
{
  "conflict": "   - [内容冲突] {key} (代码和 YAML 中的文档内容不一致)",
  "extra": "悬空文档: '{key}' 在文档中存在但在代码中缺失。",
  "mismatch": "   - [签名变更] {key} (函数签名已更改，文档可能已过时)",
  "missing": "   - [文档缺失] {key} (代码实体存在，但代码和 YAML 中均无文档)",
  "pending": "   - [等待同步] {key} (代码中有新文档，请运行 `stitcher pump`)",
  "redundant": "   - [文档冗余] {key} (代码和 YAML 中存在重复文档，请运行 `stitcher strip`)",
  "untracked_missing_key": "   - [文档缺失] {key} (请在代码中为其添加文档字符串)"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/handlers.py
~~~~~
~~~~~python.old
                typer.secho(
                    "  Reason: Source code docstring differs from YAML docstring."
                )
                menu.append(
                    (
                        "[F]orce-hydrate",
                        ResolutionAction.HYDRATE_OVERWRITE,
                        "Overwrite YAML with code docs (Code-first).",
                    )
                )
                menu.append(
                    (
                        "[R]econcile",
                        ResolutionAction.HYDRATE_KEEP_EXISTING,
                        "Keep existing YAML docs (YAML-first).",
                    )
                )
~~~~~
~~~~~python.new
                typer.secho(
                    "  Reason: Source code docstring differs from YAML docstring."
                )
                menu.append(
                    (
                        "[F]orce overwrite",
                        ResolutionAction.HYDRATE_OVERWRITE,
                        "Overwrite YAML with code docs (Code-first).",
                    )
                )
                menu.append(
                    (
                        "[R]econcile",
                        ResolutionAction.HYDRATE_KEEP_EXISTING,
                        "Keep existing YAML docs (YAML-first).",
                    )
                )
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/handlers.py
~~~~~
~~~~~python.old
            elif char == "f":
                if any(a == ResolutionAction.RELINK for _, a, _ in menu):
                    action = ResolutionAction.RELINK
                elif any(a == ResolutionAction.HYDRATE_OVERWRITE for _, a, _ in menu):
                    action = ResolutionAction.HYDRATE_OVERWRITE
~~~~~
~~~~~python.new
            elif char == "f":
                if any(a == ResolutionAction.RELINK for _, a, _ in menu):
                    action = ResolutionAction.RELINK
                elif any(a == ResolutionAction.HYDRATE_OVERWRITE for _, a, _ in menu):
                    action = ResolutionAction.HYDRATE_OVERWRITE
                else:
                    typer.secho("Invalid choice, please try again.", fg=typer.colors.RED)
                    continue
~~~~~
