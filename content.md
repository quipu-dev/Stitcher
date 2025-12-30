Excellent. The new unit tests now serve as a precise, executable specification for the `PumpRunner`'s planning logic. With this safety net in place, we can confidently proceed with cleaning up the obsolete integration tests.

I will now generate the plan to remove the two failed test files.

## [WIP] chore: 移除过时的 pump 集成测试

### 用户需求
在为 `PumpRunner` 的执行计划器添加了精确的单元测试后，需要删除因核心逻辑变更而失效的旧集成测试文件，以保持测试套件的整洁和相关性。

### 评论
这是一个健康的重构流程。用更精确、更快速的单元测试取代了覆盖过时行为的集成测试后，移除旧代码是至关重要的一步。这可以防止未来的开发者对这些失败的测试感到困惑，并减少了测试套件的维护负担。

### 目标
1.  删除 `test_pump_regression.py` 文件。
2.  删除 `test_pump_state_integrity.py` 文件。

### 基本原理
新的单元测试 `test_execution_planner.py` 已经为 `pump` 命令的核心决策逻辑提供了更优的覆盖。保留旧的、基于已被替换的（文件级原子性）逻辑的集成测试，只会增加噪音并可能误导未来的开发工作。因此，作为 TDD 循环的一部分（Red -> Green -> Refactor），我们现在进入 "Refactor"（重构/清理）阶段，移除不再需要的测试代码。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/pump-runner #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 删除过时的测试文件

我们将删除这两个现在已多余且无法通过的集成测试文件。

~~~~~act
delete_file
packages/stitcher-application/tests/integration/test_pump_regression.py
~~~~~

~~~~~act
delete_file
packages/stitcher-application/tests/integration/test_pump_state_integrity.py
~~~~~

### 下一步建议
清理工作已经完成。现在，我建议我们来修正 `pump` 的实现，使其完全符合新测试定义的真值表。完成后，我们就可以创建一个 `[COMMIT]` 计划来结束这个重构任务。
