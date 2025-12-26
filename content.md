好的，我们已经通过集成测试验证了功能。现在将这些变更作为一个完整的逻辑单元进行提交。

## [COMMIT] feat: 实现 `check` 命令的函数签名校验功能

### 用户需求
将“函数签名校验”支线任务的所有实现代码、配置和测试用例提交到 Git 仓库。

### 评论
这标志着 `stitcher-python` 具备了检测“代码漂移”的能力。不仅仅是发现新增或删除的函数，现在还能敏锐地察觉到由于参数、类型或返回值的变化而导致的文档过期风险。这是保证生产级项目文档质量的关键一步。

### 目标
1.  提交 `stitcher-spec` 中新增的指纹计算逻辑。
2.  提交 `stitcher-application` 中的 `SignatureManager` 服务及其集成逻辑。
3.  提交 `doc_manager` 关于模块文档字符串误报的修复。
4.  提交新增的本地化消息定义。
5.  提交单元测试和集成测试。

### 基本原理
遵循 `[COMMIT]` 协议，仅包含 Git 操作。我们在提交说明中详细记录了本次变更对 IR 模型、应用层服务、校验逻辑以及本地化资源的修改。

### 标签
#intent/build #flow/done #priority/high 
#comp/application #comp/spec #comp/tests #concept/state #scope/core
#ai/instruct
#task/domain/dev-tools #task/object/check-command #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交函数签名校验相关变更

~~~~~act
git_add
.stitcher/needle/en/check/signatures.json
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/src/stitcher/app/services/__init__.py
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-application/tests/test_signature_manager.py
packages/stitcher-spec/src/stitcher/spec/models.py
tests/integration/test_check_signatures.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(app): implement function signature validation for 'check' command

Introduces a SignatureManager to track and verify function/method signatures,
detecting "code drift" where an implementation changes but the documentation
remains outdated.

Key changes:
- Added 'compute_fingerprint()' to FunctionDef IR for stable, deterministic hashing of API contracts.
- Implemented SignatureManager to persist and compare fingerprints in '.stitcher/signatures/'.
- Integrated signature verification into 'StitcherApp.run_check()', reporting mismatched signatures as errors.
- Fixed an issue in 'DocumentManager' where modules without docstrings were incorrectly reported as 'MISSING' in YAML.
- Added localized message ID 'check.issue.mismatch' and its English template.
- Added comprehensive unit tests for signature management and an integration test for the end-to-end check workflow.

This completes the planned sub-task for enhancing the 'check' command's precision.
~~~~~

### 下一步建议
- **完善存根导入处理**: 接下来可以处理支线任务二：增强 `StubGenerator` 以自动处理类型注解所需的 `import` 语句，这对于生成合规的 `.pyi` 文件至关重要。
- **生命周期管理**: 或者开始实现 `strip` 和 `eject` 命令，为用户提供完整的文档解耦工作流。
