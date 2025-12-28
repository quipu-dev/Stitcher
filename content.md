好的，重构、重命名以及文档更新已全部完成。现在我们将其作为一个完整的逻辑单元提交到版本控制系统中。

## [COMMIT] refactor(core): rename hydrate/eject to pump/inject and enhance pump workflow

### 用户需求
完成“将 `hydrate` 重命名为 `pump` 并重塑其核心行为”的技术提案。

### 评论
这次重构不仅是简单的名称替换，它建立了一套更符合物理资产转移隐喻的术语体系（Pump/Inject），并显著优化了核心工作流的原子性（通过 Pump 后的交互式剥离确认）。

### 目标
1.  提交所有重命名的 localization 资源。
2.  提交重构后的 `StitcherApp` 核心逻辑和 `PumpResult` 模型。
3.  提交适配新逻辑的 CLI 入口。
4.  提交迁移后的完整集成测试套件。
5.  提交与代码库同步的最新文档资产。

### 基本原理
通过 `[COMMIT]` 计划，我们将这一系列跨越多个包的协同变更永久化，确保项目基础架构的术语统一。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/cli #comp/runtime #comp/docs #comp/tests 
#concept/executor #concept/ui #scope/core #scope/ux #scope/dx 
#ai/instruct 
#task/domain/cli #task/object/command-pump #task/action/rename-and-refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有受影响的包目录添加到暂存区并提交。

~~~~~act
git_add
packages/stitcher-application
packages/stitcher-cli
packages/stitcher-common
packages/stitcher-spec
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): rename hydrate/eject to pump/inject and enhance pump workflow

Renamed the core commands 'hydrate' to 'pump' and 'eject' to 'inject' to establish a more intuitive "asset transfer" mental model.

Key changes:
- Renamed StitcherApp methods: run_hydrate -> run_pump, run_eject -> run_inject.
- Enhanced 'run_pump' to return a 'PumpResult' containing redundant file paths.
- Updated CLI to support an interactive confirmation for stripping docstrings after a successful pump, making the workflow more atomic.
- Updated all localization assets (en/zh) to use the new terminology.
- Migrated and updated the entire test suite to match the new API.
- Fully synchronized all .stitcher.yaml documentation files.

This aligns the implementation with the 'Pumping Metaphor' where docstrings are "pumped" out of source code into the YAML library.
~~~~~

### 下一步建议
- **清理**: 既然核心流程已重塑，可以考虑在 `stitcher init` 逻辑中也加入可选的剥离（strip）确认，以进一步强化 YAML 作为唯一事实来源的地位。
- **扩展**: 接下来可以开始实施 `viewdiff` 提案，以进一步提升 `pump` 和 `check` 过程中的交互决策体验。
