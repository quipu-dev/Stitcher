我将执行一个计划，首先修复两个失败的集成测试以恢复构建状态，然后统一所有本地化文件中的文案风格，确保“缺失”与“待办”等术语的一致性，从而形成闭环的工作流。

## [WIP] fix: 修复集成测试并统一本地化文案风格

### 错误分析
1.  **`test_public_missing_triggers_warning_only` 失败**:
    *   **原因**: 测试旨在验证“公开 API 缺少文档”引发警告。但由于测试设置未创建 `.stitcher.yaml` 文件，系统将其视为 **Untracked File** 场景，触发了 `untracked_missing_key` 警告，而非测试断言预期的 `missing` 警告（该警告仅用于 Tracked 文件）。
    *   **分析**: 这是一个测试设置错误，未能正确模拟“已追踪但缺失文档”的场景。

2.  **`test_generate_with_stub_package_creates_correct_structure` 失败**:
    *   **原因**: 代码已更新为生成符合 PEP 561 标准的 `*-stubs` 目录（例如 `src/my_app-stubs`），但此测试仍断言旧的目录结构（`src/my_app`）。
    *   **分析**: 这是一个过时的测试断言。

### 用户需求
1.  **修复测试**: 确保 CI/CD 流程畅通。
2.  **统一文案**: 审查并统一 `needle` JSON 文件，特别是消除“缺失”与“待办”的区别，建立清晰的工作流闭环。

### 评论
修复测试是基础，文案统一是提升。将两者合并处理是高效的，因为它们都涉及到对系统行为（通过测试验证）和用户界面（通过文案呈现）的理解。统一术语后，用户将不再被“缺失”和“待办”的细微差别困扰，而是明确知道何时该“写文档”，何时该“同步文档”。

### 目标
1.  修正 `test_check_policy.py`，为其添加 `.stitcher.yaml` 以正确触发 Tracked 逻辑。
2.  修正 `test_stub_package.py`，更新断言以匹配 PEP 561 的 `*-stubs` 目录结构。
3.  更新中英文 JSON 文件，实施统一的术语体系（[MISSING], [PENDING], [DANGLING] 等）。

### 基本原理
1.  **测试修复**: 通过修正测试数据和断言，使其与当前代码逻辑（已验证为正确）保持一致。
2.  **文案优化**:
    *   **Untracked Missing Key** (`TODO`) -> **MISSING** (`文档缺失`): 无论文件是否被追踪，代码缺文档就是缺文档，动作都是“去写”。
    *   **Extra** (`EXTRA`) -> **DANGLING** (`定义悬空`): `EXTRA` 容易让人以为是“多余的好东西”，`DANGLING` 更准确地表达了“孤儿文档”的含义。

### 标签
#intent/fix #intent/tune #flow/ready #priority/high #comp/tests #comp/cli #scope/ux #ai/instruct #task/domain/testing #task/object/integration-tests #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 `test_check_policy.py`
为测试用例添加 `.stitcher.yaml` 文件，使其进入 Tracked 逻辑分支，从而正确触发 `check.issue.missing`。

~~~~~act
patch_file
tests/integration/test_check_policy.py
~~~~~
~~~~~python.old
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/lib.py", "def public_api(): pass")
        # No docs created
        .build()
    )
~~~~~
~~~~~python.new
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/lib.py", "def public_api(): pass")
        # Create an empty doc file to ensure the file is tracked
        .with_docs("src/lib.stitcher.yaml", {"__doc__": "Module doc"})
        .build()
    )
~~~~~

#### Acts 2: 修复 `test_stub_package.py`
更新断言以匹配 PEP 561 标准的目录结构 (`my_app-stubs`)。

~~~~~act
patch_file
tests/integration/test_stub_package.py
~~~~~
~~~~~python.old
    pyi_file = src_path / "my_app" / "main.pyi"
    assert pyi_file.is_file()
    assert "def run() -> None:" in pyi_file.read_text()

    py_typed_marker = src_path / "my_app" / "py.typed"
    assert py_typed_marker.is_file()

    # --- Assert pyproject.toml Content ---
    with stub_pyproject.open("rb") as f:
        stub_config = tomllib.load(f)
    assert stub_config["project"]["name"] == "my-test-project-stubs"

    # Assert new Hatchling configuration is present and correct
    hatch_config = stub_config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert hatch_config["packages"] == ["src/my_app"]
~~~~~
~~~~~python.new
    # PEP 561: Source directory should be named <package>-stubs
    pyi_file = src_path / "my_app-stubs" / "main.pyi"
    assert pyi_file.is_file()
    assert "def run() -> None:" in pyi_file.read_text()

    py_typed_marker = src_path / "my_app-stubs" / "py.typed"
    assert py_typed_marker.is_file()

    # --- Assert pyproject.toml Content ---
    with stub_pyproject.open("rb") as f:
        stub_config = tomllib.load(f)
    assert stub_config["project"]["name"] == "my-test-project-stubs"

    # Assert new Hatchling configuration is present and correct
    hatch_config = stub_config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert hatch_config["packages"] == ["src/my_app-stubs"]
~~~~~

#### Acts 3: 统一英文 Check 文案
使用统一的状态标签，并将 `EXTRA` 重命名为更准确的 `DANGLING`。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
~~~~~
~~~~~json
{
    "check.file.pass": "✅ {path}: Synced.",
    "check.file.fail": "❌ {path}: Found {count} errors.",
    "check.file.warn": "⚠️  {path}: Found {count} warnings.",
    "check.file.untracked": "⚠️  {path}: Untracked (no .stitcher.yaml file found; run `stitcher init` or `hydrate`)",
    "check.file.untracked_with_details": "⚠️  {path}: Untracked and needs documentation for {count} public APIs:",
    "check.issue.untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)",
    "check.issue.missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
    "check.issue.pending": "   - [PENDING]   {key} (new docstring in code, please run `stitcher hydrate`)",
    "check.issue.redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; please run `stitcher strip`)",
    "check.issue.extra": "   - [DANGLING]  {key} (docstring in YAML, but entity is missing in code)",
    "check.issue.conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.success_with_warnings": "⚠️  Check passed with warnings in {count} files.",
    "check.run.fail": "🚫 Check failed. Found errors in {count} files."
}
~~~~~

#### Acts 4: 统一中文 Check 文案
将“待办”和“缺失”统一为 `[文档缺失]`，并将 `EXTRA` 译为 `[定义悬空]`。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/main.json
~~~~~
~~~~~json
{
    "check.file.pass": "✅ {path}: 已同步。",
    "check.file.fail": "❌ {path}: 发现 {count} 个错误。",
    "check.file.warn": "⚠️  {path}: 发现 {count} 个警告。",
    "check.file.untracked": "⚠️  {path}: 未被追踪 (缺少 .stitcher.yaml 文件；请运行 `stitcher init` 或 `hydrate`)",
    "check.file.untracked_with_details": "⚠️  {path}: 未被追踪，且有 {count} 个公开 API 需要文档:",
    "check.issue.untracked_missing_key": "   - [文档缺失] {key} (请在代码中为其添加文档字符串)",
    "check.issue.missing": "   - [文档缺失] {key} (代码实体存在，但代码和 YAML 中均无文档)",
    "check.issue.pending": "   - [等待同步] {key} (代码中有新文档，请运行 `stitcher hydrate`)",
    "check.issue.redundant": "   - [文档冗余] {key} (代码和 YAML 中存在重复文档，请运行 `stitcher strip`)",
    "check.issue.extra": "   - [定义悬空] {key} (YAML 中存在，但代码中对应的实体已删除)",
    "check.issue.conflict": "   - [内容冲突] {key} (代码和 YAML 中的文档内容不一致)",
    "check.run.success": "✨ 所有检查通过，文档保持同步。",
    "check.run.success_with_warnings": "⚠️  检查通过，但在 {count} 个文件中发现警告。",
    "check.run.fail": "🚫 检查失败，在 {count} 个文件中发现错误。"
}
~~~~~

#### Acts 5: 更新英文签名检查文案

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/signatures.json
~~~~~
~~~~~json
{
    "check.issue.mismatch": "   - [CHANGED]   {key} (signature has changed, docs may be outdated)"
}
~~~~~

#### Acts 6: 更新中文签名检查文案

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/signatures.json
~~~~~
~~~~~json
{
    "check.issue.mismatch": "   - [签名变更] {key} (函数签名已更改，文档可能已过时)"
}
~~~~~

#### Acts 7: 更新英文 Hydrate 文案

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/hydrate/main.json
~~~~~
~~~~~json
{
    "hydrate.run.start": "💧 Starting hydration process...",
    "hydrate.file.success": "💧 Hydrated {count} new docstrings from: {path}",
    "hydrate.run.complete": "✨ Hydration complete. {count} files updated.",
    "hydrate.run.no_changes": "🤔 No new docstrings found in source code to hydrate.",
    "hydrate.error.conflict": "❌ Conflict in {path} for '{key}': Docstrings differ. Use --force (code-first) or --reconcile (YAML-first) to resolve.",
    "hydrate.run.conflict": "🚫 Hydration aborted due to conflicts in {count} files.",
    "hydrate.info.reconciled": "ℹ️  Ignored {count} conflicts in {path} due to --reconcile mode."
}
~~~~~

#### Acts 8: 更新中文 Hydrate 文案

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/hydrate/main.json
~~~~~
~~~~~json
{
    "hydrate.run.start": "💧 开始补水过程...",
    "hydrate.file.success": "💧 从 {path} 补水了 {count} 个新的文档字符串",
    "hydrate.run.complete": "✨ 补水完成。{count} 个文件已更新。",
    "hydrate.run.no_changes": "🤔 在源代码中未找到可供补水的新文档字符串。",
    "hydrate.error.conflict": "❌ {path} 中 '{key}' 存在内容冲突。请使用 --force (代码优先) 或 --reconcile (YAML优先) 来解决。",
    "hydrate.run.conflict": "🚫 因在 {count} 个文件中存在冲突，补水操作已中止。",
    "hydrate.info.reconciled": "ℹ️  因处于 --reconcile 模式，已忽略 {path} 中的 {count} 个冲突。"
}
~~~~~

### 下一步建议
运行所有测试，确保修复生效且新的文案未破坏任何依赖文本匹配的测试（如果有的话）。随后可以进行更广泛的 Exploratory Testing，检查 CLI 输出的实际视觉效果。
