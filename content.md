## [WIP] feat(spec): Upgrade InteractionContext to use SemanticPointer

### 用户需求

根据 Phase 1.6+ 战略分析，我们需要升级规格层。
核心任务是将 `stitcher-spec` 中的 `InteractionContext` 升级，使其支持 `SemanticPointer`，从而统一分析层和交互层的语言，消除“阻抗不匹配”。

### 评论

这是一个涉及到底层数据模型的变更。通过在 `spec` 层引入 `pyneedle`，我们确立了 SemanticPointer 作为整个系统（不仅是分析层，还包括交互层）的通用语言。这将使我们能够直接将分析层产出的 `Violation` 转化为交互层所需的上下文，而无需繁琐且易碎的枚举映射。

### 目标

1.  更新 `stitcher-spec/pyproject.toml`，添加 `pyneedle-pointer` 依赖。
2.  修改 `stitcher.spec.interaction.InteractionContext`：
    *   引入 `violation_type: SemanticPointer`。
    *   为了保持过渡期的兼容性（HFEA原则建议不做破坏性变更除非必要，但在内部重构中，彻底清理更优），我们计划**移除**旧的 `conflict_type: ConflictType` 字段，强制上层代码进行适配，从而暴露所有潜在的不兼容点。

### 基本原理

如果不升级 Spec，上层 Runner 就必须在 Analysis 的 Pointer 和 Resolver 的 Enum 之间做翻译。这不仅增加了复杂性，还限制了未来的扩展性（每次加新规则都要改 Enum）。直接在 Spec 层支持 Pointer 是最干净的架构路径。

### 标签

#intent/refine #intent/architect #flow/ready #priority/high #comp/interfaces #scope/core #ai/instruct #task/domain/architecture #task/object/spec #task/action/upgrade-interaction-context #task/state/begin

---

### Script

#### Acts 1: 添加依赖

让 `stitcher-spec` 能够使用 `SemanticPointer`。

~~~~~act
patch_file
packages/stitcher-spec/pyproject.toml
~~~~~
~~~~~toml.old
description = "Intermediate Representation (IR) models for Stitcher."
requires-python = ">=3.10"
dependencies = []

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml.new
description = "Intermediate Representation (IR) models for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "pyneedle-pointer",
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/pyproject.toml
~~~~~
~~~~~toml.old
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
~~~~~
~~~~~toml.new
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
pyneedle-pointer = { workspace = true }
~~~~~

#### Acts 2: 升级 `InteractionContext`

将 `ConflictType` 替换为 `SemanticPointer`。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/interaction.py
~~~~~
~~~~~python
from typing import Protocol, List, Optional
from dataclasses import dataclass

from needle.pointer import SemanticPointer

from stitcher.spec import ResolutionAction, ConflictType


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    
    # Replaced ConflictType Enum with SemanticPointer for extensibility
    violation_type: SemanticPointer
    
    signature_diff: Optional[str] = None
    doc_diff: Optional[str] = None
    
    # Deprecated: kept temporarily if strictly needed, but design goal is to remove it.
    # conflict_type: ConflictType 


class InteractionHandler(Protocol):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]: ...
~~~~~

#### Acts 3: 标记 `ConflictType` 为过时 (可选但建议)

虽然我们保留了 `ConflictType` 的定义（在 `models.py` 中），但它现在在交互上下文中已经不再作为核心类型使用了。为了代码清晰，我们暂时不删除 `models.py` 中的 Enum 定义，以免破坏 `pump` 模块中可能残留的引用，但在 `InteractionContext` 中我们已经切换了类型。

### 下一步建议

Spec 层已升级。这破坏了 `stitcher-application` 中 `CheckResolver` 和 `PumpRunner` 的现有代码，因为它们还在使用旧的 `ConflictType`。这正是我们想要的——通过编译器错误来驱动重构。

接下来的步骤是 **Phase 1.6.2: 应用层适配器升级 (Adapter Upgrade)**。
我们需要修改 `stitcher-application`，使其 `SubjectAdapter` 能够产出符合 `stitcher-analysis` 契约的数据，并开始着手修复因 Spec 变更导致的类型错误。

建议先从 `stitcher.app.runners.check.subject.py` 开始，让适配器实现新的 `AnalysisSubject` 协议。
