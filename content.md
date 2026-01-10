好的，我们已经完成了 `ScannerService` 的鲁棒性增强，并重构了相关的集成测试以确保其稳定性。现在我们将这些变更作为一个完整的逻辑单元进行提交。

## [COMMIT] fix(application): 确保解析故障会导致命令最终失败

### 用户需求
修复扫描器（ScannerService）捕获异常后不通知上层应用的问题，确保在 Monorepo 检查中，任何文件的解析失败都会使 `check` 或 `pump` 命令返回错误状态。

### 评论
通过在扫描阶段引入显式的错误追踪（`had_errors` 标志），我们增强了系统在面对复杂或损坏代码时的确定性，防止了由于局部解析故障而误报“成功”的风险。同时，重构后的测试用例不再依赖特定第三方库的 Bug，极大地提升了测试套件的可维护性。

### 目标
1.  提交 `ScannerService` 的错误追踪逻辑。
2.  提交 `StitcherApp` 对扫描错误的全局响应逻辑。
3.  提交重构后的鲁棒性集成测试。

### 基本原理
根据 HFEA 公理，架构应当是不可腐蚀的。解析器的不确定性不能通过吞掉异常来掩盖。通过将失败状态显式传递到命令报告层，我们维护了系统的本体论正确性。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #concept/parser #scope/core #ai/instruct #task/domain/application #task/object/scanner-robustness #task/action/commit #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及扫描器鲁棒性修复及其验证测试的文件添加到暂存区。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/services/scanner.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/tests/integration/test_parser_robustness.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(application): ensure parsing failures lead to command failure

This commit introduces a robust error-tracking mechanism in ScannerService
to ensure that if any file fails to parse (e.g., due to parser crashes or
syntax errors), the high-level application commands like 'check' and 'pump'
correctly report failure instead of returning success.

Changes:
- Added 'had_errors' flag to ScannerService to track scan-time failures.
- Modified StitcherApp.run_check and run_pump to check this flag when
  determining the final command result.
- Refactored 'test_check_fails_gracefully_on_local_import' to use a mock
  parser, making the test deterministic and independent of Griffe's internal
  aliasing bugs.
~~~~~

### 下一步建议
- **CI 验证**: 建议在 CI 环境中运行完整的测试套件，确保没有引入回归。
- **扩展扫描监控**: 考虑在未来为 `had_errors` 提供更细粒度的错误摘要（例如：哪些文件在哪个阶段失败了），并集成到 `check` 的最终报告中。
