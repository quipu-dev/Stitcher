import libcst as cst
from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.lang.python.analysis.models import UsageLocation
from stitcher.refactor.operations.transforms.rename_transformer import (
    SymbolRenamerTransformer,
)


class GlobalBatchRenamer:
    def __init__(self, rename_map: Dict[str, str], ctx: RefactorContext):
        self.rename_map = rename_map
        self.ctx = ctx

    def analyze(self) -> List[WriteFileOp]:
        ops: List[WriteFileOp] = []
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)

        # 1. Collect all usages for all renames and group by file
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, apply a single transformation that handles ALL renames
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)
                wrapper = cst.MetadataWrapper(module)

                # The key difference: The transformer receives the GLOBAL rename map
                # and a complete list of locations to modify within this file.
                transformer = SymbolRenamerTransformer(self.rename_map, file_usages)
                modified_module = wrapper.visit(transformer)

                if modified_module.code != original_source:
                    relative_path = file_path.relative_to(self.ctx.graph.root_path)
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )
            except Exception:
                # In a real app, we'd log this, but for now, re-raise
                raise
        return ops
