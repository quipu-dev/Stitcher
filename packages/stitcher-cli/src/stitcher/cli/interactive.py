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
            ConflictType.SIGNATURE_DRIFT: L.interactive.reason.signature_drift,
            ConflictType.CO_EVOLUTION: L.interactive.reason.co_evolution,
            ConflictType.DOC_CONTENT_CONFLICT: L.interactive.reason.doc_content_conflict,
            ConflictType.DANGLING_DOC: L.interactive.reason.dangling_doc,
        }
        reason_l = reason_map.get(context.conflict_type)
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
