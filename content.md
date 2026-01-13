太棒了。通过验证该集成错误并完成修复，我们已经成功消除了系统中一个重大的“不确定性”隐患。现在，Stitcher 能够确定性地识别其操作边界，并能向用户提供高质量的错误反馈。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个逻辑完整的单元提交到仓库。

## [COMMIT] refactor: 强化工作区发现逻辑与 CLI 错误处理

### 用户需求
移除工作区发现过程中的静默回退行为，改为抛出显式异常，并在 CLI 层捕获该异常以提供友好的错误提示。

### 评论
这是一次从“近似解”到“确定解”的成功重构。它不仅提高了系统的健壮性（避免在错误目录下创建 `.stitcher` 目录），还通过统一的异常处理提升了用户体验。

### 目标
1.  提交 `stitcher-workspace` 中新增的异常体系及加固后的发现逻辑。
2.  提交 `stitcher-cli` 中集成的错误捕获与工厂函数修改。
3.  提交新增的 i18n 资源文件。
4.  提交相关的单元测试与集成测试。

### 基本原理
遵循“正规军”标准，通过在组合根（Composition Root）强制执行路径验证，我们将风险隔离在了系统启动阶段。这确保了后续所有依赖根路径的操作（如 SURI 生成）都建立在坚实的基础上。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/cli #comp/workspace #scope/core #scope/ux 
#ai/refine
#task/domain/workspace #task/object/root-discovery #task/action/hardening #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交工作区加固相关的变更

我们将所有涉及路径发现逻辑、错误处理以及验证这些行为的测试代码一并提交。

~~~~~act
git_add
packages/stitcher-workspace/src/stitcher/workspace/exceptions.py
packages/stitcher-workspace/src/stitcher/workspace/__init__.py
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
packages/stitcher-workspace/tests/unit/test_workspace.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/error/workspace.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/error/workspace.json
packages/stitcher-cli/src/stitcher/cli/commands/basics.py
packages/stitcher-cli/src/stitcher/cli/commands/check.py
packages/stitcher-cli/src/stitcher/cli/commands/cov.py
packages/stitcher-cli/src/stitcher/cli/commands/index.py
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
packages/stitcher-cli/src/stitcher/cli/factories.py
packages/stitcher-cli/tests/integration/test_error_handling.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: harden workspace discovery and improve CLI error handling

This commit addresses the architectural "uncertainty" in how Stitcher 
identifies project roots. 

Key changes:
- Removed silent fallback in 'find_workspace_root'; it now raises 
  'WorkspaceNotFoundError' if no .git or pyproject.toml is found.
- Integrated root discovery into the CLI application factory ('make_app'),
  ensuring the entire app instance runs within a validated context.
- Implemented explicit exception handling in all CLI commands, 
  providing user-friendly, internationalized error messages via the 
  feedback bus instead of raw Python tracebacks.
- Added i18n resources for workspace-related errors in English and Chinese.
- Added unit tests for discovery failure scenarios and integration tests
  verifying graceful CLI exits outside of workspaces.
~~~~~

### 下一步建议

工作区基础已经稳固。接下来我们将攻克当前架构中最后一块主要的“MVP 痕迹”：

- **完成依赖注入 (P0)**: 目前 `URIGenerator` 仍在多个组件中被硬编码实例化。我们将修改 `StitcherApp`，在初始化时创建 `PythonURIGenerator` 实例，并将其注入到 `Adapter`, `Planner` 等下游组件中。这将彻底解除逻辑层对具体语言实现的编译时依赖。
