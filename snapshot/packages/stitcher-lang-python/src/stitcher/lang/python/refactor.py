from pathlib import Path
from typing import List

import libcst as cst

from stitcher.spec import (
    RefactoringStrategyProtocol,
    RefactorUsage,
)
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from stitcher.lang.python.transform.rename import SymbolRenamerTransformer


class PythonRefactoringStrategy(RefactoringStrategyProtocol):
    def rename_symbol(
        self,
        source_code: str,
        usages: List[RefactorUsage],
        old_name: str,
        new_name: str,
    ) -> str:
        if not usages:
            return source_code

        # 1. Adapt generic RefactorUsage to internal UsageLocation
        # The SymbolRenamerTransformer relies on 'target_node_fqn' (old_name) to verify
        # nodes before renaming.
        internal_locations: List[UsageLocation] = []
        dummy_path = Path("")  # Path is not used by the transformer for single-file ops

        for u in usages:
            loc = UsageLocation(
                file_path=dummy_path,
                lineno=u.location.lineno,
                col_offset=u.location.col_offset,
                end_lineno=u.location.end_lineno,
                end_col_offset=u.location.end_col_offset,
                ref_type=ReferenceType.SYMBOL,  # Default assumption
                target_node_fqn=old_name,
            )
            internal_locations.append(loc)

        # 2. Prepare the rename map
        rename_map = {old_name: new_name}

        # 3. Apply transformation
        try:
            module = cst.parse_module(source_code)
            wrapper = cst.MetadataWrapper(module)

            transformer = SymbolRenamerTransformer(rename_map, internal_locations)
            modified_module = wrapper.visit(transformer)

            return modified_module.code
        except Exception:
            # In case of syntax errors or other CST issues, return original code
            # Caller handles logging/error reporting
            return source_code
