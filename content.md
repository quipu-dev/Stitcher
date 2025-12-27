好的，重构工作已经圆满完成。我们成功将 `Nexus` 提升为 `Loader`，引入了读写分离的协议，并完成了所有术语的“升维”同步。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交到仓库。

## [COMMIT] refactor(core): implement Nexus as a Loader and CQRS protocols

### 用户需求
将当前的重构成果（Nexus Loader 化、写协议引入、文档同步）提交到 Git 仓库，使用 `git add .`。

### 评论
这次重构为 `Needle` 奠定了工业级的架构基础。通过将 `Nexus` 自身视为一个 `Loader`，我们释放了递归组合的潜力；通过引入 `domain` 概念，我们使系统具备了超越 i18n 的通用能力。

### 目标
1.  暂存所有变更。
2.  创建一个详尽的提交记录，说明重构的核心变动。

### 基本原理
按照 Git 最佳实践，在完成一个逻辑闭环（功能重构 + 修复错误 + 同步文档）后，应及时进行提交。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #comp/interfaces #concept/state #ai/instruct #task/domain/core-runtime #task/object/nexus-loader #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交重构成果

~~~~~act
run_command
~~~~~
~~~~~
git add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): implement Nexus as a Loader and CQRS protocols

This major refactoring evolves the Needle architecture by treating the Nexus itself as a ResourceLoader, enabling recursive composition.

Core changes:
- Refactored `NexusProtocol` to inherit from `ResourceLoaderProtocol`.
- Introduced `WritableResourceLoaderProtocol` to implement a CQRS-inspired write-back strategy.
- Updated `OverlayNexus` to implement both reading (layering) and writing (delegation) protocols.
- Renamed the core concept of `lang` to `domain` across all layers to support broader resource contexts (themes, config, etc.).
- Fixed namespace package issues by adding explicit `pkgutil` declarations in `pyneedle-runtime` and `pyneedle-nexus`.
- Implemented `put` and `locate` in `FileSystemLoader` with a deterministic FQN-to-Path mapping strategy.
- Synchronized all internal documentation (.stitcher.yaml) with the new terminology and signatures.

This change turns Needle into a universal semantic resource mesh, bridging the gap between static pointers and diverse, layered data sources.
~~~~~

### 下一步建议
架构已经就绪。接下来的一个好方向是利用 `OverlayNexus` 的新能力，尝试实现一个 `HttpLoader` 或 `SqliteLoader`，验证系统对非文件数据源的扩展性。
