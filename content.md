I've analyzed the new set of failures. It seems my previous fixes were on the right track but incomplete. There are still lingering issues with outdated test assertions using invalid `Fingerprint` keys, and more complex bugs in the `Planner`'s logic that my previous refactoring didn't fully resolve.

Here is my plan:
1.  **Correct All Remaining `Fingerprint` Key Errors**: I will meticulously go through the provided failing test files and replace all invalid keys like `hash` with the correct key, `baseline_code_structure_hash`.
2.  **Fix Flawed Test Logic**: The `Planner` unit test `test_planner_handles_move_and_rename_on_same_file` has an incorrect assertion about the number of expected operations. I will correct it to reflect the new reality where a lock file update is also generated.
3.  **Address the Core `Planner` Bug**: The most critical failure is in `test_refactor_move_updates_suri_in_signatures.py`, which proves the `Planner` is still not correctly updating `stitcher.lock` during file moves. The old SURI is not being removed. My previous `Planner` implementation was flawed. I will rewrite the lock file processing logic inside the `Planner` to be more robust and direct, ensuring that cross-package moves are handled correctly and that all dictionary modifications are properly persisted.

#### Acts 1: Fix Remaining Invalid `Fingerprint` Keys

I will correct the `Fingerprint` keys in the test setup and assertions.

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python.old
    assert updated_lock_data[new_suri] == {"hash": "abc"}
~~~~~
~~~~~python.new
    assert updated_lock_data[new_suri] == {"baseline_code_structure_hash": "abc"}
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_suri_update.py
~~~~~
~~~~~python.old
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "123"})}
~~~~~
~~~~~python.new
    fingerprints = {old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "123"})}
~~~~~
~~~~~python.old
    assert updated_data[new_suri]["hash"] == "123"
~~~~~
~~~~~python.new
    assert updated_data[new_suri]["baseline_code_structure_hash"] == "123"
~~~~~

#### Acts 2: Correct `Planner` Unit Test

I will fix the incorrect assertion count in the unit test to reflect the addition of the lock file write operation.

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python.old
def test_planner_handles_move_and_rename_on_same_file(mock_context: Mock):
    """
    Verifies that a file move and symbol renames within that file are planned correctly,
    resulting in a MoveOp and a single WriteOp with merged content.
    """
    # 1. ARRANGE
    src_path_rel = Path("app.py")
    dest_path_rel = Path("new_app.py")
    src_path_abs = mock_context.graph.root_path / src_path_rel
    original_content = "class OldClass: pass"

    # Define operations
    move_op = MoveFileOperation(
        src_path_abs, mock_context.graph.root_path / dest_path_rel
    )
    rename_op = RenameSymbolOperation("app.OldClass", "new_app.NewClass")
    spec = MigrationSpec().add(move_op).add(rename_op)

    # Mock find_usages
    mock_context.graph.find_usages.return_value = [
        UsageLocation(src_path_abs, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")
    ]

    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # We expect two ops: one MoveFileOp and one WriteFileOp
    assert len(file_ops) == 2

    move_ops = [op for op in file_ops if isinstance(op, MoveFileOp)]
    write_ops = [op for op in file_ops if isinstance(op, WriteFileOp)]

    assert len(move_ops) == 1
    assert len(write_ops) == 1

    # Verify the MoveOp
    assert move_ops[0].path == src_path_rel
    assert move_ops[0].dest == dest_path_rel

    # Verify the WriteOp
    # The planner generates the write for the ORIGINAL path. The TransactionManager
    # is responsible for rebasing it to the new path.
    assert write_ops[0].path == src_path_rel
    assert "class NewClass: pass" in write_ops[0].content
~~~~~
~~~~~python.new
def test_planner_handles_move_and_rename_on_same_file(mock_context: Mock):
    """
    Verifies a file move and symbol rename are planned correctly, resulting
    in a MoveOp, a WriteOp for the code, and a WriteOp for the lock file.
    """
    # 1. ARRANGE
    src_path_rel = Path("app.py")
    dest_path_rel = Path("new_app.py")
    src_path_abs = mock_context.graph.root_path / src_path_rel
    original_content = "class OldClass: pass"

    move_op = MoveFileOperation(src_path_abs, mock_context.graph.root_path / dest_path_rel)
    rename_op = RenameSymbolOperation("app.OldClass", "new_app.NewClass")
    spec = MigrationSpec().add(move_op).add(rename_op)

    mock_context.graph.find_usages.return_value = [
        UsageLocation(src_path_abs, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")
    ]

    from unittest.mock import patch
    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # Expect 3 ops: MoveOp (code), WriteOp (code), WriteOp (lock)
    assert len(file_ops) == 3

    move_ops = [op for op in file_ops if isinstance(op, MoveFileOp)]
    write_ops = {op.path.name: op for op in file_ops if isinstance(op, WriteFileOp)}

    assert len(move_ops) == 1
    assert len(write_ops) == 2
    assert "app.py" in write_ops
    assert "stitcher.lock" in write_ops

    assert move_ops[0].path == src_path_rel
    assert move_ops[0].dest == dest_path_rel

    # The write op for code should target the original path.
    # The TransactionManager will rebase this write if needed.
    assert "class NewClass: pass" in write_ops["app.py"].content
~~~~~

#### Acts 3: Final Robust Fix for `Planner`

This rewrite directly addresses the bug causing `test_refactor_move_updates_suri_in_signatures.py` to fail. I will replace the entire `planner.py` file with this corrected version, which ensures lock file modifications are calculated and applied correctly.

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, TYPE_CHECKING

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

        module_rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                old_mod_fqn = path_to_fqn(intent.src_path, ctx.graph.search_paths)
                new_mod_fqn = path_to_fqn(intent.dest_path, ctx.graph.search_paths)
                if old_mod_fqn and new_mod_fqn:
                    module_rename_map[old_mod_fqn] = new_mod_fqn

        # Aggregate and process sidecar updates
        sidecar_updates: defaultdict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        sidecar_adapter = SidecarAdapter(ctx.workspace.root_path)
        sidecar_transformer = SidecarTransformer()
        
        for path, intents in sidecar_updates.items():
            if path.suffix not in [".yaml", ".yml"]:
                continue

            data = sidecar_adapter.load_raw_data(path)
            for intent in intents:
                old_module_fqn = intent.module_fqn
                new_module_fqn = (
                    module_rename_map.get(old_module_fqn, old_module_fqn)
                    if old_module_fqn
                    else None
                )
                transform_ctx = SidecarTransformContext(
                    old_module_fqn=old_module_fqn,
                    new_module_fqn=new_module_fqn,
                    old_fqn=intent.old_fqn,
                    new_fqn=intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )
                data = sidecar_transformer.transform(path, data, transform_ctx)

            content = sidecar_adapter.dump_raw_data_to_string(data)
            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # --- Process Lock Update Intents ---
        lock_states: Dict[Path, Dict[str, Fingerprint]] = {}

        def get_lock_data(pkg_root: Path) -> Dict[str, Fingerprint]:
            if pkg_root not in lock_states:
                lock_states[pkg_root] = ctx.lock_manager.load(pkg_root)
            return lock_states[pkg_root]

        lock_intents = [i for i in all_intents if isinstance(i, (LockSymbolUpdateIntent, LockPathUpdateIntent))]
        
        for intent in lock_intents:
            if isinstance(intent, LockPathUpdateIntent):
                old_abs_path = ctx.workspace.root_path / intent.old_path_prefix
                new_abs_path = ctx.workspace.root_path / intent.new_path_prefix
                src_pkg_root = ctx.workspace.find_owning_package(old_abs_path)
                dest_pkg_root = ctx.workspace.find_owning_package(new_abs_path)
                
                src_data = get_lock_data(src_pkg_root)
                dest_data = get_lock_data(dest_pkg_root) if src_pkg_root != dest_pkg_root else src_data
                
                uris_to_move = {}
                for suri, fp in src_data.items():
                    path, fragment = PythonURIGenerator.parse(suri)
                    if path == intent.old_path_prefix or path.startswith(intent.old_path_prefix + "/"):
                        new_path = path.replace(intent.old_path_prefix, intent.new_path_prefix, 1)
                        # TODO: Phase 3 Inject URIGenerator
                        uri_gen = PythonURIGenerator()
                        new_suri = uri_gen.generate_symbol_uri(new_path, fragment) if fragment else uri_gen.generate_file_uri(new_path)
                        uris_to_move[suri] = (new_suri, fp)

                for old_suri, (new_suri, fp) in uris_to_move.items():
                    del src_data[old_suri]
                    dest_data[new_suri] = fp
            
            elif isinstance(intent, LockSymbolUpdateIntent):
                data = get_lock_data(intent.package_root)
                if intent.old_suri in data:
                    data[intent.new_suri] = data.pop(intent.old_suri)

        for pkg_root, data in lock_states.items():
            content = ctx.lock_manager.serialize(data)
            rel_lock_path = (pkg_root / "stitcher.lock").relative_to(ctx.graph.root_path)
            all_ops.append(WriteFileOp(rel_lock_path, content))

        # Process simple filesystem intents
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                all_ops.append(MoveFileOp(intent.src_path.relative_to(ctx.graph.root_path), intent.dest_path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, DeleteFileIntent):
                all_ops.append(DeleteFileOp(intent.path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, DeleteDirectoryIntent):
                all_ops.append(DeleteDirectoryOp(intent.path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, ScaffoldIntent):
                all_ops.append(WriteFileOp(intent.path.relative_to(ctx.graph.root_path), intent.content))

        return all_ops
~~~~~
