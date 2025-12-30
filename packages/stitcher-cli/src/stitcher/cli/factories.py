import sys
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.common import stitcher_operator as nexus
from stitcher.adapter.python import (
    GriffePythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)

from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer


def get_project_root() -> Path:
    return Path.cwd()


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
    # UNIFIED: Always use Griffe for analysis
    parser = GriffePythonParser()

    transformer = PythonTransformer()
    generator = PythonStubGenerator()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=get_project_root(),
        parser=parser,
        transformer=transformer,
        stub_generator=generator,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
