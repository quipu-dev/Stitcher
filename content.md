好的，我们已经完成了“阶段三：核心服务抽象化”的主要协议净化和解耦工作。现在我将生成一个 `[COMMIT]` 计划来提交这些变更。

## [COMMIT] refactor: 净化核心服务协议并解除实现细节耦合

### 用户需求
用户要求将最近关于 `DocumentManager`, `SignatureManager` 以及 `IndexStore` 的一系列协议净化和解耦工作作为一个完整的逻辑单元提交。

### 评论
这是一次重大的架构改进。通过移除协议中泄漏的实现细节（如私有方法前缀和特定的序列化逻辑），我们真正实现了“面向接口编程”。这不仅清理了代码，更重要的是为系统的可测试性打下了坚实基础——现在我们可以轻松地为 Runner 提供内存中的 Mock 实现，而无需担心它们会去访问底层的文件系统或数据库。

### 目标
1.  提交对 `stitcher-spec` 中 `managers.py` 和 `storage.py` 的协议定义改进。
2.  提交对 `stitcher-application` 中实现类和调用方 (`PumpRunner`) 的同步重构。
3.  提交对 `stitcher-index` 中索引逻辑的解耦改进，包括将 `Linker` 职责下沉至 `IndexStore`。

### 基本原理
本阶段重构严格遵循 **依赖倒置原则 (DIP)** 和 **最少知识原则 (LoD)**。通过净化协议，我们确保了核心业务逻辑（Runner 和 Indexer）只知道它们“需要什么能力”，而不知道这些能力是“如何通过 YAML 或 SQLite 实现的”。这种解耦是构建健壮插件式架构的先决条件。

### 标签
#intent/refine #flow/ready #priority/high #comp/interfaces #comp/runtime #comp/index #scope/core #ai/instruct #task/domain/architecture #task/object/protocols #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构变更

我们将所有受影响的文件添加到 Git 暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-spec/src/stitcher/spec/managers.py
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-application/src/stitcher/app/runners/pump.py
packages/stitcher-spec/src/stitcher/spec/storage.py
packages/stitcher-index/src/stitcher/index/store.py
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: purify core service protocols and decouple implementation details

This commit completes the primary objectives of Phase 3: Service Abstraction by purifying the interfaces in stitcher-spec and removing implementation-specific leaks in the application and index layers.

Key changes:
- Purified DocumentManagerProtocol and SignatureManagerProtocol by removing private methods and exposing high-level semantic APIs (e.g., compute_ir_hash, dump_data).
- Updated PumpRunner to use the new protocol-level methods, decoupling it from YAML/JSON serialization details.
- Expanded IndexStoreProtocol to cover write/sync operations, enabling FileIndexer to depend solely on abstraction.
- Absorbed Linker logic into IndexStore, removing the need for FileIndexer to hold a direct database reference.

These changes significantly improve system testability and enforce strict adherence to the Dependency Inversion Principle across package boundaries.
~~~~~

### 下一步建议
随着核心服务的协议已经净化，下一步建议进入 **“阶段四：Refactor 引擎泛化”**，或者解决 Runner 内部硬编码实例化子组件的问题，通过引入工厂模式或依赖注入框架，彻底完成 `stitcher-application` 的解耦。
