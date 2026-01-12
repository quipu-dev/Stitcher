好的，我们继续执行路线图的第二阶段。

我将生成一个新的计划，专注于修复 `stitcher-cli` 包中的交互逻辑，确保用户界面能够正确处理和展示由 `SemanticPointer` 定义的新冲突类型。

## [WIP] refactor: 迁移 CLI 交互逻辑以使用 violation_type 指针

### 用户需求

根据路线图，需要执行 Phase 2，将 `stitcher-cli` 包中负责用户交互的组件 (`TyperInteractionHandler`, `TyperInteractiveRenderer`) 从消费 `ConflictType` Enum 迁移到处理 `violation_type: SemanticPointer`。

### 评论

这是将架构变更暴露给用户的关键一步。修复 `stitcher-cli` 不仅是技术迁移的延续，更是确保最终用户体验完整、无缝的核心环节。通过更新交互处理器和渲染器，我们能将 `SemanticPointer` 带来的丰富语义信息准确地传达给开发者，使冲突解决过程更加清晰、直观。

### 目标

1.  **重构 `TyperInteractionHandler`**: 修改其内部的 `if/elif` 决策逻辑，使其基于 `context.violation_type` 的 `SemanticPointer` 值来构建交互式菜单选项。
2.  **更新 `TyperInteractiveRenderer`**: 修改其 `reason_map`，将键从 `ConflictType` 枚举替换为 `SemanticPointer`，并更新其查找逻辑以使用 `context.violation_type`。

### 基本原理

与第一阶段类似，`stitcher-cli` 的修改也涉及多个文件和文件内的多个位置。为了确保修改的原子性和正确性，我将继续采用 `write_file` 策略，对 `handlers.py` 和 `interactive.py` 进行整体更新。这可以避免因局部修改而引入的潜在集成问题，确保 CLI 层的行为与应用核心层的变更完全同步。

### 标签

#intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/refactor #task/object/conflict-type #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 修改 `TyperInteractionHandler` 以处理 `violation_type`

我们将重写 `handlers.py`，将所有对 `context.conflict_type` 的引用替换为 `context.violation_type`，并使用 `L` 指针进行条件判断。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/handlers.py
~~~~~
~~~~~python
import sys
from typing import List, Optional
from needle.pointer import L
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction
from .interactive import TyperInteractiveRenderer, SemanticMenuOption


class TyperInteractionHandler(InteractionHandler):
    def __init__(self, renderer: TyperInteractiveRenderer):
        self.renderer = renderer

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        if not sys.stdin.isatty():
            return [ResolutionAction.SKIP] * len(contexts)

        self.renderer.show_summary(len(contexts))

        resolutions: List[Optional[ResolutionAction]] = [None] * len(contexts)
        current_index = 0
        last_choice: Optional[ResolutionAction] = None

        while current_index < len(contexts):
            context = contexts[current_index]

            recorded_choice = resolutions[current_index]
            default_choice = recorded_choice or last_choice or ResolutionAction.ABORT

            # Build Options
            options = []
            violation = context.violation_type

            if violation == L.check.state.signature_drift:
                options.append(
                    SemanticMenuOption(
                        key="f",
                        action=ResolutionAction.RELINK,
                        label_id=L.interactive.option.relink.label,
                        desc_id=L.interactive.option.relink.desc,
                    )
                )
            elif violation == L.check.issue.extra:  # DANGLING_DOC
                options.append(
                    SemanticMenuOption(
                        key="p",
                        action=ResolutionAction.PURGE_DOC,
                        label_id=L.interactive.option.purge.label,
                        desc_id=L.interactive.option.purge.desc,
                    )
                )
            elif violation == L.check.state.co_evolution:
                options.append(
                    SemanticMenuOption(
                        key="r",
                        action=ResolutionAction.RECONCILE,
                        label_id=L.interactive.option.reconcile.label,
                        desc_id=L.interactive.option.reconcile.desc,
                    )
                )
            elif violation == L.check.issue.conflict:  # DOC_CONTENT_CONFLICT
                options.append(
                    SemanticMenuOption(
                        key="f",
                        action=ResolutionAction.HYDRATE_OVERWRITE,
                        label_id=L.interactive.option.overwrite.label,
                        desc_id=L.interactive.option.overwrite.desc,
                    )
                )
                options.append(
                    SemanticMenuOption(
                        key="r",
                        action=ResolutionAction.HYDRATE_KEEP_EXISTING,
                        label_id=L.interactive.option.keep.label,
                        desc_id=L.interactive.option.keep.desc,
                    )
                )

            # NOTE: Skip is disabled for pump to prevent data loss with file-level strip
            if violation != L.check.issue.conflict:
                options.append(
                    SemanticMenuOption(
                        key="s",
                        action=ResolutionAction.SKIP,
                        label_id=L.interactive.option.skip.label,
                        desc_id=L.interactive.option.skip.desc,
                    )
                )

            options.append(
                SemanticMenuOption(
                    key="a",
                    action=ResolutionAction.ABORT,
                    label_id=L.interactive.option.abort.label,
                    desc_id=L.interactive.option.abort.desc,
                )
            )
            options.append(
                SemanticMenuOption(
                    key="z",
                    action="UNDO",
                    label_id=L.interactive.option.undo.label,
                    desc_id=L.interactive.option.undo.desc,
                )
            )

            action = self.renderer.prompt(
                context, current_index, len(contexts), options, default_choice
            )

            if action == "UNDO":
                if current_index > 0:
                    current_index -= 1
                else:
                    self.renderer.show_message(
                        L.interactive.already_at_start, color="yellow"
                    )
                continue

            resolutions[current_index] = action
            if action != ResolutionAction.ABORT:
                last_choice = action

            if action == ResolutionAction.ABORT:
                for i in range(len(resolutions)):
                    if resolutions[i] is None:
                        resolutions[i] = ResolutionAction.ABORT
                break

            current_index += 1

        return [res or ResolutionAction.SKIP for res in resolutions]
~~~~~

#### Acts 2: 更新 `TyperInteractiveRenderer` 以映射 `violation_type`

我们将更新 `interactive.py` 中的 `reason_map`，使其键为 `SemanticPointer`，并调整查找逻辑。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/interactive.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import List, Any, Union
from needle.pointer import SemanticPointer, L
from stitcher.spec import ResolutionAction
from stitcher.spec.interaction import InteractionContext
import typer
import click


@dataclass
class SemanticMenuOption:
    key: str
    action: Union[ResolutionAction, str]  # str allowed for "UNDO"
    label_id: SemanticPointer
    desc_id: SemanticPointer


class TyperInteractiveRenderer:
    def __init__(self, operator):
        self.operator = operator

    def show_summary(self, count: int) -> None:
        msg = self.operator(L.interactive.summary).format(count=count)
        typer.echo(msg)

    def show_message(self, msg_id: SemanticPointer, color=None, **kwargs) -> None:
        msg = self.operator(msg_id).format(**kwargs)
        typer.secho(msg, fg=color)

    def prompt(
        self,
        context: InteractionContext,
        current_idx: int,
        total: int,
        options: List[SemanticMenuOption],
        default_action: Any,
    ) -> Any:
        # Header
        header_fmt = self.operator(L.interactive.header.title)
        typer.echo("\n" + ("-" * 20))
        typer.secho(
            header_fmt.format(
                current=current_idx + 1, total=total, path=context.file_path
            ),
            fg=typer.colors.CYAN,
        )

        symbol_fmt = self.operator(L.interactive.header.symbol)
        typer.secho("  " + symbol_fmt.format(fqn=context.fqn), bold=True)

        # Reason
        reason_map = {
            L.check.state.signature_drift: L.interactive.reason.signature_drift,
            L.check.state.co_evolution: L.interactive.reason.co_evolution,
            L.check.issue.conflict: L.interactive.reason.doc_content_conflict,
            L.check.issue.extra: L.interactive.reason.dangling_doc,
        }
        reason_l = reason_map.get(context.violation_type)
        if reason_l:
            typer.secho("  " + self.operator(reason_l), fg=typer.colors.YELLOW)

        # View Diff
        if context.signature_diff:
            typer.echo("")
            typer.secho("  [ SIGNATURE DIFF ]", bold=True)
            for line in context.signature_diff.splitlines():
                color = None
                if line.startswith("+"):
                    color = typer.colors.GREEN
                elif line.startswith("-"):
                    color = typer.colors.RED
                typer.secho(f"  {line}", fg=color)

        if context.doc_diff:
            typer.echo("")
            typer.secho("  [ DOCSTRING DIFF ]", bold=True)
            for line in context.doc_diff.splitlines():
                color = None
                if line.startswith("+"):
                    color = typer.colors.GREEN
                elif line.startswith("-"):
                    color = typer.colors.RED
                typer.secho(f"  {line}", fg=color)

        # Prompt
        typer.echo("\n  " + self.operator(L.interactive.prompt))

        # Options
        for opt in options:
            label = self.operator(opt.label_id)
            desc = self.operator(opt.desc_id)
            is_default = opt.action == default_action
            prefix = "> " if is_default else "  "
            # Label format assumes "[K]Label" style roughly
            typer.secho(f"  {prefix}{label:<25} - {desc}", bold=is_default)

        # Input loop
        while True:
            char = click.getchar().lower()

            if char == "\r" or char == "\n":
                return default_action

            for opt in options:
                if char == opt.key.lower():
                    return opt.action

            self.show_message(L.interactive.invalid_choice, color=typer.colors.RED)
~~~~~

### 下一步建议

我们已经完成了路线图的第二阶段。`stitcher-cli` 现在能够正确处理和呈现基于 `SemanticPointer` 的冲突信息。

下一步是 **Phase 3: 修复测试用例**。这是确保我们所有重构都正确无误、没有引入回归的关键验证步骤。我将准备一个计划来更新所有相关的测试文件，以反映 `InteractionContext` 的新结构。如果你同意，我将着手准备第三阶段的计划。
