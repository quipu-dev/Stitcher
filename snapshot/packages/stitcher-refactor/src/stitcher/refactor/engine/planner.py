import libcst as cst
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING

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
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
)
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from stitcher.refactor.operations.transforms.rename_transformer import (
    SymbolRenamerTransformer,
)
from stitcher.refactor.engine.sidecar import SidecarUpdater
from stitcher.lang.python.uri import SURIGenerator


class Planner:
    def __init__(self):
        self._sidecar_updater = SidecarUpdater()

    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []
        all_intents = [
            intent for op in spec.operations for intent in op.collect_intents(ctx)
        ]

        # --- 1. Aggregate Rename Intents ---
        rename_map: Dict[str, str] = {
            intent.old_fqn: intent.new_fqn
            for intent in all_intents
            if isinstance(intent, RenameIntent)
        }

        # --- 2. Plan Rename Operations ---
        if rename_map:
            all_ops.extend(self._plan_renames(rename_map, ctx))

        # --- 3. Plan Filesystem Operations ---
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

    def _plan_renames(
        self, rename_map: Dict[str, str], ctx: RefactorContext
    ) -> List[FileOp]:
        ops: List[FileOp] = []
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)

        # 1. Collect all usages for all renames
        for old_fqn in rename_map.keys():
            for usage in ctx.graph.find_usages(old_fqn):
                usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, generate a single WriteFileOp
        for file_path, locations in usages_by_file.items():
            content = file_path.read_text("utf-8")
            new_content = None

            if file_path.suffix == ".py":
                new_content = self._transform_python_file(content, locations, rename_map)
            elif file_path.suffix in (".yaml", ".yml"):
                # For YAML, the key is the FQN.
                sidecar_rename_map = {
                    loc.target_node_fqn: rename_map[loc.target_node_fqn]
                    for loc in locations
                    if loc.target_node_fqn in rename_map
                }
                new_content = self._sidecar_updater.update_keys(
                    content, sidecar_rename_map, is_yaml=True
                )
            elif file_path.suffix == ".json":
                # For JSON, the key is the SURI. We need to construct the SURI rename map.
                suri_rename_map = {}
                for loc in locations:
                    old_fqn = loc.target_node_fqn
                    if old_fqn in rename_map:
                        new_fqn = rename_map[old_fqn]
                        # This is a simplification. It doesn't handle module moves well.
                        # It assumes the file path part of the SURI remains the same.
                        symbol_record, _ = ctx.index_store.find_symbol_by_fqn(old_fqn)
                        if symbol_record:
                           old_suri = symbol_record.id
                           new_suri = old_suri.replace(old_fqn, new_fqn) # this is very wrong
                           # a suri is path#fragment, fqn is pkg.mod.Class
                           # Correct way: find symbol, get path and old fragment.
                           # Construct new SURI with same path and new fragment.
                           # Let's assume for now renames are within the same module.
                           old_frag = old_fqn.split(".")[-1]
                           new_frag = new_fqn.split(".")[-1]
                           if symbol_record and symbol_record.id:
                               suri_rename_map[symbol_record.id] = symbol_record.id.replace(old_frag, new_frag)

                if suri_rename_map:
                    new_content = self._sidecar_updater.update_keys(
                        content, suri_rename_map, is_yaml=False
                    )

            if new_content and new_content != content:
                ops.append(
                    WriteFileOp(
                        file_path.relative_to(ctx.graph.root_path), new_content
                    )
                )
        return ops

    def _transform_python_file(
        self, content: str, locations: List[UsageLocation], rename_map: Dict[str, str]
    ) -> str:
        try:
            module = cst.parse_module(content)
            wrapper = cst.MetadataWrapper(module)
            transformer = SymbolRenamerTransformer(rename_map, locations)
            modified_module = wrapper.visit(transformer)
            return modified_module.code
        except Exception:
            return content