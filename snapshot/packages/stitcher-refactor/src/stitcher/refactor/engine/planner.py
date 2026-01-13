from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING
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
    LockSymbolUpdateIntent,
    LockPathUpdateIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.lang.sidecar import (
    SidecarTransformer,
    SidecarTransformContext,
    SidecarAdapter,
)
from stitcher.lang.python.uri import PythonURIGenerator
from .utils import path_to_fqn


class Planner:
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
                # TODO: Handle rename chains (A->B, B->C should become A->C)
                rename_map[intent.old_fqn] = intent.new_fqn

        # Process symbol renames in code
        renamer = GlobalBatchRenamer(rename_map, ctx)
        all_ops.extend(renamer.analyze())

        # Build a map of module renames from move intents. This is the source of truth
        # for determining the new module FQN context.
        module_rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                old_mod_fqn = path_to_fqn(intent.src_path, ctx.graph.search_paths)
                new_mod_fqn = path_to_fqn(intent.dest_path, ctx.graph.search_paths)
                if old_mod_fqn and new_mod_fqn:
                    module_rename_map[old_mod_fqn] = new_mod_fqn

        # Aggregate and process sidecar updates
        sidecar_updates: DefaultDict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        sidecar_adapter = SidecarAdapter(ctx.workspace.root_path)
        sidecar_transformer = SidecarTransformer()
        for path, intents in sidecar_updates.items():
            # Load the sidecar file only once
            is_yaml = path.suffix in [".yaml", ".yml"]
            data = (
                sidecar_adapter.load_raw_data(path)
                if is_yaml
                else json.loads(path.read_text("utf-8"))
            )

            # Apply all intents for this file
            for intent in intents:
                old_module_fqn = intent.module_fqn
                if old_module_fqn is not None:
                    new_module_fqn = module_rename_map.get(old_module_fqn, old_module_fqn)
                else:
                    new_module_fqn = None

                transform_ctx = SidecarTransformContext(
                    old_module_fqn=old_module_fqn,
                    new_module_fqn=new_module_fqn,
                    old_fqn=intent.old_fqn,
                    new_fqn=intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )
                data = sidecar_transformer.transform(path, data, transform_ctx)

            # Dump the final state
            content = (
                sidecar_adapter.dump_raw_data_to_string(data)
                if is_yaml
                else json.dumps(data, indent=2, sort_keys=True)
            )
            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # --- Process Lock Update Intents ---
        # Group updates by package root (stitcher.lock location)
        lock_updates: DefaultDict[Path, List[RefactorIntent]] = defaultdict(list)
        for intent in all_intents:
            if isinstance(intent, (LockSymbolUpdateIntent, LockPathUpdateIntent)):
                lock_updates[intent.package_root].append(intent)

        for pkg_root, intents in lock_updates.items():
            lock_data = ctx.lock_manager.load(pkg_root)
            modified = False
            current_data = lock_data.copy()

            # Sort intents to process mass path updates before individual symbol renames
            intents.sort(key=lambda x: 0 if isinstance(x, LockPathUpdateIntent) else 1)

            for intent in intents:
                if isinstance(intent, LockPathUpdateIntent):
                    updates_to_make = {}  # old_suri -> new_suri
                    for suri in current_data.keys():
                        path, fragment = PythonURIGenerator.parse(suri)
                        new_path = None
                        if path == intent.old_path_prefix:
                            new_path = intent.new_path_prefix
                        elif path.startswith(intent.old_path_prefix + "/"):
                            suffix = path[len(intent.old_path_prefix) :]
                            new_path = intent.new_path_prefix + suffix

                        if new_path:
                            modified = True
                            uri_gen = PythonURIGenerator()
                            new_suri = (
                                uri_gen.generate_symbol_uri(new_path, fragment)
                                if fragment
                                else uri_gen.generate_file_uri(new_path)
                            )
                            updates_to_make[suri] = new_suri

                    for old_suri, new_suri in updates_to_make.items():
                        if old_suri in current_data:
                            current_data[new_suri] = current_data.pop(old_suri)

                elif isinstance(intent, LockSymbolUpdateIntent):
                    if intent.old_suri in current_data:
                        current_data[intent.new_suri] = current_data.pop(
                            intent.old_suri
                        )
                        modified = True

            if modified:
                content = ctx.lock_manager.serialize(current_data)
                rel_lock_path = (pkg_root / "stitcher.lock").relative_to(
                    ctx.graph.root_path
                )
                all_ops.append(WriteFileOp(rel_lock_path, content))

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
