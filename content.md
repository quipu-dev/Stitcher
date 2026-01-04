好的，我们已经完成了“引入纯净应用层”提案的第一阶段，并修复了 `pump` 流程中的路径处理 Bug。现在我将生成一个 `[COMMIT]` 计划来提交这些更改。

## [COMMIT] refactor(app): 解耦 run_pump 的 UI 逻辑并修复冗余报告

### 用户需求
将之前的重构（解耦应用层与 CLI 交互）以及针对 `pump` 冗余文件报告的修复固化到 Git 历史中。

### 评论
这次提交不仅提升了架构的纯净度，还通过引入高质量的集成测试解决了 TUI/CLI 交互中一个隐蔽的 Bug。这标志着我们将应用层定义为“无状态服务层”的努力取得了阶段性成功。

### 目标
1.  提交对 `StitcherApp.run_pump` 的解耦修改。
2.  提交对 `PumpRunner.run` 的修复逻辑（返回绝对路径列表）。
3.  包含新创建的交互测试文件。

### 基本原理
遵循原子提交原则，将所有相关的重构、修复和测试代码作为一个逻辑单元进行提交。这有助于保持 Git 历史的清晰，并使未来的审计或回滚更加容易。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/runtime #comp/cli #comp/tests #scope/core 
#ai/instruct 
#task/domain/architecture #task/object/application-layer #task/action/decouple-ui 
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有涉及的文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/src/stitcher/app/runners/pump.py
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(app): decouple CLI logic from run_pump and fix redundancy reporting

- Cleaned up `StitcherApp.run_pump` by removing direct dependencies on `typer`, moving orchestration logic to the CLI layer.
- Fixed `PumpRunner` to properly detect and return redundant files after a successful pump operation.
- Ensured that reported redundant files use absolute paths to satisfy downstream service requirements.
- Added a robust integration test `test_pump_prompts_for_strip_when_redundant` to verify the interactive strip workflow.

This completes the first phase of the 'Pure Application Layer' proposal.
~~~~~

### 下一步建议
- **架构审计**: 虽然 `pump` 已经完成，但可以继续检查 `generate` 或 `init` 等命令，看是否还有类似的小型 UI 泄露。
- **完善测试**: 基于本次建立的 `Mock Handler Factory` 模式，可以为 `check` 命令也添加类似的交互式回归测试，确保其在各种冲突场景下的表现符合预期。
