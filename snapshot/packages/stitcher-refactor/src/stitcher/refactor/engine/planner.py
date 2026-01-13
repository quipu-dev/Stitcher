from collections import defaultdict
from pathlib import Path
from typing import List, Dict, TYPE_CHECKING
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
from stitcher.spec import Fingerprint


class Planner:
    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        # --- 1. Intent Collection ---
        all_intents: List[RefactorIntent] = []
        for operation in spec.operations:
            all_intents.extend(operation.collect_intents(ctx))

        # --- 2. Intent Aggregation & Processing ---
        
        # Use dictionaries to merge operations on the same file path
        write_ops: Dict[Path, WriteFileOp] = {}
        other_ops: List[FileOp] = []

        # Aggregate renames for batch processing
        rename_map: Dict[str, str] = {
            intent.old_fqn: intent.new_fqn
            for intent in all_intents
            if isinstance(intent, RenameIntent)
        }

        # Process symbol renames in code
        for op in GlobalBatchRenamer(rename_map, ctx).analyze():
            write_ops[op.path] = op

        module_rename_map: Dict[str, str] = {
            path_to_fqn(intent.src_path, ctx.graph.search_paths): path_to_fqn(intent.dest_path, ctx.graph.search_paths)
            for intent in all_intents
            if isinstance(intent, MoveFileIntent) and path_to_fqn(intent.src_path, ctx.graph.search_paths) and path_to_fqn(intent.dest_path, ctx.graph.search_paths)
        }

        # Aggregate and process sidecar updates
        sidecar_updates: defaultdict[Path, List[SidecarUpdateIntent]] = defaultdict(list)
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        sidecar_adapter = SidecarAdapter(ctx.workspace.root_path)
        sidecar_transformer = SidecarTransformer()
        for path, intents in sidecar_updates.items():
            rel_path = path.relative_to(ctx.graph.root_path)
            # Start with existing planned content if available, else load from disk
            initial_content = write_ops[rel_path].content if rel_path in write_ops else (path.read_text("utf-8") if path.exists() else "{}")
            
            is_yaml = path.suffix in [".yaml", ".yml"]
            data = yaml.safe_load(initial_content) if is_yaml else json.loads(initial_content)
            
            for intent in intents:
                old_module_fqn = intent.module_fqn
                new_module_fqn = module_rename_map.get(old_module_fqn, old_module_fqn) if old_module_fqn else None
                transform_ctx = SidecarTransformContext(
                    old_module_fqn=old_module_fqn, new_module_fqn=new_module_fqn,
                    old_fqn=intent.old_fqn, new_fqn=intent.new_fqn,
                    old_file_path=intent.old_file_path, new_file_path=intent.new_file_path
                )
                data = sidecar_transformer.transform(path, data, transform_ctx)

            content = sidecar_adapter.dump_raw_data_to_string(data) if is_yaml else json.dumps(data, indent=2, sort_keys=True)
            write_ops[rel_path] = WriteFileOp(rel_path, content)


        # --- Process Lock Update Intents ---
        lock_states: Dict[Path, Dict[str, Fingerprint]] = {}

        def get_lock_data(pkg_root: Path) -> Dict[str, Fingerprint]:
            if pkg_root not in lock_states:
                rel_lock_path = (pkg_root / "stitcher.lock").relative_to(ctx.graph.root_path)
                if rel_lock_path in write_ops:
                    # If planner already decided to write to the lock file, load that state
                    # This is complex; for now, assume we load from disk first.
                    lock_states[pkg_root] = ctx.lock_manager.load(pkg_root)
                else:
                    lock_states[pkg_root] = ctx.lock_manager.load(pkg_root)
            return lock_states[pkg_root]

        sorted_lock_intents = sorted(
            [i for i in all_intents if isinstance(i, (LockSymbolUpdateIntent, LockPathUpdateIntent))],
            key=lambda x: 0 if isinstance(x, LockPathUpdateIntent) else 1,
        )

        for intent in sorted_lock_intents:
            if isinstance(intent, LockPathUpdateIntent):
                src_pkg = ctx.workspace.find_owning_package(ctx.workspace.root_path / intent.old_path_prefix)
                dest_pkg = ctx.workspace.find_owning_package(ctx.workspace.root_path / intent.new_path_prefix)
                src_data = get_lock_data(src_pkg)

                suris_to_move = {}
                for suri in list(src_data.keys()):
                    path, fragment = PythonURIGenerator.parse(suri)
                    new_path = None
                    if path == intent.old_path_prefix:
                        new_path = intent.new_path_prefix
                    elif path.startswith(intent.old_path_prefix + "/"):
                        suffix = path[len(intent.old_path_prefix) :]
                        new_path = intent.new_path_prefix + suffix

                    if new_path:
                        uri_gen = PythonURIGenerator()
                        new_suri = uri_gen.generate_symbol_uri(new_path, fragment) if fragment else uri_gen.generate_file_uri(new_path)
                        suris_to_move[suri] = new_suri

                if src_pkg == dest_pkg:
                    for old, new in suris_to_move.items():
                        if old in src_data:
                            src_data[new] = src_data.pop(old)
                else:
                    dest_data = get_lock_data(dest_pkg)
                    for old, new in suris_to_move.items():
                        if old in src_data:
                            dest_data[new] = src_data.pop(old)

            elif isinstance(intent, LockSymbolUpdateIntent):
                data = get_lock_data(intent.package_root)
                if intent.old_suri in data:
                    data[intent.new_suri] = data.pop(intent.old_suri)

        for pkg_root, data in lock_states.items():
            content = ctx.lock_manager.serialize(data)
            rel_lock_path = (pkg_root / "stitcher.lock").relative_to(ctx.graph.root_path)
            write_ops[rel_lock_path] = WriteFileOp(rel_lock_path, content)

        # Process simple filesystem intents
        for intent in all_intents:
            rel_src_path = intent.src_path.relative_to(ctx.graph.root_path) if hasattr(intent, 'src_path') else None
            rel_dest_path = intent.dest_path.relative_to(ctx.graph.root_path) if hasattr(intent, 'dest_path') else None
            rel_path = intent.path.relative_to(ctx.graph.root_path) if hasattr(intent, 'path') else None

            if isinstance(intent, MoveFileIntent):
                other_ops.append(MoveFileOp(rel_src_path, rel_dest_path))
            elif isinstance(intent, DeleteFileIntent):
                other_ops.append(DeleteFileOp(rel_path))
            elif isinstance(intent, DeleteDirectoryIntent):
                other_ops.append(DeleteDirectoryOp(rel_path))
            elif isinstance(intent, ScaffoldIntent):
                 # Merge scaffold with existing writes if possible
                if rel_path in write_ops:
                    # Typically, a scaffold is for an empty file. If something else
                    # is writing to it, that takes precedence. This logic might need refinement.
                    pass
                else:
                    write_ops[rel_path] = WriteFileOp(rel_path, intent.content)

        return list(write_ops.values()) + other_ops