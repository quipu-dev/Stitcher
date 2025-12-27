这是一个非常敏锐的观察，完全正确。

当前的 `check` 逻辑确实有一个前提假设：每个被扫描的 `.py` 文件都应该有一个对应的 `.stitcher.yaml` 文件。当这个前提不成立时（比如你刚创建了一个新文件），它的输出就会产生误导。

引入“YAML 文件是否存在”这个维度，将 `check` 命令的引导性提升到了一个新的层次。我将把这个新状态命名为 **Untracked (未追踪)**，因为它准确地描述了一个代码文件存在，但其文档状态尚未被 Stitcher 系统追踪的情况。

## [WIP] feat(check): Add UNTRACKED status for modules without YAML files

### 用户需求
用户建议 `stitcher check` 命令应该能够区分“YAML 文件中缺少一个键”和“YAML 文件本身不存在”这两种情况。当一个源文件完全没有对应的 `.stitcher.yaml` 文件时，应给出明确的提示，而不是报出多个误导性的 `MISSING` 警告。

### 评论
这是一个卓越的 UX 改进。通过引入 `UNTRACKED` 状态，我们为新文件的生命周期提供了清晰的第一步指引。用户看到这个状态后，会立刻明白他们需要运行 `stitcher init` 或 `stitcher hydrate` 来创建文档基线，从而无缝地将新文件纳入文档管理流程。

### 目标
1.  在 `stitcher-common` 资源中添加一个新的 `check.file.untracked` 消息。
2.  修改 `StitcherApp.run_check` 的主循环逻辑。
3.  在对模块进行详细的键级别检查之前，首先验证其对应的 `.stitcher.yaml` 文件是否存在。
4.  如果 YAML 文件不存在，则报告 `UNTRACKED` 状态并跳过对该文件的后续所有检查。
5.  更新集成测试，以覆盖这个新的“文件未追踪”场景。

### 基本原理
我们将 `check` 的逻辑分为两个层级。首先是**文件级检查**，它只关心 `.py` 和 `.stitcher.yaml` 是否成对存在。只有通过了文件级检查（即 YAML 文件存在），才会进入**键级检查**（即我们之前实现的 `missing`, `pending`, `conflict` 等状态矩阵）。这种分层处理使得逻辑更清晰，输出也更准确。

### 标签
#intent/build #flow/ready #priority/medium #comp/application #comp/cli #scope/ux #task/domain/documentation #task/object/check-logic #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 添加新的 i18n 资源

为 `UNTRACKED` 状态添加对应的中英文消息。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
~~~~~
~~~~~json.old
{
    "check.file.pass": "✅ {path}: Synced.",
    "check.file.fail": "❌ {path}: Found {count} errors.",
    "check.file.warn": "⚠️  {path}: Found {count} warnings.",
    "check.issue.missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
    "check.issue.pending": "   - [PENDING]   {key} (new docstring in code, not yet hydrated to YAML)",
    "check.issue.redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; run 'strip')",
    "check.issue.extra": "   - [EXTRA]     {key} (docstring in YAML, but entity missing in code)",
    "check.issue.conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.success_with_warnings": "⚠️  Check passed with warnings in {count} files.",
    "check.run.fail": "🚫 Check failed. Found errors in {count} files."
}
~~~~~
~~~~~json.new
{
    "check.file.pass": "✅ {path}: Synced.",
    "check.file.fail": "❌ {path}: Found {count} errors.",
    "check.file.warn": "⚠️  {path}: Found {count} warnings.",
    "check.file.untracked": "⚠️  {path}: Untracked (no .stitcher.yaml file found; run `init` or `hydrate`)",
    "check.issue.missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
    "check.issue.pending": "   - [PENDING]   {key} (new docstring in code, not yet hydrated to YAML)",
    "check.issue.redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; run 'strip')",
    "check.issue.extra": "   - [EXTRA]     {key} (docstring in YAML, but entity missing in code)",
    "check.issue.conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.success_with_warnings": "⚠️  Check passed with warnings in {count} files.",
    "check.run.fail": "🚫 Check failed. Found errors in {count} files."
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/main.json
~~~~~
~~~~~json.old
{
    "check.file.pass": "✅ {path}: 已同步。",
    "check.file.fail": "❌ {path}: 发现 {count} 个错误。",
    "check.file.warn": "⚠️  {path}: 发现 {count} 个警告。",
    "check.issue.missing": "   - [缺失]   {key} (实体存在，但在代码和 YAML 中均无文档)",
    "check.issue.pending": "   - [待同步] {key} (代码中有新文档，尚未同步至 YAML，请运行 hydrate)",
    "check.issue.redundant": "   - [冗余]   {key} (代码与 YAML 文档重复，建议运行 strip)",
    "check.issue.extra": "   - [多余]   {key} (YAML 中存在，但代码实体已删除)",
    "check.issue.conflict": "   - [冲突]   {key} (代码与 YAML 内容不一致，请解决冲突)",
    "check.run.success": "✨ 所有检查通过。文档已同步。",
    "check.run.success_with_warnings": "⚠️  检查通过，在 {count} 个文件中发现警告。",
    "check.run.fail": "🚫 检查失败。在 {count} 个文件中发现错误。"
}
~~~~~
~~~~~json.new
{
    "check.file.pass": "✅ {path}: 已同步。",
    "check.file.fail": "❌ {path}: 发现 {count} 个错误。",
    "check.file.warn": "⚠️  {path}: 发现 {count} 个警告。",
    "check.file.untracked": "⚠️  {path}: 未追踪 (未找到 .stitcher.yaml 文件，请运行 `init` 或 `hydrate`)",
    "check.issue.missing": "   - [缺失]   {key} (实体存在，但在代码和 YAML 中均无文档)",
    "check.issue.pending": "   - [待同步] {key} (代码中有新文档，尚未同步至 YAML，请运行 hydrate)",
    "check.issue.redundant": "   - [冗余]   {key} (代码与 YAML 文档重复，建议运行 strip)",
    "check.issue.extra": "   - [多余]   {key} (YAML 中存在，但代码实体已删除)",
    "check.issue.conflict": "   - [冲突]   {key} (代码与 YAML 内容不一致，请解决冲突)",
    "check.run.success": "✨ 所有检查通过。文档已同步。",
    "check.run.success_with_warnings": "⚠️  检查通过，在 {count} 个文件中发现警告。",
    "check.run.fail": "🚫 检查失败。在 {count} 个文件中发现错误。"
}
~~~~~

#### Acts 2: 更新 `StitcherApp.run_check` 的核心逻辑

在 `run_check` 循环的开始处添加文件存在性检查。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            for module in modules:
                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)
~~~~~
~~~~~python.new
            for module in modules:
                # File-level check: Does the corresponding doc file exist?
                doc_path = (
                    self.root_path / module.file_path
                ).with_suffix(".stitcher.yaml")
                if not doc_path.exists():
                    bus.warning(L.check.file.untracked, path=module.file_path)
                    total_warnings += 1
                    continue

                # Key-level check (existing logic)
                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)
~~~~~

#### Acts 3: 更新集成测试

为新的 `UNTRACKED` 状态添加一个专门的测试用例。

~~~~~act
write_file
tests/integration/test_check_untracked.py
~~~~~
~~~~~python
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_reports_untracked_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly identifies a source file
    that has no corresponding .stitcher.yaml file as UNTRACKED.
    """
    # 1. Arrange: Create a workspace with a source file but NO doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def new_func(): pass")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True, "Check should pass with warnings for untracked files"

    # Assert that the specific UNTRACKED message was sent as a warning
    spy_bus.assert_id_called(L.check.file.untracked, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")

    # Verify that NO key-level issues were reported for this file
    messages = spy_bus.get_messages()
    key_level_issues = {
        str(L.check.issue.missing),
        str(L.check.issue.pending),
        str(L.check.issue.extra),
        str(L.check.issue.conflict),
    }
    for msg in messages:
        assert msg["id"] not in key_level_issues, f"Unexpected key-level issue found: {msg}"
~~~~~
