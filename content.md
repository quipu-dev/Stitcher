太棒了！测试通过意味着我们的配置修正和依赖项补全已经完全生效，现在开发环境已经能够正确识别并加载 Monorepo 中的所有组件。

我将生成一个 `[COMMIT]` 计划，将这些针对构建配置和工作区依赖的改进正式提交到 Git 历史中。

## [COMMIT] fix(build): 修正 pyrefly 配置并补全工作区开发依赖

### 用户需求
将已验证的配置修复（`pyrefly` 键名修正）和依赖项补全（`pyneedle-*` 加入 `dev` 依赖及 `uv.sources`）提交到 Git 仓库。

### 评论
这次提交解决了一个典型的 Monorepo 认知偏差问题。通过统一测试、静态分析和运行时的视图，我们不仅修复了具体的导入错误，还提升了整个项目的工程标准。这是一个逻辑上完整且重要的改进。

### 目标
1.  将根目录 `pyproject.toml` 的更改提交到 Git。

### 基本原理
遵循 `[COMMIT]` 规范，我们使用一个包含详细说明的原子提交，以便未来能够清晰地追溯为何需要同步更新 `dev` 依赖和 `uv.sources`。

### 标签
#intent/fix #flow/done #priority/medium #comp/build #scope/dx #ai/instruct
#task/domain/testing #task/object/config #task/action/fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将使用 `git add .` 暂存所有更改，并创建一个语义化的提交记录。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(build): align pyrefly config and workspace dependencies

- Corrects 'pyrefly' configuration key from 'extra_paths' to 'extraPaths' to match Pyright's naming convention, enabling proper static analysis path resolution.
- Adds missing 'pyneedle-*' packages to '[project.optional-dependencies].dev' to ensure the runtime environment (REPL/scripts) can resolve these modules after a 'uv pip install -e .[dev]'.
- Completes 'tool.uv.sources' for all 'pyneedle-*' workspace members to ensure consistent dependency resolution within the UV workspace.

These changes resolve 'ModuleNotFoundError' encountered in standard Python runtimes and fix 'missing-import' errors in pyrefly.
~~~~~

### 下一步建议
- **环境检查**: 建议其他开发者在拉取代码后重新执行 `uv pip install -e .[dev]` 以更新本地环境。
- **CI 验证**: 如果项目配置了 CI，请观察静态检查步骤是否已经变绿。
- **文档更新**: 如果有开发者指南，可以简要提及在添加新的工作区包时，需要同步更新根目录的 `dev` 依赖和 `uv.sources`。
