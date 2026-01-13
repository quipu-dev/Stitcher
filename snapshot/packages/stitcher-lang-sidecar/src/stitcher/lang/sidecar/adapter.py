import json
from pathlib import Path
from typing import List, Tuple

from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_yaml_references, parse_json_references


class SidecarAdapter(LanguageAdapter):
    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        if file_path.suffix == ".yaml":
            refs = parse_yaml_references(content)
            for ref_fqn, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=ref_fqn,
                        target_id=None,  # Will be resolved by the Linker
                        kind="yaml_fqn",
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(ref_fqn),
                    )
                )
        elif file_path.suffix == ".json":
            refs = parse_json_references(content)
            for ref_suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,  # This is a by-id reference
                        target_id=ref_suri,  # The key IS the target ID
                        kind="json_suri",
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(ref_suri) + 2,  # +2 for quotes
                    )
                )

        return symbols, references