from pathlib import Path
from typing import Callable, Optional
from stitcher.config import StitcherConfig

from stitcher.common import bus
from needle.pointer import L
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
from stitcher.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.python import PythonAdapter


class RefactorRunner:
    def __init__(
        self,
        root_path: Path,
        index_store: IndexStore,
        file_indexer: FileIndexer,
    ):
        self.root_path = root_path
        self.index_store = index_store
        self.file_indexer = file_indexer

    def run_apply(
        self,
        migration_script: Path,
        config: StitcherConfig,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 0. Ensure index is up to date
            bus.info(L.index.run.start)
            workspace = Workspace(self.root_path, config)

            # Ensure the database schema is initialized before indexing.
            from stitcher.index.db import DatabaseManager

            db_manager = DatabaseManager(
                self.root_path / ".stitcher" / "index" / "index.db"
            )
            db_manager.initialize()

            # The FileIndexer was created with an unconfigured workspace.
            # We must re-register the adapter with the correct search paths.
            self.file_indexer.register_adapter(
                ".py", PythonAdapter(self.root_path, workspace.get_search_paths())
            )

            files_to_index = workspace.discover_files()
            self.file_indexer.index_files(files_to_index)

            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            bus.debug(
                L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
            )
            sidecar_manager = SidecarManager(self.root_path)
            graph = SemanticGraph(workspace, self.index_store)

            graph.load_from_workspace()

            ctx = RefactorContext(
                workspace=workspace,
                graph=graph,
                sidecar_manager=sidecar_manager,
                index_store=self.index_store,
            )

            # 2. Load and plan the migration
            bus.info(L.refactor.run.planning)
            loader = MigrationLoader()
            spec = loader.load_from_path(migration_script)

            planner = Planner()
            file_ops = planner.plan(spec, ctx)
            bus.debug(L.debug.log.refactor_planned_ops_count, count=len(file_ops))

            if not file_ops:
                bus.success(L.refactor.run.no_ops)
                return True

            # 3. Preview
            from stitcher.common.transaction import (
                WriteFileOp,
                MoveFileOp,
                DeleteFileOp,
                DeleteDirectoryOp,
            )

            tm = TransactionManager(self.root_path)
            for op in file_ops:
                if isinstance(op, WriteFileOp):
                    tm.add_write(op.path, op.content)
                elif isinstance(op, MoveFileOp):
                    tm.add_move(op.path, op.dest)
                elif isinstance(op, DeleteFileOp):
                    tm.add_delete_file(op.path)
                elif isinstance(op, DeleteDirectoryOp):
                    tm.add_delete_dir(op.path)

            bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
            for desc in tm.preview():
                bus.info(desc)

            if dry_run:
                return True

            # 4. Confirm (via callback)
            if confirm_callback:
                if not confirm_callback(tm.pending_count):
                    bus.error(L.refactor.run.aborted)
                    return False

            # 5. Execute
            bus.info(L.refactor.run.applying)
            tm.commit()
            bus.success(L.refactor.run.success, count=len(file_ops))
            return True

        except (MigrationError, FileNotFoundError) as e:
            bus.error(L.error.generic, error=str(e))
            return False
        except Exception as e:
            bus.error(L.error.generic, error=f"An unexpected error occurred: {e}")
            return False
