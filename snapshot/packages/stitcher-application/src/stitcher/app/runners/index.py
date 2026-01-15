from stitcher.bus import bus
from needle.pointer import L
from stitcher.index.db import DatabaseManager
from stitcher.index.indexer import FileIndexer
from stitcher.workspace import Workspace
from typing import Dict, Any


class IndexRunner:
    def __init__(self, db_manager: DatabaseManager, indexer: FileIndexer):
        self.db_manager = db_manager
        self.indexer = indexer

    def run_build(self, workspace: Workspace) -> Dict[str, Any]:
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
            sidecars=stats.get("sidecars", 0),
        )

        if stats.get("errors", 0) > 0:
            # Report the first detailed error to give the user immediate context
            if stats["error_details"]:
                path, err = stats["error_details"][0]
                bus.error(L.error.generic, error=f"Failed to parse {path}: {err}")
            else:
                bus.error(
                    L.error.generic,
                    error=f"Failed to index {stats['errors']} file(s). Check logs for details.",
                )
            stats["success"] = False
            return stats

        stats["success"] = True
        return stats
