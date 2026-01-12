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
    spec.add(
        Move(
            Path("packages/stitcher-application/src/stitcher/app/protocols.py"),
            Path("packages/stitcher-spec/src/stitcher/spec/interaction.py"),
        )
    )

    # 1.2 迁移索引层数据模型 (FileRecord, SymbolRecord, ReferenceRecord)
    # FQN 变更: stitcher.index.types -> stitcher.spec.index
    spec.add(
        Move(
            Path("packages/stitcher-index/src/stitcher/index/types.py"),
            Path("packages/stitcher-spec/src/stitcher/spec/index.py"),
        )
    )

    # 1.3 迁移语言适配器协议 (LanguageAdapter)
    # FQN 变更: stitcher.index.protocols -> stitcher.spec.registry
    spec.add(
        Move(
            Path("packages/stitcher-index/src/stitcher/index/protocols.py"),
            Path("packages/stitcher-spec/src/stitcher/spec/registry.py"),
        )
    )

    # 1.4 迁移文档持久化协议 (DocumentAdapter)
    # FQN 变更: stitcher.common.interfaces -> stitcher.spec.persistence
    spec.add(
        Move(
            Path("packages/stitcher-common/src/stitcher/common/interfaces.py"),
            Path("packages/stitcher-spec/src/stitcher/spec/persistence.py"),
        )
    )
