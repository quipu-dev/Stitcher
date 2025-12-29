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
                options.append(
                    SemanticMenuOption(
                        key="f",
                        action=ResolutionAction.RELINK,
                        label_id=L.interactive.option.relink.label,
                        desc_id=L.interactive.option.relink.desc,
                    )
                )
            elif context.conflict_type == ConflictType.CO_EVOLUTION:
                options.append(
                    SemanticMenuOption(
                        key="r",
                        action=ResolutionAction.RECONCILE,
                        label_id=L.interactive.option.reconcile.label,
                        desc_id=L.interactive.option.reconcile.desc,
                    )
                )
            elif context.conflict_type == ConflictType.DOC_CONTENT_CONFLICT:
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
                if context.conflict_type != ConflictType.DOC_CONTENT_CONFLICT:
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
