from pathlib import Path
from typing import Optional, Dict

from stitcher.app.core import StitcherApp
from stitcher.spec.interaction import InteractionHandler
from stitcher.lang.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace

from stitcher.lang.python.parser.griffe import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.lang.sidecar import LockFileManager


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
    uri_generator = PythonURIGenerator()
    indexer.register_adapter(
        ".py", PythonAdapter(root_path, search_paths, uri_generator=uri_generator)
    )
    indexer.index_files(files_to_index)

    return store


def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    app = StitcherApp(
        root_path=root_path,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=interaction_handler,
    )
    # Database is now initialized in StitcherApp constructor.
    return app


def get_stored_hashes(project_root: Path, file_path: str) -> Dict[str, dict]:
    workspace = Workspace(project_root)
    lock_manager = LockFileManager()

    # 1. Find the package root for the given file
    abs_file_path = project_root / file_path
    pkg_root = workspace.find_owning_package(abs_file_path)

    # 2. Load the lock data for that package
    lock_data = lock_manager.load(pkg_root)

    # 3. Filter and re-key the data for the specific file
    # We want to return a dict of {fragment: fingerprint_dict} for just this file.
    ws_rel_path = workspace.to_workspace_relative(abs_file_path)
    file_prefix = f"py://{ws_rel_path}#"

    file_hashes = {}
    for suri, fp in lock_data.items():
        if suri.startswith(file_prefix):
            fragment = suri[len(file_prefix) :]
            file_hashes[fragment] = fp.to_dict()

    return file_hashes
