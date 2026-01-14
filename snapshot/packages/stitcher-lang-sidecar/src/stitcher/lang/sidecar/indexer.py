import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Any, Optional

from ruamel.yaml import YAML

from stitcher.spec import URIGeneratorProtocol, DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.python.docstring import RawSerializer, GoogleSerializer, NumpySerializer
from stitcher.lang.sidecar.parser import parse_doc_references
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarIndexerAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
        serializer: Optional[DocstringSerializerProtocol] = None,
    ):
        self.root_path = root_path
        self.uri_generator = uri_generator
        # Default to RawSerializer if none provided, though ideally the app should inject the configured one.
        # However, for indexing, we need to handle whatever is in the file.
        # Since we don't know the style per file, we might need a robust way to deserialize.
        # For now, we use the injected serializer or Raw.
        self.serializer = serializer or RawSerializer()
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
        # file_path passed here is relative to project root (physical path)
        # We need to determine the companion Python file path for references
        py_name = file_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = file_path.with_name(py_name)
        
        # Note: We don't check if py_path exists on disk here, because we are indexing the sidecar itself.
        # The reference is valid intent even if the python file is missing (dangling reference).
        
        # 3. Parse references with location info using the helper
        # parse_doc_references returns list of (fragment, lineno, col_offset)
        # We use this to get accurate location info for symbols
        loc_map = {frag: (line, col) for frag, line, col in parse_doc_references(content)}

        for fragment, value in data.items():
            # Skip if it's not a valid key
            if not isinstance(fragment, str):
                continue
            
            # --- Build Symbol ---
            # 1. URI
            suri = self.uri_generator.generate_symbol_uri(str(file_path), fragment)
            
            # 2. Location
            lineno, col_offset = loc_map.get(fragment, (0, 0))
            
            # 3. Content (DocstringIR -> JSON)
            # Use the serializer to convert the YAML value (view data) to IR
            # Then convert IR to transfer data (JSON-safe dict) for storage
            try:
                ir = self.serializer.from_view_data(value)
                transfer_data = self.serializer.to_transfer_data(ir)
                docstring_content_json = json.dumps(transfer_data, sort_keys=True)
                docstring_hash = hashlib.sha256(docstring_content_json.encode("utf-8")).hexdigest()
            except Exception:
                # Fallback for malformed data
                docstring_content_json = "{}"
                docstring_hash = "0" * 64

            symbol = SymbolRecord(
                id=suri,
                name=fragment,
                kind="doc_fragment",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno, # Approximation
                end_col_offset=col_offset, # Approximation
                logical_path=fragment,
                canonical_fqn=fragment, # In sidecar context, fragment is the key
                docstring_content=docstring_content_json,
                docstring_hash=docstring_hash,
                # Fields not relevant for sidecar symbols:
                signature_hash=None,
                signature_text=None,
                alias_target_fqn=None,
                alias_target_id=None
            )
            symbols.append(symbol)

            # --- Build Reference (Binding to Python) ---
            # Generate the Python SURI. Note: This requires PythonURIGenerator logic ideally.
            # But here we construct a cross-reference.
            # The target_id should be the Python SURI.
            # We assume standard python scheme "py://"
            
            python_suri = f"py://{py_path_rel}#{fragment}"
            
            # Special handling for module docstring
            if fragment == "__doc__":
                # Module docstring usually maps to the module symbol itself or __doc__?
                # In PythonAdapter, module symbol is the file itself (py://path/to/file.py) without fragment
                # BUT, PythonAdapter also emits "__doc__" as attribute? No.
                # PythonAdapter: 
                #   Module symbol: id=py://path/to/file.py, name=module_name
                #   Attributes...
                # So "__doc__" in sidecar should point to the module symbol `py://path/to/file.py`
                python_suri = f"py://{py_path_rel}"
            
            ref = ReferenceRecord(
                source_file_id=None, # Filled by storage
                target_fqn=None, # We use strong ID binding
                target_id=python_suri,
                kind="doc_binding",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset + len(fragment)
            )
            references.append(ref)

        return symbols, references