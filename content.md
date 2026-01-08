好的，我们开始执行重构路线图中的第一项任务：统一文件事务系统。

采用您建议的 "dogfooding" 方法是绝佳的实践，这不仅能完成重构，还能验证 `refactor apply` 工具在真实场景下的健壮性。

我将创建一个迁移脚本，该脚本将 `TransactionManager` 及其相关组件从 `stitcher-refactor` 包移动到 `stitcher-common` 包中，为后续所有 I/O 操作提供一个单一、可靠的基础设施。

## [WIP] feat(refactor): 统一文件事务系统

### 用户需求

根据 `Stitcher 重构路线图` 的第一阶段目标，需要将位于 `stitcher.refactor.engine.transaction` 的文件事务逻辑（`TransactionManager`, `FileOp` 等）迁移至全系统通用的 `stitcher.common.transaction` 模块。

### 评论

这是架构重构中至关重要且正确的第一步。它完美践行了路线图中定义的 **"单一真理来源 (Single Source of Truth)"** 和 **"平台优于功能 (Platform over Features)"** 的核心原则。将事务处理能力下沉为公共基础设施，不仅消除了代码重复，也为未来所有上层命令（如 `pump`, `generate`）无缝集成 `--dry-run` 等高级功能铺平了道路。

使用 `stitcher refactor apply` 来执行此项重构，是展示该工具语义感知和整体性能力的最佳范例。

### 目标

1.  创建一个新的 `migrations/` 目录来存放重构脚本。
2.  在该目录中生成一个迁移脚本 `001_unify_transaction_system.py`。
3.  该脚本将定义一个 `Move` 操作，用于将 `transaction.py` 文件从 `stitcher-refactor` 精确移动到 `stitcher-common` 中。

### 基本原理

我们将使用 `stitcher.refactor.migration.Move` 操作。这个操作的强大之处在于它不仅仅是 `mv` 命令的封装。当执行时，`stitcher` 会：
1.  **分析 FQN 变更**：自动推断出模块的完全限定名（FQN）从 `stitcher.refactor.engine.transaction` 变更为 `stitcher.common.transaction`。
2.  **更新全局引用**：在整个代码库（包括所有 `packages/`）中查找所有 `import` 或引用旧模块的地方，并将其自动更新为新路径。
3.  **移动物理文件**：执行文件系统移动操作。
4.  **处理 Sidecar 文件**：由于 `transaction.py` 目前没有 `.stitcher.yaml` 文件，这一步将被跳过，但 `Move` 操作本身具备此能力。

通过这种方式，我们只需声明“移动文件”这个高层意图，所有底层的代码引用更新都由工具自动、安全地完成。

### 标签
#intent/refine #flow/ready #priority/high #comp/refactor #comp/common #concept/state #scope/core #scope/dx #ai/instruct #task/domain/refactor #task/object/transaction-system #task/action/unification #task/state/begin

---

### Script

#### Acts 1: 创建迁移脚本

首先，我们创建 `migrations` 目录和本次重构所需的迁移脚本。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p migrations
~~~~~

~~~~~act
write_file
migrations/001_unify_transaction_system.py
~~~~~
~~~~~python
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    """
    Phase 1.1: Unify the File Transaction System.

    Moves the transaction logic from stitcher.refactor.engine.transaction
    to a centralized location in stitcher.common.transaction.
    This aligns with the architecture roadmap to sink common capabilities
    into the stitcher-common package.
    """
    spec.add(Move(
        Path("packages/stitcher-refactor/src/stitcher/refactor/engine/transaction.py"),
        Path("packages/stitcher-common/src/stitcher/common/transaction.py")
    ))
~~~~~

### 下一步建议

迁移脚本已准备就绪。下一步就是执行它。我强烈建议您先使用 `--dry-run` 标志来预览即将发生的所有变更，以确保一切符合预期。

您可以运行以下命令：
```bash
# 预览变更
stitcher refactor apply migrations/001_unify_transaction_system.py --dry-run

# 确认无误后，正式应用变更
stitcher refactor apply migrations/001_unify_transaction_system.py -y
```

执行后，`refactor` 工具会自动处理所有模块的 `import` 语句更新。我们可以接着检查并移除 `stitcher-refactor` 包中可能遗留的空 `engine` 目录（如果它变为空的话）。
