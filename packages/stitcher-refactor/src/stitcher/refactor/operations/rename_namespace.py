import libcst as cst

from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from .base import AbstractOperation
from .transforms.rename_namespace_transformer import NamespaceRenamerTransformer
from stitcher.refactor.types import RefactorContext
from stitcher.common.transaction import FileOp, WriteFileOp
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType


class RenameNamespaceOperation(AbstractOperation):
    def __init__(self, old_prefix: str, new_prefix: str):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        usages = ctx.graph.find_usages(self.old_prefix)
        import_usages = [u for u in usages if u.ref_type == ReferenceType.IMPORT_PATH]

        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)
        for usage in import_usages:
            usages_by_file[usage.file_path].append(usage)

        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)

                # Build locations map for the transformer
                locations = {(u.lineno, u.col_offset): u for u in file_usages}

                # Use standard MetadataWrapper
                wrapper = cst.MetadataWrapper(module)

                transformer = NamespaceRenamerTransformer(
                    self.old_prefix, self.new_prefix, locations
                )
                modified_module = wrapper.visit(transformer)

                relative_path = file_path.relative_to(ctx.graph.root_path)
                if modified_module.code != original_source:
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )
            except Exception:
                # In a real app, log this error
                raise

        return ops
