import json
import hashlib
from pathlib import Path
from typing import List, Tuple

from ruamel.yaml import YAML

from stitcher.spec import URIGeneratorProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from .parser import parse_doc_references
from stitcher.lang.python.analysis.utils import path_to_logical_fqn


class SidecarIndexerAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
    ):
        self.root_path = root_path
        self.uri_generator = uri_generator
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        # Only process .stitcher.yaml files
        if not file_path.name.endswith(".stitcher.yaml"):
            return symbols, references

        # 1. Parse YAML to get data structure
        try:
            data = self._yaml.load(content)
        except Exception:
            return symbols, references

        if not isinstance(data, dict):
            return symbols, references

        # 2. Determine paths
        # file_path passed here might be absolute (from FileIndexer), ensure relative
        if file_path.is_absolute():
            try:
                rel_path = file_path.relative_to(self.root_path)
            except ValueError:
                # Fallback if path is outside root (unlikely given discovery logic)
                rel_path = file_path
        else:
            rel_path = file_path

        py_name = rel_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = rel_path.with_name(py_name)

        # Pre-calculate logical module FQN for linking
        logical_module_fqn = path_to_logical_fqn(py_path_rel.as_posix())

        # 3. Parse references with location info using the helper
        loc_map = {
            frag: (line, col) for frag, line, col in parse_doc_references(content)
        }

        for fragment, value in data.items():
            # Skip if it's not a valid key
            if not isinstance(fragment, str):
                continue

            # --- Build Symbol ---
            suri = self.uri_generator.generate_symbol_uri(str(rel_path), fragment)
            lineno, col_offset = loc_map.get(fragment, (0, 0))

            # STORE STRATEGY: Store raw View Data as JSON.
            # We don't convert to IR here because we don't know the docstring style yet.
            try:
                # Value is the ruamel object (str or dict/map), json dump it to store
                docstring_content_json = json.dumps(value, default=str, sort_keys=True)
                docstring_hash = hashlib.sha256(
                    docstring_content_json.encode("utf-8")
                ).hexdigest()
            except Exception:
                docstring_content_json = "{}"
                docstring_hash = "0" * 64

            symbol = SymbolRecord(
                id=suri,
                name=fragment,
                kind="doc_fragment",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset,
                logical_path=fragment,
                canonical_fqn=fragment,
                docstring_content=docstring_content_json,
                docstring_hash=docstring_hash,
                signature_hash=None,
                signature_text=None,
                alias_target_fqn=None,
                alias_target_id=None,
            )
            symbols.append(symbol)

            # --- Build Reference (Binding to Python) ---
            # Use Late Binding (FQN) instead of Early Binding (ID) to avoid Foreign Key constraint violations
            # if the Python file hasn't been indexed yet.
            target_fqn = f"{logical_module_fqn}.{fragment}"
            if fragment == "__doc__":
                target_fqn = logical_module_fqn

            ref = ReferenceRecord(
                source_file_id=None,
                target_fqn=target_fqn,
                target_id=None,  # Leave NULL, let Linker resolve it
                kind="doc_binding",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset + len(fragment),
            )
            references.append(ref)

        return symbols, references
