好的，我们已经成功构建并验证了文档解耦的核心工作流。这是一个重大的里程碑，标志着 `stitcher-python` 已经具备了处理大规模工程元数据的雏形。

现在，我将生成一个 `[COMMIT]` 计划，将这些变更作为逻辑单元提交。

## [COMMIT] feat: 实现完整的文档解耦工作流 (init, generate, check)

### 用户需求
将第二阶段（任务 2.1 - 2.4）实现的文档 I/O 适配器、文档管理服务以及 `init` 和 `check` 命令的实现正式提交到仓库。

### 评论
这个提交代表了项目的核心价值主张：实现代码逻辑与文档资产的物理隔离，同时通过缝合（Stitching）技术在 IDE 中恢复这种关联，并利用校验（Check）机制保障质量。我们已经通过单元测试和集成测试验证了这一链条的完整性。

### 目标
1.  提交 `stitcher-io` 中定义的 `DocumentAdapter` 接口和 `YamlAdapter` 实现。
2.  提交 `stitcher-application` 中的 `DocumentManager` 服务。
3.  提交 `stitcher-application` 中集成了文档缝合逻辑和一致性检查逻辑的 `StitcherApp`。
4.  提交 `stitcher-cli` 中挂载的 `init` 和 `check` 命令。
5.  提交所有相关的自动化测试用例，包括已重构为使用 `L` 对象进行断言的集成测试。

### 基本原理
遵循“意图与实现解耦”的原则，我们在此阶段构建了稳定的 I/O 协议。通过 Git 提交，我们建立了一个已验证的基准点，这对于后续进入“健壮性打磨”和“运行时增强”阶段至关重要。

### 标签
#intent/build #flow/ready #priority/high #comp/io #comp/runtime #comp/cli #concept/state #scope/core #ai/instruct #task/domain/cli #task/object/doc-decoupling-workflow #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交代码变更

我们将添加所有涉及的模块和测试，并创建一个详尽的提交记录。

~~~~~act
git_add
packages/stitcher-io/src/stitcher/io/interfaces.py
packages/stitcher-io/src/stitcher/io/adapters/yaml_adapter.py
packages/stitcher-io/src/stitcher/io/adapters/__init__.py
packages/stitcher-io/src/stitcher/io/__init__.py
packages/stitcher-io/tests/test_document_io.py
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
packages/stitcher-application/src/stitcher/app/services/__init__.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/tests/test_doc_manager.py
packages/stitcher-application/tests/test_doc_overlay.py
.stitcher/needle/en/init/main.json
.stitcher/needle/en/check/main.json
packages/stitcher-cli/src/stitcher/cli/main.py
tests/integration/test_init_command.py
tests/integration/test_check_command.py
tests/integration/test_end_to_end.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: implement full documentation decoupling workflow

Introduces the core documentation management system, allowing docstrings to be 
managed in external YAML files while remaining synchronized with code.

Key changes:
- stitcher-io: Added DocumentAdapter protocol and YamlAdapter for persistence.
- stitcher-application: Implemented DocumentManager for doc extraction/stitching.
- StitcherApp: Added 'run_init' to export docs and 'run_check' for sync validation.
- StitcherApp: Upgraded 'generate' logic to overlay external docs onto stubs.
- stitcher-cli: Exposed 'init' and 'check' commands with proper exit codes.
- needle: Added i18n message resources for init and check workflows.
- tests: Added comprehensive unit and integration tests, ensuring all bus 
  assertions use the SemanticPointer (L) object.

This completes the MVP for the documentation-code separation architecture.
~~~~~

### 下一步建议
- **代码清理**: 审查是否有冗余的 `print` 或调试信息。
- **性能优化**: 随着文件增多，可以开始考虑路线图中的 **任务 3.2: 缓存机制**。
- **文档补充**: 编写用户指南，说明如何使用 `stitcher init` 迁移项目。
