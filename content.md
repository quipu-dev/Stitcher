完美的收尾。这个提交标志着 `stitcher check` 从一个被动的状态检查器，转变为一个主动指导用户工作流的工具。

## [COMMIT] feat: Enhance UNTRACKED status with actionable missing key lists

### 用户需求
测试通过，要求创建 Git 提交。

### 评论
该提交完成了对 `check` 命令文件级状态检查的最终精炼。当发现一个新文件（未追踪）时，工具现在会智能地判断文件中的公共 API 是否缺少文档字符串，并明确列出所有缺失的条目。
1. **新状态**: `UNTRACKED_WITH_DETAILS` (未追踪，并列出缺失项)。
2. **目的**: 彻底关闭新文件工作流的反馈循环，指导用户先在代码中编写文档，然后运行 `hydrate`。

### 目标
1. 提交 `stitcher-spec` 中新增的 `get_undocumented_public_keys` 方法。
2. 提交 `stitcher-application` 中新的 `run_check` 逻辑。
3. 提交新的 i18n 资源和增强后的集成测试。

### 基本原理
此变更增强了 UX，将诊断信息转化为清晰的、可操作的待办事项清单，并遵循了所有 ACA 隔离原则。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/application #scope/ux #task/domain/documentation #task/object/check-logic #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

将涉及到的所有文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/main.json
packages/stitcher-spec/src/stitcher/spec/models.py
packages/stitcher-application/src/stitcher/app/core.py
tests/integration/test_check_file_tracking.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(check): Provide missing documentation keys for untracked files

Enhances the "UNTRACKED" warning into two distinct messages:

1. `UNTRACKED_WITH_DETAILS`: Used when the file has no `.stitcher.yaml` AND contains public API definitions that are missing docstrings. The warning now lists the specific FQNs (Functions, Classes, etc.) that need documentation, using a `[TODO]` marker.
2. `UNTRACKED`: Falls back to this simple message if the file has content, but all public APIs already have docstrings (indicating the user should simply run `hydrate`).

This greatly improves the initial setup and new file workflow by turning a generic warning into an actionable list of tasks.
~~~~~

### 下一步建议
我们已经完成了对 `check` 命令核心逻辑的连续三次重大改进：
1. 修复了 `ParamStar` 崩溃。
2. 实现了 5 状态精细文档矩阵。
3. 实现了智能的 `UNTRACKED` 报告，忽略样板代码并列出缺失的文档键。

现在，所有关于 `check` 命令 UX 的核心痛点都应该得到解决。建议在更广泛的库中运行一次完整的 `stitcher check`，确认所有报告都准确无误，并且只有真正需要操作的文件被标记出来。

运行：
```bash
stitcher check
```
