import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)


def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    return StitcherApp(
        root_path=root_path,
        parser=PythonParser(),
        transformer=PythonTransformer(),
        stub_generator=PythonStubGenerator(),
        fingerprint_strategy=PythonFingerprintStrategy(),
        interaction_handler=interaction_handler,
    )


def get_stored_hashes(project_root: Path, file_path: str) -> dict:
    sig_file = (
        project_root / ".stitcher/signatures" / Path(file_path).with_suffix(".json")
    )
    if not sig_file.exists():
        return {}
    with sig_file.open("r") as f:
        return json.load(f)
