from stitcher.common import bus
from needle.pointer import L
from stitcher.index.db import DatabaseManager
from stitcher.index.scanner import WorkspaceScanner


class IndexRunner:
    def __init__(self, db_manager: DatabaseManager, scanner: WorkspaceScanner):
        self.db_manager = db_manager
        self.scanner = scanner

    def run_build(self) -> bool:
        # Ensure DB is initialized (schema created)
        self.db_manager.initialize()

        bus.info(L.index.run.start)
        stats = self.scanner.scan()

        bus.success(
            L.index.run.complete,
            added=stats["added"],
            updated=stats["updated"],
            deleted=stats["deleted"],
            skipped=stats["skipped"],
        )
        return True
