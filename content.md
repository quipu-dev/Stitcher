好的，重构的物理迁移与逻辑剥离部分已经完成。现在我们将这些变更作为一个完整的逻辑单元提交到 Git 仓库。

## [COMMIT] refactor: 整合 I18N 资产与反馈工厂至 stitcher-bus

### 用户需求
完成架构纯化动作，将多语言资产、`pyneedle` 工厂组装逻辑以及全局 `bus` 单例正式移入 `stitcher-bus` 包，并记录相关的配置变更与迁移脚本。

### 评论
这次提交标志着 `Stitcher` 反馈机制的完全独立化。`stitcher-bus` 不再仅仅是一个轻量级的包定义，它现在承载了系统所有的视觉和文本交互灵魂。`stitcher-common` 则被成功瘦身为一个纯粹的底层工具集，这将显著降低后续开发中的理解成本。

### 目标
1. 将 `stitcher-bus` 的新增文件（Assets, factory）和配置变更添加到暂存区。
2. 将 `stitcher-common` 的代码清理和资产移除操作同步至暂存区。
3. 包含用于更新 FQN 引用的重构脚本。

### 基本原理
根据 `d3-constraint-quipu-plan-script-rules`，在代码验证通过后，通过独立的提交计划将变更持久化。这确保了版本历史的清晰，且每一个 `[COMMIT]` 节点都是一个稳定、可工作的状态。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/bus #comp/common #comp/build #concept/ui #scope/core 
#ai/instruct
#task/domain/refactoring #task/object/i18n-hub #task/action/consolidation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交整合变更

我们将 `stitcher-bus` 的完整功能化变更以及 `stitcher-common` 的瘦身变更进行原子化提交。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: consolidate I18N assets and factory logic into 'stitcher-bus'

This completes the transformation of 'stitcher-bus' into the project's central communication hub:
- Moved all multi-language JSON assets (needle/) from common to bus.
- Implemented 'factory.py' in stitcher-bus to handle pyneedle operator composition and language detection.
- Relocated the global 'bus' singleton and 'stitcher_operator' to the bus package.
- Stripped I18N and bus instantiation logic from 'stitcher-common', leaving it as a pure utility package.
- Added migration script '005_update_bus_fqn_references.py' to facilitate workspace-wide FQN updates.

The system's feedback mechanism is now decoupled from general utilities, ensuring a cleaner dependency graph.
~~~~~

### 下一步建议
1. **全局引用更新**: 立即执行 `stitcher refactor apply migrations/005_update_bus_fqn_references.py` 来同步全项目的导入语句。
2. **包可见性检查**: 在不同的包中尝试导入 `from stitcher.bus import bus`，验证 IDE 的自动完成和类型提示是否正常工作。
3. **环境同步**: 建议所有开发者运行 `uv sync` 以应用最新的包资产包含配置。
