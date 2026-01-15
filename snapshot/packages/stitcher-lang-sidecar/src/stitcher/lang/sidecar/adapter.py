import io
from pathlib import Path
from typing import List, Tuple, Dict, Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from stitcher.spec import DocstringIR, URIGeneratorProtocol
from stitcher.spec.protocols import DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord

from .parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
from stitcher.lang.python.analysis.models import ReferenceType


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
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

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

        elif file_path.suffix in (".yaml", ".yml"):
            try:
                if not file_path.name.endswith(".stitcher.yaml"):
                    return symbols, references

                py_name = file_path.name.replace(".stitcher.yaml", ".py")
                py_path = file_path.with_name(py_name)

                if not py_path.exists():
                    return symbols, references

                rel_py_path = py_path.relative_to(self.root_path).as_posix()

                refs = parse_doc_references(content)
                for fragment, line, col in refs:
                    suri = self.uri_generator.generate_symbol_uri(rel_py_path, fragment)
                    references.append(
                        ReferenceRecord(
                            target_id=suri,
                            kind=ReferenceType.SIDECAR_DOC_ID.value,
                            lineno=line,
                            col_offset=col,
                            end_lineno=line,
                            end_col_offset=col + len(fragment),
                        )
                    )
            except (ValueError, FileNotFoundError):
                pass

        return symbols, references

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

            return {
                fqn: serializer.from_view_data(val) for fqn, val in raw_data.items()
            }
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
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = self._yaml.load(f)
                original_content = path.read_text("utf-8")
            except Exception:
                data = {}
                original_content = ""

            if not isinstance(data, dict):
                data = {}

            for fqn, ir in irs.items():
                view_obj = serializer.to_view_data(ir)
                if isinstance(view_obj, str):
                    data[fqn] = LiteralScalarString(view_obj)
                elif isinstance(view_obj, dict):
                    data[fqn] = self._to_literal_strings(view_obj)
                else:
                    data[fqn] = view_obj

            string_stream = io.StringIO()
            self._yaml.dump(data, string_stream)
            new_content = string_stream.getvalue()

            if original_content != new_content:
                with path.open("w", encoding="utf-8") as f:
                    f.write(new_content)
        else:
            # --- CREATE PATH ---
            sorted_irs = dict(sorted(irs.items()))
            view_data = {
                fqn: serializer.to_view_data(ir) for fqn, ir in sorted_irs.items()
            }
            formatted_data = self._to_literal_strings(view_data)
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

    def _ensure_block_scalars_inplace(self, data: Any) -> None:
        """
        Recursively updates the data structure in-place to convert strings to LiteralScalarString.
        This preserves Comments/Structure of CommentedMap/CommentedSeq while enforcing block style.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    data[k] = LiteralScalarString(v)
                elif isinstance(v, (dict, list)):
                    self._ensure_block_scalars_inplace(v)
        elif isinstance(data, list):
            for i, v in enumerate(data):
                if isinstance(v, str):
                    data[i] = LiteralScalarString(v)
                elif isinstance(v, (dict, list)):
                    self._ensure_block_scalars_inplace(v)

    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str:
        """Dumps data while preserving formatting, for high-fidelity updates."""
        # Enforce block scalar style for all string values in-place
        self._ensure_block_scalars_inplace(data)

        string_stream = io.StringIO()
        self._yaml.dump(data, string_stream)
        return string_stream.getvalue()

    def serialize_ir_for_transfer(
        self, ir: DocstringIR, serializer: DocstringSerializerProtocol
    ) -> Dict[str, Any]:
        return serializer.to_transfer_data(ir)
