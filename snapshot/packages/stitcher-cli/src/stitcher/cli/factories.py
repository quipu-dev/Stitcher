import sys
from pathlib import Path
from typing import Optional

from stitcher.app.core import StitcherApp
from stitcher.spec.interaction import InteractionHandler
from stitcher.bus import stitcher_operator as nexus
from stitcher.lang.python import (
    GriffePythonParser,
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace.utils import find_workspace_root

from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer


def make_interaction_handler(
    non_interactive: bool = False,
    auto_resolve_mode: bool = False,
) -> Optional[InteractionHandler]:
    if sys.stdin.isatty() and not non_interactive and not auto_resolve_mode:
        renderer = TyperInteractiveRenderer(nexus)
        return TyperInteractionHandler(renderer)
    return None


def make_app(
    handler: Optional[InteractionHandler] = None,
) -> StitcherApp:
    # Composition Root: Assemble the dependencies

    # 1. Determine the true workspace root. This may raise WorkspaceNotFoundError,
    # which is caught by the command functions.
    project_root = find_workspace_root(Path.cwd())

    # 2. UNIFIED: Always use Griffe for analysis
    parser = GriffePythonParser()

    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=project_root,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
