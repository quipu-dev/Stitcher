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
        # Store tuples of (UsageLocation, triggering_old_fqn)
        usages_by_file: Dict[Path, List[tuple[UsageLocation, str]]] = defaultdict(list)

        # 1. Collect all usages for all renames
        for old_fqn in rename_map.keys():
            for usage in ctx.graph.find_usages(old_fqn):
                usages_by_file[usage.file_path].append((usage, old_fqn))

        # 2. For each affected file, generate a single WriteFileOp
        for file_path, items in usages_by_file.items():
            # Unpack locations for Python transformer which expects list[UsageLocation]
            locations = [item[0] for item in items]
            
            content = file_path.read_text("utf-8")
            new_content = None

            if file_path.suffix == ".py":
                new_content = self._transform_python_file(content, locations, rename_map)
            elif file_path.suffix in (".yaml", ".yml"):
                # For YAML, the key is the FQN.
                sidecar_rename_map = {}
                for loc, old_fqn in items:
                    # Prefer the FQN from the location if available (it should be equal to old_fqn for YAML)
                    key = loc.target_node_fqn or old_fqn
                    if key in rename_map:
                        sidecar_rename_map[key] = rename_map[key]
                        
                new_content = self._sidecar_updater.update_keys(
                    content, sidecar_rename_map, is_yaml=True
                )
            elif file_path.suffix == ".json":
                # For JSON, the key is the SURI. 
                suri_rename_map = {}
                for loc, old_fqn in items:
                    # For Signature files, target_node_id IS the key (SURI).
                    # target_node_fqn might be None.
                    # We rely on old_fqn passed from the loop to know what we are renaming.
                    
                    if not loc.target_node_id:
                        continue

                    old_suri = loc.target_node_id
                    
                    if old_fqn in rename_map:
                        new_fqn = rename_map[old_fqn]

                        # Reconstruct SURI.
                        try:
                            path, old_fragment = SURIGenerator.parse(old_suri)
                            # We need to compute the new fragment.
                            # old_fqn: pkg.mod.Class
                            # new_fqn: pkg.mod.NewClass
                            # Logic: Replace the suffix of the fragment that corresponds to the changed part of FQN.
                            
                            # Simplistic approach: calculate the new short name
                            # This works for simple renames.
                            # For nested renames (Class.method), SURIGenerator.parse handles #Class.method
                            
                            old_short_name = old_fqn.split(".")[-1]
                            new_short_name = new_fqn.split(".")[-1]
                            
                            # This is still a bit heuristic. A robust way is needed.
                            # If old_fragment ends with old_short_name, replace it.
                            if old_fragment and old_fragment.endswith(old_short_name):
                                new_fragment = old_fragment[: -len(old_short_name)] + new_short_name
                                new_suri = SURIGenerator.for_symbol(path, new_fragment)
                                suri_rename_map[old_suri] = new_suri
                                
                        except (ValueError, AttributeError):
                            continue

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