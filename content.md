好的，我们已经完成了从底层 Bug 修复到测试基础设施重构的一系列工作。代码现在更加健壮，且具备了更好的可测试性。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交到版本控制系统中。

## [COMMIT] fix(common): 修复 bus 导入并引入测试工具包

### 用户需求
1.  修复 `stitcher-common` 中 `bus` 实例导入路径错误导致的 CLI 崩溃。
2.  建立专门的测试工具包 `stitcher-test-utils`。
3.  通过 `MockNeedle` 和 `SpyBus` 统一并简化整个测试套件的 Mock 逻辑。

### 评论
这次提交不仅解决了阻断性的启动错误，还显著提升了项目的测试架构。通过引入领域特定的测试双向（Test Doubles），我们将测试代码与底层的 Mock 实现细节解耦，极大地增强了测试的可读性和维护性。

### 目标
1.  将所有修改过的代码和新创建的 `stitcher-test-utils` 包添加到 Git 暂存区。
2.  创建一个详尽的提交记录，说明修复的内容和引入的新测试工具。

### 基本原理
按照 Quipu 协议，在确认所有重构和修复均已通过测试验证后，我们将这些变更转化为持久的代码记录。使用 `[COMMIT]` 模式确保了我们在执行提交前不会再对文件系统进行任何不稳定的修改。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/common #comp/tests #scope/core #scope/dx #ai/instruct #task/domain/testing #task/object/test-infrastructure #task/action/integration #task/state/end #task/status/completed

---
### Script

#### Acts 1: 提交变更

我们将所有涉及到的文件添加到 Git 暂存区并执行提交。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(common): fix bus import and introduce test utilities

- Corrected the import path for the global 'bus' singleton in stitcher-common, resolving an AttributeError on CLI startup.
- Introduced 'stitcher-test-utils' package to centralize common testing abstractions.
- Implemented 'MockNeedle' to provide a declarative way to mock semantic addressing in tests.
- Implemented 'SpyBus' to enable high-level assertions for message bus activity, decoupling tests from MagicMock implementation details.
- Refactored all integration tests and message bus unit tests to use the new utilities, significantly improving readability and DRY compliance.
~~~~~

### 下一步建议
- **WorkspaceFactory**: 下一步，我们可以按照计划，在 `stitcher-test-utils` 中实现 `WorkspaceFactory` 工具，以彻底消除集成测试中繁琐的文件系统设置代码。
- **CLI 命令验证**: 既然 `bus` 导入已修复，可以手动运行 `stitcher --help` 验证 CLI 的基本渲染是否恢复正常。
