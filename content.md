好的，重构已顺利完成。我们通过引入严格的 `Fingerprint` 模型，不仅解决了 `hydrate` 命令意外重写文件的问题，还加固了整个系统状态管理的底层架构。

现在，我将生成最终的 `[COMMIT]` 计划，将所有更改合并为一个逻辑完整的工作单元。

---
## [COMMIT] refactor: 引入 Fingerprint 模型并实施严格的 Schema 验证

### 用户需求
解决 `stitcher hydrate` 在遇到旧版指纹 Schema 时导致的意外文件重写问题，并建立健壮的指纹数据管理机制。

### 目标
1.  提交 `Fingerprint` 模型及其验证逻辑。
2.  提交 `SignatureManager` 和 `StitcherApp` 的重构代码。
3.  提交新增的回归测试和修正后的单元测试。

### 基本原理
本次重构将原本松散的“字典+约定”模式升级为“对象+公理”模式。通过 `Fingerprint` 容器，我们确保了所有存储和处理的哈希键必须符合 `[State]_[Source]_[Object]_hash` 的命名公理。加载时的严格验证机制能够自动识别并清除过时的指纹文件，从而实现系统的平滑自愈。

### 标签
#intent/refactor #flow/ready #priority/high #comp/runtime #comp/spec #concept/state #ai/instruct #task/domain/core #task/object/fingerprint-model #task/action/commit #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有受影响的文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-spec/src/stitcher/spec/fingerprint.py
packages/stitcher-spec/src/stitcher/spec/__init__.py
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/tests/integration/test_hydrate_regression.py
packages/stitcher-application/tests/test_signature_manager.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): introduce Fingerprint model and enforce strict schema validation

This commit addresses the issue where 'stitcher hydrate' unnecessarily rewrote signature files due to an implicit schema mismatch between the initial 'init' and subsequent 'hydrate' logic.

Key Changes:
- Introduced 'Fingerprint' class in stitcher-spec: A self-validating container for symbol hashes that enforces the naming axiom ('[State]_[Source]_[Object]_hash') via regex.
- Updated SignatureManager: Now operates on 'Fingerprint' objects. It implements a "fail-fast and heal" strategy where legacy or malformed keys trigger an InvalidFingerprintKeyError, causing the manager to discard the corrupted data and return an empty state, which leads to automatic regeneration of correct signatures.
- Refactored StitcherApp: Replaced fragile dictionary manipulations with structured Fingerprint object interactions across check, init, and hydrate workflows.
- Added Regression Test: 'test_hydrate_regression.py' confirms that the system now correctly migrates legacy signature files to the new schema during a hydrate run without affecting the docstrings.
- Fixed existing unit tests to comply with the new Fingerprint-based API.

This refactoring eliminates "conceptual debt" by making the naming axiom an enforced runtime contract rather than a mere convention.
~~~~~

### 下一步建议
- **扩展验证**: 既然我们有了通用的正则验证，可以考虑在未来引入 `ast` 来源的指纹（例如 `baseline_code_ast_hash`），只需更新正则即可。
- **性能优化**: 随着指纹维度的增加，可以审查 `Fingerprint` 序列化对大型项目性能的影响。目前基于 Python 字典的实现对于当前规模是绰绰有余的。
