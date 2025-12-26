好的，我们已经完成了 `stitcher-needle` 的完整实现、测试以及全栈集成。这是一个重大的架构飞跃。

我将生成一个 `[COMMIT]` 计划，将所有变更作为一个完整的工作单元提交。

## [COMMIT] feat: 实现 stitcher-needle 微内核并迁移至全栈语义寻址

### 用户需求
完成 `stitcher-needle` 微内核的开发，并将其作为整个项目语义寻址的基础设施。将所有现有的字符串消息 ID 迁移到 `L` 语义指针，并根据新的 SST (物理分片语义分类法) 规范组织资源文件。

### 评论
这是一次深远的架构演进。我们不仅实现了一个零依赖、自愈的运行时，还通过将资产移至 `.stitcher/` 目录并引入健壮的根目录发现机制，确立了项目的数据与代码分离原则。这种“语义化编程”模式将极大提升开发者的生产力和系统的可维护性。

### 目标
1.  提交 `packages/stitcher-needle` 的完整代码和测试。
2.  提交 `stitcher-common`, `stitcher-application`, `stitcher-cli` 的集成和重构代码。
3.  提交重构后的 `.stitcher/` 资源目录。
4.  记录这一核心架构决策的落地。

### 基本原理
通过一个单一的、逻辑完整的提交，我们将项目的状态固化在这一新的里程碑上。这确保了版本历史的清晰性，使未来的回溯和审计变得更加容易。使用 `git_add .` 将涵盖新创建的包、移动的资源文件以及所有的代码修改。

### 标签
#intent/build #intent/architect #flow/ready #priority/high #comp/runtime #comp/common #comp/cli #comp/application #scope/core #scope/dx #task/domain/runtime #task/object/needle-kernel #task/action/implementation #task/state/end

---
### Script

#### Acts 1: 提交 Needle 核心及全栈集成

我们将所有相关变更添加到暂存区，并创建一个详尽的提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: implement stitcher-needle micro-kernel and semantic addressing

This commit marks a major architectural milestone: the transition from magic string IDs to a type-safe, self-healing semantic addressing paradigm.

Core components introduced:
- stitcher-needle: A zero-dependency runtime kernel.
- SemanticPointer (L): A recursive proxy for type-safe path building.
- SST (Semantic Sharding Taxonomy): A robust physical storage spec using FQN keys in JSON.
- Needle Runtime: Featuring project root discovery and a 3-tier graceful fallback (Target -> Default -> Identity).

Key structural changes:
- Assets relocated from packages to a top-level '.stitcher/' workspace to prevent namespace shadowing and promote high cohesion.
- MessageBus refactored to consume SemanticPointers and use the Needle runtime for resolution.
- Project-wide migration: All bus calls in CLI and Application now use the 'L' object.

This layer provides the foundation for future IDE autocompletion (.pyi generation) and AI-driven localization workflows.
~~~~~

### 下一步建议
- **生成存根**: 现在 `L` 对象已经就绪，下一步可以开始实现 `stitcher` 工具的 `stitching` 功能，即根据 `.stitcher/needle/` 中的内容自动为 `stitcher-needle` 生成 `.pyi` 存根文件，从而激活 IDE 的自动补全。
- **配置自愈**: 可以考虑在 `needle.get()` 触发身份回退时，自动向 `.stitcher` 目录写入缺少的键（即路线图中的 Auto-Seeding 机制）。
