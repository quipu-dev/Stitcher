from stitcher.common import bus
from needle.pointer import L
from stitcher.index.db import DatabaseManager
from stitcher.index.indexer import FileIndexer
from stitcher.workspace import Workspace


class IndexRunner:
    def __init__(self, db_manager: DatabaseManager, indexer: FileIndexer):
        self.db_manager = db_manager
        self.indexer = indexer

    def run_build(self, workspace: Workspace) -> bool:
        # Ensure DB is initialized (schema created)
        self.db_manager.initialize()

        # Discover files using the workspace
        files_to_index = workspace.discover_files()

        bus.info(L.index.run.start)
        stats = self.indexer.index_files(files_to_index)

        bus.success(
            L.index.run.complete,
            added=stats["added"],
            updated=stats["updated"],
            deleted=stats["deleted"],
            skipped=stats["skipped"],
        )
        return True
