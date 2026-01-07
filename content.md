好的，既然测试已经全部通过，这意味着 `stitcher cov` 功能已经达到了生产级标准：计算准确、逻辑严密且输出美观对齐。

我将生成一个 `[COMMIT]` 计划，将这次开发任务的所有成果——包括核心逻辑、CLI 接口、国际化支持以及集成测试——作为一个完整的逻辑单元提交到仓库。

## [COMMIT] feat: 实现 `stitcher cov` 命令用于文档覆盖率报告

### 用户需求

实现一个类似于 `pytest-cov` 的命令，用于分析并报告项目中公开 API 的文档覆盖率。

### 评论

这是一个提升开发者体验（DX）的重要里程碑。通过将文档完整性量化为覆盖率指标，我们为项目维护者提供了一个清晰的质量衡量工具。

### 目标

1.  提交 `stitcher-spec` 中增强的 `ModuleDef` 逻辑（支持公开符号识别和模块可文档化检查）。
2.  提交 `stitcher-application` 中的 `CoverageRunner` 核心引擎。
3.  提交 `stitcher-cli` 中新增的 `cov` 命令及其关联工厂配置。
4.  提交 `stitcher-common` 中新增的中英文国际化资源。
5.  提交完整的集成测试套件，验证覆盖率计算和输出对齐。

### 基本原理

该功能通过 `CoverageRunner` 协调 `ScannerService`（解析代码结构）和 `DocumentManager`（检查 YAML 文档存储）。它动态计算列宽以确保在各种终端环境下的完美对齐，并自动排除仅包含私有成员的“非文档化”模块。

### 标签

#intent/build #flow/ready #comp/cli #comp/application #comp/spec #concept/ui #scope/dx #task/domain/cli #task/object/coverage-report #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有变更

我们将所有相关文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-spec/src/stitcher/spec/models.py
packages/stitcher-application/src/stitcher/app/types.py
packages/stitcher-application/src/stitcher/app/runners/coverage.py
packages/stitcher-application/src/stitcher/app/runners/__init__.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-cli/src/stitcher/cli/commands/cov.py
packages/stitcher-cli/src/stitcher/cli/main.py
packages/stitcher-cli/tests/integration/test_coverage_command.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/command.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/command.json
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: implement 'stitcher cov' for documentation coverage reporting

Introduces a new 'cov' command that provides a file-level coverage report of documentation stored in .stitcher.yaml files, inspired by pytest-cov.

Core improvements:
- spec: Enhanced ModuleDef with 'get_public_documentable_fqns' and refined 'is_documentable' logic to focus strictly on public APIs.
- application: Created CoverageRunner that aggregates documentation stats across scanned modules.
- cli: Added 'cov' subcommand with professional, dynamically-aligned tabular output.
- i18n: Added English and Chinese help strings for the new command.
- tests: Added comprehensive integration tests covering various coverage scenarios and UI alignment.

This feature allows teams to quantify documentation health and identify missing documentation in a standardized way.
~~~~~

### 下一步建议

- **CI 集成**: 可以考虑将 `stitcher cov` 集成到 CI 流程中，如果覆盖率低于某个阈值，则使构建失败。
- **输出格式扩展**: 未来可以支持 `--cov-report=json` 或 `xml` 格式，以便与其他质量分析工具（如 SonarQube）集成。
- **文档更新**: 记得在项目的 README 或用户手册中添加 `cov` 命令的使用说明。
