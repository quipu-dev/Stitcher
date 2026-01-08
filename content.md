好的，我们已经完成了核心服务的提取和 Runner 的解耦工作。现在的架构为 Phase 2 的结构化文档支持打下了坚实的基础。

我将生成一个 `[COMMIT]` 计划，将这些重构内容提交到 Git 仓库。

## [COMMIT] refactor: 解耦对比与合并逻辑至独立服务

### 用户需求
将 `CheckRunner` 和 `PumpRunner` 中重复的 Diff 生成逻辑以及耦合的文档合并逻辑提取为独立服务（`Differ` 和 `Merger`），以提升代码复用性并为结构化文档（Phase 2）做准备。

### 评论
这次重构成功地将“流程控制”（Runners）与“业务策略”（Merger）分离。`DocstringMerger` 现在作为处理文档冲突的单一真理来源，极大地方便了后续对 Google/NumPy 风格合并规则的扩展，同时也保证了插件数据（Addons）在任何操作下都能得到妥善保护。

### 目标
1.  提交新创建的 `Differ` 和 `DocstringMerger` 服务。
2.  提交对 `CheckRunner` 和 `PumpRunner` 的重构，使其使用新服务。
3.  提交 `StitcherApp` 组装层的更新。
4.  提交 Phase 1 和 Pre-Phase 2 涉及的所有测试更新。

### 基本原理
遵循“关注点分离”原则。Runner 现在只关注“何时”进行对比和合并，而 `Differ` 和 `Merger` 关注“如何”进行。这种解耦使得我们可以独立于 CLI 逻辑去测试和升级合并算法，符合高保真工程公理。

### 标签
#intent/refine #flow/ready #comp/application #comp/spec #scope/core #ai/delegate #task/domain/architecture #task/object/core-services #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构变更

我们将所有涉及架构解耦和文档模型升级的变更打包提交。

~~~~~act
git_add
packages/stitcher-spec/src/stitcher/spec/docstring.py
packages/stitcher-spec/src/stitcher/spec/models.py
packages/stitcher-spec/src/stitcher/spec/protocols.py
packages/stitcher-spec/src/stitcher/spec/__init__.py
packages/stitcher-config/src/stitcher/config/loader.py
packages/stitcher-common/src/stitcher/common/interfaces.py
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/raw_parser.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/__init__.py
packages/stitcher-application/src/stitcher/app/services/differ.py
packages/stitcher-application/src/stitcher/app/services/differ.stitcher.yaml
packages/stitcher-application/src/stitcher/app/services/merger.py
packages/stitcher-application/src/stitcher/app/services/merger.stitcher.yaml
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
packages/stitcher-application/src/stitcher/app/services/__init__.py
packages/stitcher-application/src/stitcher/app/runners/check.py
packages/stitcher-application/src/stitcher/app/runners/pump.py
packages/stitcher-application/src/stitcher/app/runners/transform.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/tests/unit/test_docstring_hybrid.py
packages/stitcher-application/tests/unit/test_doc_manager.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: decouple diff and merge logic into standalone services

This commit implements the structural foundation for the upcoming
multi-style docstring support (Phase 2) and the Plugin (Addon) system.

Key changes:
- Extracted 'Differ' service to centralize text diff generation,
  removing duplication between Check and Pump runners.
- Extracted 'DocstringMerger' service to encapsulate the logic of
  merging source code changes with YAML data while preserving addons.
- Refactored CheckRunner and PumpRunner to delegate these tasks to
  the new services, simplifying their core loops.
- Upgraded DocumentManager to work with structured 'DocstringIR'
  objects instead of raw strings, enabling support for Hybrid Mode
  (Raw summary + Addon data).
- Updated internal data models (ModuleDef, etc.) and configuration
  loaders to handle docstring styles and structured data.
- Added unit tests for Hybrid Mode serialization and hash stability.

This decoupling ensures that future structured merging logic can be
implemented within the Merger service without affecting the workflow
logic of the Runners.
~~~~~

### 下一步建议

- **单元测试强化**: 既然 `DocstringMerger` 已经独立，建议为其编写更详尽的单元测试，覆盖各种边界情况（如只有 Addon、Summary 改变但 Addon 为空等）。
- **启动 Phase 2**: 开始实施结构化文档支持。首要任务是引入 `griffe` 解析器来实现真正的 Google/NumPy 风格解析，并将其集成到 `DocstringMerger` 中实现“智能合并”。
