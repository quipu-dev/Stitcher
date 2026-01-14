Of course. We will now proceed with the consumer layer refactoring, integrating the new protocols to complete the Sidecar indexing pipeline.

## [WIP] refactor: Integrate Sidecar parsing into the indexing pipeline

### 用户需求

The user requires the refactoring of the consumer layer to complete the Sidecar indexing feature. This involves upgrading `SidecarAdapter` to parse `.stitcher.yaml` files into `DocEntryRecord`s and registering this adapter within the main application's `FileIndexer`.

### 评论

This plan completes the "Write Path" portion of our "Zero-IO" architecture. By integrating the `SidecarAdapter` into the `FileIndexer`, we ensure that any changes to `.stitcher.yaml` files are now parsed, processed, and stored in the database during the indexing phase. This is the final and most critical step in moving the expensive YAML parsing logic away from the high-frequency `check` command.

### 目标

1.  Completely refactor the `SidecarAdapter.parse` method to utilize the new `DocstringSerializerProtocol`, parse YAML content, generate SURIs, and produce a list of `DocEntryRecord`s.
2.  Update the `StitcherApp` to register an instance of `SidecarAdapter` with the `FileIndexer` for `.yaml` and `.yml` file extensions.

### 基本原理

1.  **`SidecarAdapter` Refactoring**: The `parse` method will be rewritten entirely. It will now perform the heavy lifting: loading YAML with `ruamel.yaml`, using a serializer to convert the data into `DocstringIR` and then into a JSON-serializable DTO, generating a deterministic hash, and finally creating the `DocEntryRecord`s. This change is substantial, so `write_file` is the most robust strategy.
2.  **Application Integration**: A simple `patch_file` will be applied to `stitcher-application`'s `core.py`. In the `StitcherApp.__init__` method, we will add the lines to register the `SidecarAdapter` with the `FileIndexer`, making the indexer aware of how to process YAML files.

### 标签

#intent/refine #flow/ready #priority/high #comp/sidecar #comp/application #comp/index #concept/parser #scope/core #ai/instruct #task/domain/storage #task/object/sidecar-index #task/action/implementation #task/state/continue #task/status/active

---

### Script

#### Acts 1: Refactor SidecarAdapter to Produce DocEntryRecords

We will replace the entire `adapter.py` file in `stitcher-lang-sidecar` with the new, compliant implementation.

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python
import io
import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Dict, Union, Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from stitcher.spec import DocstringIR, URIGeneratorProtocol
from stitcher.spec.protocols import DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord, DocEntryRecord

from .parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
from stitcher.lang.python.analysis.models import ReferenceType

# For the indexing path, we need a default serializer.
# The `DocumentManager` is responsible for setting the correct one based on config,
# but the indexer operates at a lower level. RawSerializer is a safe default.
from stitcher.lang.python.docstring import RawSerializer


class SidecarAdapter(LanguageAdapter):
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
    ):
        self.root_path = root_path
        self.uri_generator = uri_generator
        self.resolver = AssetPathResolver(root_path)
        self._yaml = YAML()
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        self._yaml.preserve_quotes = True
        self._yaml.width = 1000  # Avoid line wrapping for readability

    def _to_literal_strings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively convert all string values to LiteralScalarString for block style."""
        processed = {}
        for k, v in data.items():
            if isinstance(v, str):
                processed[k] = LiteralScalarString(v)
            elif isinstance(v, dict):
                processed[k] = self._to_literal_strings(v)
            else:
                processed[k] = v
        return processed

    def parse(
        self, file_path: Path, content: str
    ) -> Union[
        Tuple[List[SymbolRecord], List[ReferenceRecord]],
        Tuple[List[SymbolRecord], List[ReferenceRecord], List[DocEntryRecord]],
    ]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []
        doc_entries: List[DocEntryRecord] = []

        # This adapter handles both .json (signatures) and .yaml (docs)
        if file_path.suffix == ".json":
            refs = parse_signature_references(content)
            for suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,
                        target_id=suri,
                        kind=ReferenceType.SIDECAR_ID.value,
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )
            return symbols, references

        elif file_path.suffix in (".yaml", ".yml"):
            try:
                if not file_path.name.endswith(".stitcher.yaml"):
                    return symbols, references

                # Derive the associated source Python file path
                py_name = file_path.name.replace(".stitcher.yaml", ".py")
                py_path = file_path.with_name(py_name)

                if not py_path.exists():
                    return symbols, references

                # For SURI generation, we need the workspace-relative path of the source file
                rel_py_path = py_path.relative_to(self.root_path).as_posix()

                # Full parsing for DocEntryRecord creation
                data = self._yaml.load(content)
                # Use RawSerializer as a default for the indexing path
                serializer = RawSerializer()

                if isinstance(data, dict):
                    for fragment, raw_ir_obj in data.items():
                        # 1. Determine location (line/col) from ruamel
                        lineno = 0
                        lc = getattr(data, "lc", None)
                        if lc and hasattr(lc, "item"):
                            pos = lc.item(fragment)
                            if pos:
                                lineno = pos[0] + 1

                        # 2. Generate SURI for the symbol
                        suri = self.uri_generator.generate_symbol_uri(
                            rel_py_path, str(fragment)
                        )

                        try:
                            # 3. Normalize to IR, then to a JSON-safe DTO
                            ir = serializer.from_yaml_object(raw_ir_obj)
                            ir_dict = serializer.to_serializable_dict(ir)
                            ir_json = json.dumps(ir_dict, sort_keys=True)

                            # 4. Compute deterministic hash from the JSON string
                            content_hash = hashlib.sha256(
                                ir_json.encode("utf-8")
                            ).hexdigest()

                            # 5. Create the DocEntryRecord for the indexer
                            doc_entries.append(
                                DocEntryRecord(
                                    symbol_id=suri,
                                    content_hash=content_hash,
                                    ir_data_json=ir_json,
                                    lineno=lineno,
                                )
                            )

                            # 6. Also create a ReferenceRecord for graph analysis
                            references.append(
                                ReferenceRecord(
                                    target_id=suri,
                                    kind=ReferenceType.SIDECAR_DOC_ID.value,
                                    lineno=lineno,
                                    col_offset=0,  # Col is less precise for YAML keys
                                    end_lineno=lineno,
                                    end_col_offset=len(str(fragment)),
                                )
                            )

                        except Exception:
                            # Skip malformed entries within the YAML file
                            continue

            except (ValueError, FileNotFoundError, Exception):
                # If the whole file is malformed or paths are wrong, return empty
                pass

        return symbols, references, doc_entries

    def load_doc_irs(
        self, path: Path, serializer: DocstringSerializerProtocol
    ) -> Dict[str, DocstringIR]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                raw_data = self._yaml.load(f)
            if not isinstance(raw_data, dict):
                return {}

            return {fqn: serializer.from_yaml_object(val) for fqn, val in raw_data.items()}
        except Exception:
            return {}

    def save_doc_irs(
        self,
        path: Path,
        irs: Dict[str, DocstringIR],
        serializer: DocstringSerializerProtocol,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            # --- UPDATE PATH ---
            # Load existing content to preserve formatting, comments, and key order.
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = self._yaml.load(f)
                original_content = path.read_text("utf-8")
            except Exception:
                # If we can't read/parse, treat it as a new file creation.
                data = {}
                original_content = ""

            if not isinstance(data, dict):
                data = {}

            # Update the loaded data with new/modified IRs.
            # NO SORTING is applied to preserve original key order.
            # New keys will be appended by ruamel.yaml.
            for fqn, ir in irs.items():
                yaml_val = serializer.to_yaml_object(ir)
                if isinstance(yaml_val, str):
                    formatted_val = LiteralScalarString(yaml_val)
                elif isinstance(yaml_val, dict):
                    formatted_val = self._to_literal_strings(yaml_val)
                else:
                    formatted_val = yaml_val
                data[fqn] = formatted_val

            string_stream = io.StringIO()
            self._yaml.dump(data, string_stream)
            new_content = string_stream.getvalue()

            # Compare with original content to avoid unnecessary writes/mtime changes.
            if original_content != new_content:
                with path.open("w", encoding="utf-8") as f:
                    f.write(new_content)
        else:
            # --- CREATE PATH ---
            # For new files, create a clean, sorted baseline for predictability.
            sorted_irs = dict(sorted(irs.items()))
            yaml_data = {fqn: serializer.to_yaml_object(ir) for fqn, ir in sorted_irs.items()}
            formatted_data = self._to_literal_strings(yaml_data)
            string_stream = io.StringIO()
            self._yaml.dump(formatted_data, string_stream)
            with path.open("w", encoding="utf-8") as f:
                f.write(string_stream.getvalue())

    def dump_to_string(self, data: Dict[str, Any]) -> str:
        string_stream = io.StringIO()
        self._yaml.dump(self._to_literal_strings(data), string_stream)
        return string_stream.getvalue()

    def load_raw_data(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                # ruamel.yaml.load returns a special dict-like object that preserves structure
                raw_data = self._yaml.load(f)
            return raw_data if isinstance(raw_data, dict) else {}
        except Exception:
            return {}

    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str:
        """Dumps data while preserving formatting, for high-fidelity updates."""
        string_stream = io.StringIO()
        self._yaml.dump(data, string_stream)
        return string_stream.getvalue()

    def serialize_ir(
        self, ir: DocstringIR, serializer: DocstringSerializerProtocol
    ) -> Union[str, Dict[str, Any]]:
        return serializer.to_yaml_object(ir)
~~~~~

#### Acts 2: Register SidecarAdapter in StitcherApp

Now, we register the `SidecarAdapter` with the `FileIndexer`.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python import PythonAdapter
from stitcher.workspace import Workspace
~~~~~
~~~~~python.new
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python import PythonAdapter
from stitcher.lang.sidecar import SidecarAdapter
from stitcher.workspace import Workspace
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        python_adapter = PythonAdapter(
            root_path, search_paths, uri_generator=self.uri_generator
        )
        self.file_indexer.register_adapter(".py", python_adapter)

        # 3. Runners (Command Handlers)
        check_resolver = CheckResolver(
~~~~~
~~~~~python.new
        python_adapter = PythonAdapter(
            root_path, search_paths, uri_generator=self.uri_generator
        )
        sidecar_adapter = SidecarAdapter(root_path, uri_generator=self.uri_generator)

        self.file_indexer.register_adapter(".py", python_adapter)
        self.file_indexer.register_adapter(".yaml", sidecar_adapter)
        self.file_indexer.register_adapter(".yml", sidecar_adapter)

        # 3. Runners (Command Handlers)
        check_resolver = CheckResolver(
~~~~~

### 下一步建议
The "Write Path" for Sidecar indexing is now complete. All foundational work for the "Zero-IO" `check` command is in place.

The next and final step is to **refactor `CheckRunner` and its dependencies** to stop reading files from the filesystem and instead query the `index.db` (joining `symbols` and `doc_entries`) to perform its consistency analysis. This will deliver the massive performance improvement we are aiming for.
