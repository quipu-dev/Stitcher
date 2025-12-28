import sys
from typing import List, Optional
import click
import typer

from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType


class TyperInteractionHandler(InteractionHandler):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        if not sys.stdin.isatty():
            # Should not happen if logic is correct, but as a safeguard
            return [ResolutionAction.SKIP] * len(contexts)

        typer.echo(f"Found {len(contexts)} conflicts. Please review them one by one.")

        resolutions: List[Optional[ResolutionAction]] = [None] * len(contexts)
        current_index = 0
        last_choice: Optional[ResolutionAction] = None

        while current_index < len(contexts):
            context = contexts[current_index]

            # Determine default choice
            recorded_choice = resolutions[current_index]
            default_choice = recorded_choice or last_choice or ResolutionAction.ABORT

            # --- Display Conflict ---
            typer.echo("\n" + ("-" * 20))
            typer.secho(
                f"Conflict {current_index + 1}/{len(contexts)} in {context.file_path}",
                fg=typer.colors.CYAN,
            )
            typer.secho(f"  Symbol: {context.fqn}", bold=True)

            # --- Build and Display Menu ---
            menu = []
            if context.conflict_type == ConflictType.SIGNATURE_DRIFT:
                typer.secho(
                    "  Reason: Signature has changed, but docs have not (Signature Drift)."
                )
                menu.append(
                    (
                        "[F]orce-relink",
                        ResolutionAction.RELINK,
                        "Force-relink new signature with old docs.",
                    )
                )
            elif context.conflict_type == ConflictType.CO_EVOLUTION:
                typer.secho(
                    "  Reason: Both signature and docs have changed (Co-evolution)."
                )
                menu.append(
                    (
                        "[R]econcile",
                        ResolutionAction.RECONCILE,
                        "Accept both changes as the new correct state.",
                    )
                )
            elif context.conflict_type == ConflictType.DOC_CONTENT_CONFLICT:
                typer.secho(
                    "  Reason: Source code docstring differs from YAML docstring."
                )
                menu.append(
                    (
                        "[F]orce overwrite",
                        ResolutionAction.HYDRATE_OVERWRITE,
                        "Overwrite YAML with code docs (Code-first).",
                    )
                )
                menu.append(
                    (
                        "[R]econcile",
                        ResolutionAction.HYDRATE_KEEP_EXISTING,
                        "Keep existing YAML docs (YAML-first).",
                    )
                )

            menu.append(
                ("[S]kip", ResolutionAction.SKIP, "Skip this conflict for now.")
            )
            menu.append(
                ("[A]bort", ResolutionAction.ABORT, "Abort the entire check process.")
            )
            menu.append(("[Z]Undo", "UNDO", "Go back to the previous conflict."))

            typer.echo("  Please choose an action:")
            for option, action, desc in menu:
                is_default = action == default_choice
                prefix = "> " if is_default else "  "
                typer.secho(f"  {prefix}{option:<15} - {desc}", bold=is_default)

            # --- Get Input ---
            char = click.getchar().lower()

            # --- Process Input ---
            if char == "\r" or char == "\n":  # Enter
                action = default_choice
            elif char == "f":
                if any(a == ResolutionAction.RELINK for _, a, _ in menu):
                    action = ResolutionAction.RELINK
                elif any(a == ResolutionAction.HYDRATE_OVERWRITE for _, a, _ in menu):
                    action = ResolutionAction.HYDRATE_OVERWRITE
                else:
                    typer.secho("Invalid choice, please try again.", fg=typer.colors.RED)
                    continue
            elif char == "r":
                if any(a == ResolutionAction.RECONCILE for _, a, _ in menu):
                    action = ResolutionAction.RECONCILE
                elif any(
                    a == ResolutionAction.HYDRATE_KEEP_EXISTING for _, a, _ in menu
                ):
                    action = ResolutionAction.HYDRATE_KEEP_EXISTING
            elif char == "s":
                action = ResolutionAction.SKIP
            elif char == "a":
                action = ResolutionAction.ABORT
            elif char == "z":
                if current_index > 0:
                    current_index -= 1
                else:
                    typer.secho(
                        "Already at the first conflict.", fg=typer.colors.YELLOW
                    )
                continue  # loop to re-display previous conflict
            else:
                typer.secho("Invalid choice, please try again.", fg=typer.colors.RED)
                continue

            resolutions[current_index] = action
            if action != ResolutionAction.ABORT:
                last_choice = action  # Update sticky default

            if action == ResolutionAction.ABORT:
                # Fill remaining with ABORT to signal cancellation
                for i in range(len(resolutions)):
                    if resolutions[i] is None:
                        resolutions[i] = ResolutionAction.ABORT
                break

            current_index += 1

        # Fill any remaining unvisited with SKIP
        final_actions = [res or ResolutionAction.SKIP for res in resolutions]

        # Final confirmation could be added here later

        return final_actions
