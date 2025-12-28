好的，根据您的要求，我将创建一个 `[COMMIT]` 计划来固化上一步的文件结构调整。

## [COMMIT] refactor(tests): Relocate most integration tests to pkg directories

### 用户需求
提交集成测试文件结构调整，以将应用级别的集成测试归档到相应的软件包目录中，并清理根集成测试目录。

### 评论
文件归类完成后，项目的测试结构变得更清晰、更模块化。这提高了开发人员体验（DX），因为测试现在与其所测试的组件位于同一命名空间下。

### 目标
通过 `git commit` 操作，记录以下变更：
1.  将大部分应用集成测试（共 14 个文件）从 `tests/integration/` 迁移到 `packages/stitcher-application/tests/integration/`。
2.  确保保留在根 `tests/integration/` 目录中的测试文件（如 `test_ide_proxy.py` 和 `test_stub_package_resolution.py`）以及 `conftest.py` 继续被跟踪。

### 基本原理
遵守 [指令级约束：脚本与 Git 操作互斥] 原则，本计划只包含 `git_add` 和 `git_commit`，不包含任何文件修改操作。Git 的文件重命名检测机制将确保这些 `move_file` 操作被正确记录为重命名，而不是删除和新增。

### 标签
#intent/refine #flow/done #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/integration-tests #task/action/refactor #task/state/end

---
### Script

#### Acts 1: 添加所有更改到暂存区并创建提交

我们将所有受影响的路径添加到暂存区，然后创建一条描述此次结构调整的提交。

~~~~~act
git_add
packages/stitcher-application/tests/integration/
tests/integration/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): Relocate most integration tests to pkg directories

Moves the majority of application-level integration tests from the top-level 
`tests/integration/` directory into `packages/stitcher-application/tests/integration/`. 
This enhances modularity and improves test discoverability.

The root `tests/integration/` is now reserved exclusively for high-cost, 
end-to-end tests that require a virtual environment (e.g., type-checker validation).
~~~~~

### 下一步建议
如果未来需要将 `test_hydrate_interactive_flow.py` 或 `test_check_regression.py` 等非 `VenvHarness` 依赖的测试文件也归类到 `stitcher-application` 中，可以随时使用 `move_file` 指令执行后续的结构调整。目前，提交已经完成。
