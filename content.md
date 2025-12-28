## [WIP] feat: 交互式 CLI 本地化重构

### 用户需求
目前的 CLI 交互（如冲突解决菜单）中的文本是硬编码的英文，无法享受到系统的本地化（Needle/L）机制。需要重构这一部分，使其支持通过 L 指针动态加载本地化文本。

### 评论
这是一个必要的重构，使得 Stitcher 的用户界面在多语言环境下表现一致。

### 目标
1.  在 `stitcher-common` 中定义交互相关的 Needle 资源（`interactive.json`）。
2.  在 `stitcher-cli` 中实现 `SemanticMenuOption` 模型和 `TyperInteractiveRenderer`。
3.  重构 `TyperInteractionHandler` 以使用上述组件，替代硬编码字符串。
4.  在 `main.py` 中正确装配这些组件。

### 基本原理
通过引入“语义渲染器”模式，将业务逻辑（决定显示哪些选项）与表现层（如何显示选项文本）分离。`InteractionHandler` 负责逻辑，`Renderer` 负责 IO 和通过 Nexus 获取本地化文本。这不仅解决了本地化问题，也提高了代码的可测试性和整洁度。

### 标签
#intent/refine #flow/ready #priority/medium #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/ui #task/object/interactive-prompt #task/action/localize #task/state/begin

---

### Script

#### Acts 1: 定义 Needle 资源 (Data Layer)

首先，我们在 `stitcher-common` 中定义交互所需的文本资源。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/interactive.json
~~~~~
~~~~~json
{
  "header": {
    "title": "Conflict {current}/{total} in {path}",
    "symbol": "Symbol: {fqn}"
  },
  "reason": {
    "signature_drift": "Reason: Signature has changed, but docs have not (Signature Drift).",
    "co_evolution": "Reason: Both signature and docs have changed (Co-evolution).",
    "doc_content_conflict": "Reason: Source code docstring differs from YAML docstring."
  },
  "option": {
    "relink": { "label": "[F]orce-relink", "desc": "Force-relink new signature with old docs." },
    "reconcile": { "label": "[R]econcile", "desc": "Accept both changes as the new correct state." },
    "overwrite": { "label": "[F]orce overwrite", "desc": "Overwrite YAML with code docs (Code-first)." },
    "keep": { "label": "[R]econcile", "desc": "Keep existing YAML docs (YAML-first)." },
    "skip": { "label": "[S]kip", "desc": "Skip this conflict for now." },
    "abort": { "label": "[A]bort", "desc": "Abort the entire check process." },
    "undo": { "label": "[Z]Undo", "desc": "Go back to the previous conflict." }
  },
  "prompt": "Please choose an action:",
  "summary": "Found {count} conflicts. Please review them one by one.",
  "invalid_choice": "Invalid choice, please try again.",
  "already_at_start": "Already at the first conflict."
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/interactive.json
~~~~~
~~~~~json
{
  "header": {
    "title": "冲突 {current}/{total} 位于 {path}",
    "symbol": "符号: {fqn}"
  },
  "reason": {
    "signature_drift": "原因: 签名已变更，但文档未变 (签名漂移)。",
    "co_evolution": "原因: 签名和文档均已变更 (协同演进)。",
    "doc_content_conflict": "原因: 源代码文档字符串与 YAML 文档字符串不一致。"
  },
  "option": {
    "relink": { "label": "[F]强制重链 (Force-relink)", "desc": "强制将新签名关联到旧文档。" },
    "reconcile": { "label": "[R]调和 (Reconcile)", "desc": "接受双方变更作为新的正确状态。" },
    "overwrite": { "label": "[F]强制覆盖 (Force overwrite)", "desc": "使用代码文档覆盖 YAML (代码优先)。" },
    "keep": { "label": "[R]保留 (Reconcile)", "desc": "保留现有 YAML 文档 (YAML优先)。" },
    "skip": { "label": "[S]跳过 (Skip)", "desc": "暂不处理此冲突。" },
    "abort": { "label": "[A]中止 (Abort)", "desc": "中止整个检查过程。" },
    "undo": { "label": "[Z]撤销 (Undo)", "desc": "返回上一个冲突。" }
  },
  "prompt": "请选择操作:",
  "summary": "发现 {count} 个冲突。请逐一审查。",
  "invalid_choice": "无效选择，请重试。",
  "already_at_start": "已经是第一个冲突。"
}
~~~~~

#### Acts 2: 实现交互式渲染器 (Presentation Layer)

在 CLI 包中创建一个新的模块 `interactive.py`，用于定义语义选项模型和渲染器。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/interactive.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import List, Any, Union
from needle.pointer import SemanticPointer, L
from stitcher.spec import ResolutionAction, ConflictType
from stitcher.app.protocols import InteractionContext
import typer
import click

@dataclass
class SemanticMenuOption:
    key: str
    action: Union[ResolutionAction, str]  # str allowed for "UNDO"
    label_id: SemanticPointer
    desc_id: SemanticPointer

class TyperInteractiveRenderer:
    def __init__(self, nexus):
        self.nexus = nexus

    def show_summary(self, count: int) -> None:
        msg = self.nexus.get(L.interactive.summary).format(count=count)
        typer.echo(msg)

    def show_message(self, msg_id: SemanticPointer, color=None, **kwargs) -> None:
        msg = self.nexus.get(msg_id).format(**kwargs)
        typer.secho(msg, fg=color)

    def prompt(
        self,
        context: InteractionContext,
        current_idx: int,
        total: int,
        options: List[SemanticMenuOption],
        default_action: Any
    ) -> Any:
        # Header
        header_fmt = self.nexus.get(L.interactive.header.title)
        typer.echo("\n" + ("-" * 20))
        typer.secho(
            header_fmt.format(current=current_idx + 1, total=total, path=context.file_path),
            fg=typer.colors.CYAN,
        )
        
        symbol_fmt = self.nexus.get(L.interactive.header.symbol)
        typer.secho("  " + symbol_fmt.format(fqn=context.fqn), bold=True)

        # Reason
        reason_map = {
            ConflictType.SIGNATURE_DRIFT: L.interactive.reason.signature_drift,
            ConflictType.CO_EVOLUTION: L.interactive.reason.co_evolution,
            ConflictType.DOC_CONTENT_CONFLICT: L.interactive.reason.doc_content_conflict,
        }
        reason_l = reason_map.get(context.conflict_type)
        if reason_l:
             typer.secho("  " + self.nexus.get(reason_l), fg=typer.colors.YELLOW)

        # Prompt
        typer.echo("  " + self.nexus.get(L.interactive.prompt))

        # Options
        for opt in options:
            label = self.nexus.get(opt.label_id)
            desc = self.nexus.get(opt.desc_id)
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

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/interactive.stitcher.yaml
~~~~~
~~~~~yaml
"SemanticMenuOption": |-
  Data model representing a single option in an interactive menu, linking a key/action to semantic L pointers.
"TyperInteractiveRenderer": |-
  Renders interactive prompts using Typer, resolving text via Nexus.
"TyperInteractiveRenderer.prompt": |-
  Displays the full conflict resolution menu and captures user input.
"TyperInteractiveRenderer.show_message": |-
  Displays a formatted message resolved from an L pointer.
"TyperInteractiveRenderer.show_summary": |-
  Displays the summary of conflicts found.
~~~~~

#### Acts 3: 重构 InteractionHandler (Logic Layer)

现在重构 `handlers.py`，移除硬编码字符串，改为构建语义选项列表。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/handlers.py
~~~~~
~~~~~python
import sys
from typing import List, Optional
from needle.pointer import L
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType
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
            
            if context.conflict_type == ConflictType.SIGNATURE_DRIFT:
                options.append(SemanticMenuOption(
                    key="f", action=ResolutionAction.RELINK, 
                    label_id=L.interactive.option.relink.label, desc_id=L.interactive.option.relink.desc
                ))
            elif context.conflict_type == ConflictType.CO_EVOLUTION:
                options.append(SemanticMenuOption(
                    key="r", action=ResolutionAction.RECONCILE,
                    label_id=L.interactive.option.reconcile.label, desc_id=L.interactive.option.reconcile.desc
                ))
            elif context.conflict_type == ConflictType.DOC_CONTENT_CONFLICT:
                options.append(SemanticMenuOption(
                    key="f", action=ResolutionAction.HYDRATE_OVERWRITE,
                    label_id=L.interactive.option.overwrite.label, desc_id=L.interactive.option.overwrite.desc
                ))
                options.append(SemanticMenuOption(
                    key="r", action=ResolutionAction.HYDRATE_KEEP_EXISTING,
                    label_id=L.interactive.option.keep.label, desc_id=L.interactive.option.keep.desc
                ))
            
            options.append(SemanticMenuOption(
                key="s", action=ResolutionAction.SKIP,
                label_id=L.interactive.option.skip.label, desc_id=L.interactive.option.skip.desc
            ))
            options.append(SemanticMenuOption(
                key="a", action=ResolutionAction.ABORT,
                label_id=L.interactive.option.abort.label, desc_id=L.interactive.option.abort.desc
            ))
            options.append(SemanticMenuOption(
                key="z", action="UNDO",
                label_id=L.interactive.option.undo.label, desc_id=L.interactive.option.undo.desc
            ))

            action = self.renderer.prompt(
                context, current_index, len(contexts), options, default_choice
            )
            
            if action == "UNDO":
                if current_index > 0:
                    current_index -= 1
                else:
                    self.renderer.show_message(L.interactive.already_at_start, color="yellow")
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

#### Acts 4: 装配组件 (Main)

最后，更新 `main.py` 以注入渲染器。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python
from .rendering import CliRenderer
from .handlers import TyperInteractionHandler

app = typer.Typer(
~~~~~
~~~~~python
from .rendering import CliRenderer
from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer

app = typer.Typer(
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python
    if (
        sys.stdin.isatty()
        and not non_interactive
        and not force_relink
        and not reconcile
    ):
        handler = TyperInteractionHandler()

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
~~~~~
~~~~~python
    if (
        sys.stdin.isatty()
        and not non_interactive
        and not force_relink
        and not reconcile
    ):
        renderer = TyperInteractiveRenderer(nexus)
        handler = TyperInteractionHandler(renderer)

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python
    handler = None
    is_interactive = sys.stdin.isatty() and not non_interactive

    if is_interactive and not force and not reconcile:
        handler = TyperInteractionHandler()

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
~~~~~
~~~~~python
    handler = None
    is_interactive = sys.stdin.isatty() and not non_interactive

    if is_interactive and not force and not reconcile:
        renderer = TyperInteractiveRenderer(nexus)
        handler = TyperInteractionHandler(renderer)

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
~~~~~

### 下一步建议
我们引入了新的交互层，建议运行一次 `check` 来验证是否有未预料的 Typer/Click 行为变化，或者是否有 L 指针拼写错误。虽然有单元测试覆盖 Bus，但交互式部分的自动化测试较难，通常依赖人工冒烟测试。
