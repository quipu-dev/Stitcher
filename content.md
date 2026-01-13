## [WIP] fix: Complete the semantic loop for architecture violations

### 错误分析
由于 `L.check.architecture.circular_dependency` 指针对应的 i18n 模板被错误地放置在了 `check/issue.json`（应为 `check/architecture.json`），导致 `CheckReporter` 输出的是原始字符串而非格式化后的消息。此外，CLI 的 `TyperInteractiveRenderer` 尚未在语义上识别此类违例。

### 用户需求
确保 `stitcher check` 发现的循环依赖错误能够以正确、美观、且符合 i18n 规范的格式显示在终端。

### 目标
1.  删除 `check/issue.json` 中错误的架构相关条目。
2.  创建 `packages/stitcher-common/src/stitcher/common/assets/needle/{en,zh}/check/architecture.json` 并填入模板。
3.  更新 `packages/stitcher-cli/src/stitcher/cli/interactive.py` 的 `reason_map`，使其支持架构错误的语义解释。

### 标签
#intent/fix #flow/ready #priority/critical #comp/common #comp/cli #concept/i18n #scope/ux #ai/refine #task/domain/cli #task/object/output-streams #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正 i18n 资源布局

我们首先移除错误的定义，并为 `architecture` 类别建立专用的 json 文件。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/issue.json
~~~~~
~~~~~json.old
  "untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)",
  "architecture.circular_dependency": "   - [ARCH]      {key}: Circular dependency detected: {cycle}"
}
~~~~~
~~~~~json.new
  "untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/issue.json
~~~~~
~~~~~json.old
  "untracked_missing_key": "   - [文档缺失]  {key} (请在代码中为其添加文档字符串)",
  "architecture.circular_dependency": "   - [架构问题]  {key}: 检测到循环依赖: {cycle}"
}
~~~~~
~~~~~json.new
  "untracked_missing_key": "   - [文档缺失]  {key} (请在代码中为其添加文档字符串)"
}
~~~~~

~~~~~act
run_command
~~~~~
~~~~~bash
touch packages/stitcher-common/src/stitcher/common/assets/needle/en/check/architecture.json
touch packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/architecture.json
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/architecture.json
~~~~~
~~~~~json
{
  "circular_dependency": "   - [ARCH]      {key}: Circular dependency detected: {cycle}"
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/architecture.json
~~~~~
~~~~~json
{
  "circular_dependency": "   - [架构问题]  {key}: 检测到循环依赖: {cycle}"
}
~~~~~

#### Acts 2: 更新 CLI 渲染器语义

我们将 `CircularDependency` 违例添加到 CLI 渲染器的原因映射表中，确保即使未来开启交互式检查，它也能被正确解释。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/interactive.py
~~~~~
~~~~~python.old
        reason_map = {
            L.check.state.signature_drift: L.interactive.reason.signature_drift,
            L.check.state.co_evolution: L.interactive.reason.co_evolution,
            L.check.issue.conflict: L.interactive.reason.doc_content_conflict,
            L.check.issue.extra: L.interactive.reason.dangling_doc,
        }
~~~~~
~~~~~python.new
        reason_map = {
            L.check.state.signature_drift: L.interactive.reason.signature_drift,
            L.check.state.co_evolution: L.interactive.reason.co_evolution,
            L.check.issue.conflict: L.interactive.reason.doc_content_conflict,
            L.check.issue.extra: L.interactive.reason.dangling_doc,
            L.check.architecture.circular_dependency: L.interactive.reason.circular_dependency,
        }
~~~~~

#### Acts 3: 完善交互提示信息

在 `interactive.json` 中补充架构检查的描述模板。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/interactive.json
~~~~~
~~~~~json.old
    "signature_drift": "Reason: Signature has changed, but docs have not (Signature Drift).",
    "co_evolution": "Reason: Both signature and docs have changed (Co-evolution).",
    "doc_content_conflict": "Reason: Source code docstring differs from YAML docstring.",
    "dangling_doc": "Reason: Documentation exists in YAML but not in code (Dangling Doc)."
  },
~~~~~
~~~~~json.new
    "signature_drift": "Reason: Signature has changed, but docs have not (Signature Drift).",
    "co_evolution": "Reason: Both signature and docs have changed (Co-evolution).",
    "doc_content_conflict": "Reason: Source code docstring differs from YAML docstring.",
    "dangling_doc": "Reason: Documentation exists in YAML but not in code (Dangling Doc).",
    "circular_dependency": "Reason: A circular dependency between modules was detected."
  },
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/interactive.json
~~~~~
~~~~~json.old
    "signature_drift": "原因: 签名已变更，但文档未变 (签名漂移)。",
    "co_evolution": "原因: 签名和文档均已变更 (协同演进)。",
    "doc_content_conflict": "原因: 源代码文档字符串与 YAML 文档字符串不一致。",
    "dangling_doc": "原因: 文档存在于 YAML 但代码中不存在 (悬空文档)。"
  },
~~~~~
~~~~~json.new
    "signature_drift": "原因: 签名已变更，但文档未变 (签名漂移)。",
    "co_evolution": "原因: 签名和文档均已变更 (协同演进)。",
    "doc_content_conflict": "原因: 源代码文档字符串与 YAML 文档字符串不一致。",
    "dangling_doc": "原因: 文档存在于 YAML 但代码中不存在 (悬空文档)。",
    "circular_dependency": "原因: 检测到模块之间存在循环依赖。"
  },
~~~~~

### 下一步建议
通过修复 i18n 资源布局和 CLI 语义映射，我们完成了“架构违例”在系统中的语义闭环。现在 `stitcher check` 应该能正确打印带有 `[架构问题]` 前缀和完整路径的错误信息了。

完成此修复后，建议再次运行 `stitcher check`（如用户提供的 XML 所示），观察格式化后的输出。如果一切正常，我们将正式结束 Phase 2 并再次尝试提交。
