from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.spec import RefactorUsage
from stitcher.lang.python.analysis.models import UsageLocation


class GlobalBatchRenamer:
    def __init__(self, rename_map: Dict[str, str], ctx: RefactorContext):
        self.rename_map = rename_map
        self.ctx = ctx

    def _adapt_usage(self, usage: UsageLocation) -> RefactorUsage:
        """Adapts the internal, detailed UsageLocation to the generic RefactorUsage."""
        from stitcher.spec.models import SourceLocation
        return RefactorUsage(
            location=SourceLocation(
                lineno=usage.lineno,
                col_offset=usage.col_offset,
                end_lineno=usage.end_lineno,
                end_col_offset=usage.end_col_offset,
            ),
        )

    def analyze(self) -> List[WriteFileOp]:
        ops: List[WriteFileOp] = []
        
        # Group usages by file path, and then by the FQN being renamed.
        # This is crucial for applying multiple renames to a single file correctly.
        usages_by_file_and_fqn: Dict[Path, Dict[str, List[UsageLocation]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # 1. Collect all usages for all renames
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file_and_fqn[usage.file_path][old_fqn].append(usage)

        # 2. For each affected file, apply all relevant transformations
        for file_path, fqn_to_usages in usages_by_file_and_fqn.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                modified_source = original_source

                # Get the appropriate strategy for this file type
                strategy = self.ctx.strategy_registry.get(file_path.suffix)
                if not strategy:
                    # Log a warning? For now, we just skip files without a strategy.
                    continue

                # Apply renames one by one to the source string.
                # This is safe because usages are based on original locations, and we
                # are modifying the code in place for each symbol.
                # A more advanced implementation might use CST modification for all
                # symbols at once, but this is simpler and effective.
                for old_fqn, usages in fqn_to_usages.items():
                    new_fqn = self.rename_map[old_fqn]
                    
                    refactor_usages = [self._adapt_usage(u) for u in usages]
                    
                    modified_source = strategy.rename_symbol(
                        modified_source,
                        refactor_usages,
                        old_name=old_fqn,
                        new_name=new_fqn,
                    )

                if modified_source != original_source:
                    relative_path = file_path.relative_to(self.ctx.graph.root_path)
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_source)
                    )
            except Exception:
                # In a real app, we'd log this, but for now, re-raise
                raise
        return ops