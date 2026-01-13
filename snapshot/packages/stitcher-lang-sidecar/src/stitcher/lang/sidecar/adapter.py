from pathlib import Path
from typing import List, Tuple

from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_doc_references, parse_signature_references


class SidecarAdapter(LanguageAdapter):
    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        # We don't currently generate symbols for the sidecar file itself in the index,
        # as it's a secondary artifact. It's tracked via the 'files' table directly.
        
        if file_path.suffix == ".json":
            # --- Handle Signature File (.json) ---
            # Keys are SURIs (Identity References)
            refs = parse_signature_references(content)
            for suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,        # Pure ID reference
                        target_id=suri,         # The key IS the ID
                        kind="json_suri",       # Distinct kind
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )

        elif file_path.suffix in (".yaml", ".yml"):
            # --- Handle Doc File (.yaml) ---
            # Keys are FQNs (Name References)
            refs = parse_doc_references(content)
            for ref_fqn, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=ref_fqn,     # Name reference
                        target_id=None,         # Linker will resolve this
                        kind="yaml_fqn",        # Distinct kind
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(ref_fqn),
                    )
                )

        return symbols, references