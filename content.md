Excellent. The test has failed exactly as predicted, confirming the bug. We are now in the "red" state of the TDD cycle. It's time to implement the fix and make the test pass.

Your diagnosis is precise: the refactoring process moves the signature file but fails to update its internal content—specifically the SURI keys which are now stale.

I will now generate the plan to fix this.

## [WIP] fix(refactor): Update SURI paths in signatures on file move

### 错误分析

The root cause of the bug is that the `SidecarUpdateIntent` processing logic within the `Planner` was designed to handle FQN (Fully Qualified Name) remapping, which works for `.stitcher.yaml` files, but it does not understand the SURI (Stitcher Uniform Resource Identifier) format used as keys in signature files (`.json`). When a file move occurs, the `Planner` correctly moves the signature file but applies the wrong transformation logic to its contents, leaving the path component of the SURI keys unchanged.

### 用户需求

The refactoring engine must update the path component of SURI keys within `.stitcher/signatures/*.json` files whenever the corresponding source Python file is moved using a `Move` or `MoveDir` operation.

### 评论

This is a critical integrity fix for the refactoring engine. Failing to update SURIs breaks the link between a symbol's signature and its source code location, undermining the core value proposition of Stitcher. Implementing this fix will make the `refactor` command truly holistic and reliable.

### 目标

1.  **Enhance `SidecarUpdateIntent`**: Modify the intent to optionally carry the source and destination paths of the primary file being moved. This makes the intent more expressive.
2.  **Update `MoveFileOperation`**: Modify the operation to populate these new path fields when creating a `SidecarUpdateIntent` for a signature file.
3.  **Implement SURI-aware logic in `Planner`**: Update the `Planner` to detect when it's processing a signature file update. It will then use a new, specific logic to parse each SURI key, replace the old path with the new one, and reconstruct the key, leaving the symbol fragment untouched.

### 基本原理

The solution involves making the communication between the `MoveFileOperation` and the `Planner` more explicit. By adding optional `src_path` and `dest_path` fields to `SidecarUpdateIntent`, we empower the `Planner` to make a more intelligent decision. When it receives an intent for a `.json` signature file that also contains these path attributes, it will invoke a new `_update_signature_file_data` method. This method will perform the precise SURI transformation required. For all other sidecar files (like `.stitcher.yaml`), it will fall back to the existing FQN-based remapping logic, ensuring no existing behavior is broken.

### 标签

#intent/fix #flow/ready #priority/high #comp/refactor #concept/suri #scope/core #ai/instruct #task/domain/refactor #task/object/suri-integrity #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Enhance `SidecarUpdateIntent`

First, I'll add the optional path fields to the `SidecarUpdateIntent` dataclass.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class SidecarUpdateIntent(RefactorIntent):
    sidecar_path: Path
    module_fqn: Optional[str]
    old_fqn: str
    new_fqn: str
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class SidecarUpdateIntent(RefactorIntent):
    sidecar_path: Path
    module_fqn: Optional[str]
    old_fqn: str
    new_fqn: str
    # Optional: For file types like signatures that need path info, not just FQN
    src_path: Optional[Path] = None
    dest_path: Optional[Path] = None
~~~~~

#### Acts 2: Update `MoveFileOperation` to provide path info

Now, I will modify `MoveFileOperation` to populate these new fields when creating the intent for signature files.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python.old
            sig_src_path = ctx.sidecar_manager.get_signature_path(src_path)
            if sig_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                    )
                )
~~~~~
~~~~~python.new
            sig_src_path = ctx.sidecar_manager.get_signature_path(src_path)
            if sig_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                        src_path=src_path,
                        dest_path=dest_path,
                    )
                )
~~~~~

#### Acts 3: Implement SURI update logic in the Planner

This is the core of the fix. I will update the `Planner` to handle the enhanced intent and perform the correct SURI transformation. Since this involves adding a new method and modifying the main planning loop, I'll provide the complete file.

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议

The fix is now fully implemented. The `Planner` is equipped to handle SURI transformations correctly. Please run the test suite again. The test `test_move_file_operation_updates_suri_in_signatures` should now pass, turning from "red" to "green," and confirming the bug has been resolved.
