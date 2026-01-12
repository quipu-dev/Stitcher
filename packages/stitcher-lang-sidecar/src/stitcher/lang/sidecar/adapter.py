from pathlib import Path
from typing import List, Tuple

from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_sidecar_references


class SidecarAdapter(LanguageAdapter):
    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        # 1. Define the module symbol for the sidecar file itself
        # This allows the sidecar file to be tracked in the index.
        # rel_path = file_path.as_posix() # Assuming file_path passed in is relative or we handle it
        # Actually LanguageAdapter.parse receives file_path which might be absolute or relative
        # depending on caller. The caller (FileIndexer) usually passes absolute path
        # but expects records to contain info relevant for storage.
        # Usually SURIGenerator needs a relative path.
        # Let's assume the caller handles SURI generation or we create a specific SURI for sidecar?
        # For now, we only care about references.

        # 2. Extract references (keys)
        refs = parse_sidecar_references(content)
        for ref_fqn, line, col in refs:
            # We treat each top-level key as a reference to a Python symbol.
            # Kind is 'sidecar_key' so we can distinguish it later if needed.
            references.append(
                ReferenceRecord(
                    target_fqn=ref_fqn,
                    kind="sidecar_key",
                    lineno=line,
                    col_offset=col,
                    end_lineno=line,
                    end_col_offset=col + len(ref_fqn),
                )
            )

        return symbols, references
