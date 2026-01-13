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

        # --- 0. Build Path Move Map ---
        # We need this to correctly update SURIs when files are moved.
        path_move_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                # Store as string for easier lookup during SURI parsing
                src = intent.src_path.relative_to(ctx.graph.root_path).as_posix()
                dest = intent.dest_path.relative_to(ctx.graph.root_path).as_posix()
                path_move_map[src] = dest

        # --- 1. Aggregate Rename Intents ---
        rename_map: Dict[str, str] = {
            intent.old_fqn: intent.new_fqn
            for intent in all_intents
            if isinstance(intent, RenameIntent)
        }

        # --- 2. Plan Rename Operations ---
        if rename_map:
            all_ops.extend(self._plan_renames(rename_map, path_move_map, ctx))

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
        self,
        rename_map: Dict[str, str],
        path_move_map: Dict[str, str],
        ctx: RefactorContext,
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
                new_content = self._transform_python_file(
                    content, locations, rename_map
                )
            elif file_path.suffix in (".yaml", ".yml"):
                # For YAML, we pass the rename_map directly.
                # The SidecarUpdater now handles prefix matching, so we don't need to filter it here.
                # But to be safe and efficient, we could filter.
                # Actually, filtering is tricky because we might miss children not in items (if graph lookup failed for children).
                # But for now, we rely on SidecarUpdater's prefix logic.
                new_content = self._sidecar_updater.update_keys(
                    content, rename_map, is_yaml=True
                )
            elif file_path.suffix == ".json":
                # For JSON, the key is the SURI.
                suri_rename_map = {}
                for loc, old_fqn in items:
                    if not loc.target_node_id:
                        # Fallback: if it's an FQN key (legacy), treat it like YAML
                        key = loc.target_node_fqn or old_fqn
                        if key:
                            # Use SidecarUpdater's resolve logic by passing the map
                            # But here we are building a specific map for THIS file's keys
                            pass
                        continue

                    old_suri = loc.target_node_id

                    if old_fqn in rename_map:
                        new_fqn = rename_map[old_fqn]

                        # Reconstruct SURI.
                        try:
                            path, old_fragment = SURIGenerator.parse(old_suri)

                            # 1. Update Path if file was moved
                            if path in path_move_map:
                                path = path_move_map[path]

                            # 2. Update Fragment
                            # Logic: If the fragment starts with the old_fqn suffix? No.
                            # We assume the FQN structure mirrors the fragment structure somewhat.
                            # But FQN mapping is best.
                            # Calculate the suffix changed.
                            # old_fqn: A.B.C
                            # new_fqn: A.B.D
                            # fragment: C (or B.C)

                            # We can try to replace the part of the fragment that matches the changed part of FQN.
                            # BUT, we don't know exactly how FQN maps to fragment without more context.
                            # Heuristic: old_fqn and new_fqn usually share a prefix.
                            # Find common prefix length?
                            
                            # Simpler Heuristic:
                            # If fragment ends with old_short_name, replace it.
                            old_short_name = old_fqn.split(".")[-1]
                            new_short_name = new_fqn.split(".")[-1]

                            new_fragment = old_fragment
                            if old_fragment and old_fragment.endswith(old_short_name):
                                new_fragment = (
                                    old_fragment[: -len(old_short_name)]
                                    + new_short_name
                                )
                            
                            # If fragment didn't change but path did, we still need new SURI
                            new_suri = SURIGenerator.for_symbol(path, new_fragment)
                            suri_rename_map[old_suri] = new_suri

                        except (ValueError, AttributeError):
                            continue

                if suri_rename_map:
                    # Also mix in pure FQN renames for legacy keys in JSON
                    # This is a bit mixed, but if SidecarAdapter returned target_id=None,
                    # we would have skipped the loop above.
                    # We might want to pass rename_map too?
                    # Let's keep it simple: update SURI keys first.
                    
                    new_content = self._sidecar_updater.update_keys(
                        content, suri_rename_map, is_yaml=False
                    )
                    
                    # If we have legacy FQN keys that were found by FQN lookup (target_id=None),
                    # we should also apply rename_map to them.
                    # But SidecarUpdater processes the whole file. 
                    # If we pass a combined map?
                    # SURI keys and FQN keys are disjoint.
                    # Let's merge maps.
                    full_map = suri_rename_map.copy()
                    full_map.update(rename_map)
                    
                    new_content = self._sidecar_updater.update_keys(
                        content, full_map, is_yaml=False
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