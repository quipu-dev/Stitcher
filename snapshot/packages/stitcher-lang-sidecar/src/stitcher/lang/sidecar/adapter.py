from pathlib import Path
from typing import List, Tuple

from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
from stitcher.lang.python.uri import SURIGenerator
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarAdapter(LanguageAdapter):
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        if file_path.suffix == ".json":
            # --- Handle Signature File (.json) ---
            # Keys are SURIs (Identity References)
            refs = parse_signature_references(content)
            for suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,  # Pure ID reference
                        target_id=suri,  # The key IS the ID
                        kind=ReferenceType.SIDECAR_ID.value,
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )

        elif file_path.suffix in (".yaml", ".yml"):
            # --- Handle Doc File (.yaml) ---
            # Keys are Fragments, which we resolve to SURIs
            try:
                # 1. Resolve corresponding python file by reversing the doc path.
                # e.g. /path/to/file.stitcher.yaml -> /path/to/file.py
                if not file_path.name.endswith(".stitcher.yaml"):
                    return symbols, references
                
                py_name = file_path.name.replace(".stitcher.yaml", ".py")
                py_path = file_path.with_name(py_name)

                if not py_path.exists():
                     # If the corresponding .py file doesn't exist, this is a dangling sidecar.
                     # We can't generate SURIs, so we skip it.
                    return symbols, references

                rel_py_path = py_path.relative_to(self.root_path).as_posix()

                # 2. Parse fragments from YAML
                refs = parse_doc_references(content)
                for fragment, line, col in refs:
                    # 3. Compute SURI
                    suri = SURIGenerator.for_symbol(rel_py_path, fragment)

                    # 4. Create ReferenceRecord
                    references.append(
                        ReferenceRecord(
                            target_id=suri,  # Direct, strong reference
                            kind=ReferenceType.SIDECAR_DOC_ID.value,
                            lineno=line,
                            col_offset=col,
                            end_lineno=line,
                            end_col_offset=col + len(fragment),
                        )
                    )
            except (ValueError, FileNotFoundError):
                # If we can't find the source file, we can't generate SURIs.
                # In a real app, we might log a warning here.
                pass

        return symbols, references