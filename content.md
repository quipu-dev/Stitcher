你的需求很明确。我将为你生成用于执行“阶段一：协议标准化与下沉”的 Stitcher 迁移脚本。

## [WIP] feat: 创建阶段一协议下沉重构脚本

### 用户需求
创建一个符合 `stitcher refactor apply` 规范的迁移脚本，按照重构路线图将核心协议和数据模型从应用层和实现层下沉到 `stitcher-spec` 包中。

### 评论
这是架构演进的关键一步。通过物理移动文件并利用 Stitcher 的语义重构能力，我们可以确保全库范围内的 FQN 引用（如导入语句）自动更新，从而实现真正的、确定性的解耦。

### 目标
1. 创建迁移脚本文件 `migrations/001_phase_1_sinking.py`。
2. 在脚本中定义 `upgrade` 函数。
3. 使用 `Move` 操作精确迁移 Interaction、Index、Registry 和 Persistence 四个核心模块。

### 基本原理
利用 Stitcher `Move` 操作的语义感知特性。当一个 `.py` 文件在源代码树中移动时，Stitcher 会根据其新旧物理位置自动计算出逻辑 FQN 的变更，并作为“副作用”自动触发全局的 `Rename` 逻辑，更新所有消费者代码中的 `import` 语句和调用点。同时，关联的 `.stitcher.yaml` 和签名文件也会被同步移动和更新。

### 标签
#intent/tooling #flow/ready #priority/high #comp/build #concept/executor #scope/dx #ai/instruct #task/domain/refactor #task/object/migration-script #task/action/create #task/state/begin

---

### Script

#### Acts 1: 创建迁移脚本

我们将创建一个独立的 Python 迁移脚本，它将作为 `stitcher refactor apply` 的输入。

~~~~~act
write_file
migrations/001_phase_1_sinking.py
~~~~~
~~~~~python
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    """
    Stitcher 架构重构阶段一：协议标准化与下沉
    
    此脚本将核心协议和数据模型从各个功能包移动到核心协议包 stitcher-spec 中。
    Stitcher 将自动处理由此产生的 FQN 变更并全局更新引用。
    """
    
    # 1.1 迁移应用层交互协议 (InteractionHandler, InteractionContext)
    # FQN 变更: stitcher.app.protocols -> stitcher.spec.interaction
    spec.add(Move(
        Path("packages/stitcher-application/src/stitcher/app/protocols.py"),
        Path("packages/stitcher-spec/src/stitcher/spec/interaction.py")
    ))
    
    # 1.2 迁移索引层数据模型 (FileRecord, SymbolRecord, ReferenceRecord)
    # FQN 变更: stitcher.index.types -> stitcher.spec.index
    spec.add(Move(
        Path("packages/stitcher-index/src/stitcher/index/types.py"),
        Path("packages/stitcher-spec/src/stitcher/spec/index.py")
    ))
    
    # 1.3 迁移语言适配器协议 (LanguageAdapter)
    # FQN 变更: stitcher.index.protocols -> stitcher.spec.registry
    spec.add(Move(
        Path("packages/stitcher-index/src/stitcher/index/protocols.py"),
        Path("packages/stitcher-spec/src/stitcher/spec/registry.py")
    ))
    
    # 1.4 迁移文档持久化协议 (DocumentAdapter)
    # FQN 变更: stitcher.common.interfaces -> stitcher.spec.persistence
    spec.add(Move(
        Path("packages/stitcher-common/src/stitcher/common/interfaces.py"),
        Path("packages/stitcher-spec/src/stitcher/spec/persistence.py")
    ))
~~~~~

### 下一步建议

1.  **预览变更**: 执行 `stitcher refactor apply migrations/001_phase_1_sinking.py --dry-run`。仔细审查输出的计划，确认所有 `import` 语句的重写是否符合预期。
2.  **正式执行**: 确认无误后，移除 `--dry-run` 标志正式应用重构。
3.  **同步配置**: 重构完成后，你需要手动更新各包的 `pyproject.toml` 中的 `dependencies`。特别是确保那些现在依赖下沉协议的包（如 `stitcher-application`）已经添加了 `stitcher-spec` 作为依赖。
4.  **开始阶段二**: 完成物理移动和引用更新后，即可开始“阶段二：语言能力统一与合并”。


