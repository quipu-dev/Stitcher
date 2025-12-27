好的，我们已经成功完成了 `pyneedle` 生态的重构和验证。现在是时候将这个里程碑式的工作提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划，该计划将暂存所有变更并创建一个内容详尽的提交信息，以记录这次重要的架构演进。

## [COMMIT] refactor(runtime): 将 stitcher-needle 重构为模块化的 pyneedle 生态

### 用户需求
将 `stitcher-needle` 的重构工作（分包为 `pyneedle-spec`, `pyneedle-pointer`, `pyneedle-nexus`, `pyneedle`）作为一个完整的逻辑单元提交。

### 评论
这次重构是项目的一个重要里程碑。它将一个单一的、耦合的运行时分解为一个协议优先、高度可测试、可扩展的微内核架构。这不仅提升了代码质量和可维护性，还为 `Needle` 作为一个独立于 `Stitcher` 的生态系统的未来发展奠定了坚实的基础。提交信息需要清晰地反映出这一系列的设计决策。

### 目标
1.  将所有新建、修改的文件添加到 Git 暂存区。
2.  创建一个符合 Conventional Commits 规范的提交，详细说明重构的动机、过程和成果。

### 基本原理
一个原子化的、信息丰富的提交有助于未来的代码考古和维护。我们将所有相关的变更打包在一次提交中，因为它代表了一个单一的、连贯的架构决策。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/interfaces #comp/build #scope/core
#task/domain/runtime #task/object/pyneedle #task/action/commit
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有变更
使用 `git_add .` 将所有新包和修改的配置文件添加到暂存区。

~~~~~act
git_add
.
~~~~~

#### Acts 2: 提交重构成果
创建一个详细的 Git 提交，记录这次架构演进。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): decompose stitcher-needle into modular pyneedle ecosystem

This commit introduces a major architectural refactoring, replacing the monolithic `stitcher-needle` package with a new, protocol-first `pyneedle` ecosystem. This lays the foundation for a more robust, testable, and extensible semantic runtime.

### Motivation

The original `stitcher-needle` package was becoming a "god object," mixing concerns of I/O, runtime logic, and pointer implementation. This made it difficult to test in isolation and limited its potential as a standalone library independent of the `stitcher` developer tool.

### Key Changes

1.  **Protocol-First Architecture (`pyneedle-spec`)**: A new, zero-dependency package now defines the core contracts (`SemanticPointerProtocol`, `NexusProtocol`, `ResourceLoaderProtocol`), decoupling the API from the implementation.

2.  **Semantic Algebra (`pyneedle-pointer`)**: The `SemanticPointer` (L) and `PointerSet` (Ls) implementations are now isolated in their own package, complete with robust operator overloading (`+`, `/`, `*`, `[]`) and comprehensive unit tests.

3.  **IO-Agnostic Core (`pyneedle-nexus`)**: The runtime engine (`OverlayNexus`) is now a pure, in-memory component that operates on loaders via protocols. It uses `ChainMap` for logical overlays, providing superior testability and performance.

4.  **Batteries-Included Assembly (`pyneedle`)**: A new top-level package assembles all components, implements the `FileSystemLoader`, and exposes the simple `from needle import nexus, L` API for end-users.

5.  **API Clarification**: The global runtime instance has been renamed from `needle` to `nexus` to improve clarity and avoid conceptual overlap with the "Needle" (as in "L") metaphor.

This refactoring resolves previous testing difficulties, clarifies architectural boundaries, and positions the `pyneedle` runtime for future growth.
~~~~~

### 下一步建议
我们已经成功地将 `pyneedle` 生态的核心构建并提交。现在，我们的首要任务是：
*   **迁移消费者**: 逐一更新 `stitcher-common`、`stitcher-cli` 等包，将它们的依赖从 `stitcher-needle` 切换到新的 `pyneedle` 包，并适配 `from needle import nexus, L` 的新 API。
*   **清理**: 在所有消费者迁移完毕后，我们就可以安全地从工作区中删除 `packages/stitcher-needle` 目录了。
