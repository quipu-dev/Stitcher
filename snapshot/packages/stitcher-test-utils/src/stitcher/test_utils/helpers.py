import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.spec.interaction import InteractionHandler
from stitcher.lang.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace, find_package_root

from stitcher.lang.python.parser.griffe import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter


def create_populated_index(root_path: Path) -> IndexStore:
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    indexer.register_adapter(".py", PythonAdapter(root_path, search_paths))
    indexer.index_files(files_to_index)

    return store


def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    return StitcherApp(
        root_path=root_path,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=interaction_handler,
    )


def get_stored_hashes(project_root: Path, file_path_in_package: str) -> dict:
    """
    Reads a stitcher.lock file for the package containing the given file
    and returns all fingerprints within that lock file.
    """
    abs_file_path = project_root / file_path_in_package
    package_root = find_package_root(abs_file_path)
    if not package_root:
        return {}

    lock_path = package_root / "stitcher.lock"
    if not lock_path.exists():
        return {}

    with lock_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("fingerprints", {})
