from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING, Any

from stitcher.common.adapters.yaml_adapter import YamlAdapter
import json

if TYPE_CHECKING:
    from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    FileOp,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
    DeleteDirectoryOp,
)
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.refactor.operations.base import SidecarUpdateMixin
from stitcher.adapter.python.uri import SURIGenerator


class Planner(SidecarUpdateMixin):
    def _update_signature_file_data(
        self,
        data: Dict[str, Any],
        src_path_abs: Path,
        dest_path_abs: Path,
        ctx: RefactorContext,
    ) -> Dict[str, Any]:
        """Updates SURI keys in a signature file dictionary."""
        new_data = {}
        src_path_rel_str = src_path_abs.relative_to(ctx.workspace.root_path).as_posix()
        dest_path_rel_str = dest_path_abs.relative_to(
            ctx.workspace.root_path
        ).as_posix()

        for suri, value in data.items():
            try:
                path_str, fragment = SURIGenerator.parse(suri)
                if path_str == src_path_rel_str:
                    new_suri = SURIGenerator.build(dest_path_rel_str, fragment)
                    new_data[new_suri] = value
                else:
                    new_data[suri] = value
            except ValueError:
                # Not a valid SURI, preserve it as is
                new_data[suri] = value
        return new_data

    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []

        # --- 1. Intent Collection ---
        all_intents: List[RefactorIntent] = []
        for operation in spec.operations:
            all_intents.extend(operation.collect_intents(ctx))

        # --- 2. Intent Aggregation & Processing ---

        # Aggregate renames for batch processing
        rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, RenameIntent):
                rename_map[intent.old_fqn] = intent.new_fqn

        # Process symbol renames in code
        renamer = GlobalBatchRenamer(rename_map, ctx)
        all_ops.extend(renamer.analyze())

        # Aggregate and process sidecar updates
        sidecar_updates: DefaultDict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        yaml_adapter = YamlAdapter()
        for path, intents in sidecar_updates.items():
            is_sig_file = path.suffix == ".json"
            is_doc_file = path.suffix == ".yaml"

            if is_doc_file:
                data = yaml_adapter.load(path)
            elif is_sig_file:
                data = json.loads(path.read_text("utf-8")) if path.exists() else {}
            else:
                continue  # Skip unknown sidecar types

            for intent in intents:
                # Use SURI-aware logic for signature files if path info is available
                if is_sig_file and intent.src_path and intent.dest_path:
                    data = self._update_signature_file_data(
                        data, intent.src_path, intent.dest_path, ctx
                    )
                # Use FQN-based logic for doc files
                elif is_doc_file:
                    data = self._update_sidecar_data(
                        data, intent.module_fqn, intent.old_fqn, intent.new_fqn
                    )

            if is_doc_file:
                content = yaml_adapter.dump(data)
            else:  # is_sig_file
                content = json.dumps(data, indent=2, sort_keys=True)

            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # Process simple filesystem intents
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                all_ops.append(
                    MoveFileOp(
                        intent.src_path.relative_to(ctx.graph.root_path),
                        intent.dest_path.relative_to(ctx.graph.root_path),
                    )
                )
            elif isinstance(intent, DeleteFileIntent):
                all_ops.append(
                    DeleteFileOp(intent.path.relative_to(ctx.graph.root_path))
                )
            elif isinstance(intent, DeleteDirectoryIntent):
                all_ops.append(
                    DeleteDirectoryOp(intent.path.relative_to(ctx.graph.root_path))
                )
            elif isinstance(intent, ScaffoldIntent):
                all_ops.append(
                    WriteFileOp(
                        intent.path.relative_to(ctx.graph.root_path), intent.content
                    )
                )

        return all_ops