from pathlib import Path
from typing import List, Tuple, Optional

from stitcher.spec import ModuleDef
from stitcher.index.protocols import LanguageAdapter
from stitcher.index.types import SymbolRecord, ReferenceRecord

from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python.fingerprint import PythonFingerprintStrategy
from .uri import SURIGenerator


class PythonAdapter(LanguageAdapter):
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.parser = GriffePythonParser()
        self.hasher = PythonFingerprintStrategy()

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        # 1. Calculate relative path for SURI
        try:
            rel_path = file_path.relative_to(self.root_path).as_posix()
        except ValueError:
            # Fallback if file is not in root (should not happen in normal scan)
            rel_path = file_path.name

        # 2. Parse into ModuleDef
        module_def = self.parser.parse(content, file_path=rel_path)

        # 3. Project to Symbols
        symbols = self._extract_symbols(rel_path, module_def)

        # 4. Project to References (Basic Import Analysis for MVP)
        # TODO: Implement full usage analysis using UsageScanVisitor
        references = self._extract_references(rel_path, module_def)

        return symbols, references

    def _extract_symbols(self, rel_path: str, module: ModuleDef) -> List[SymbolRecord]:
        symbols: List[SymbolRecord] = []

        # Helper to add symbol
        def add(
            name: str,
            kind: str,
            entity_for_hash: Optional[object] = None,
            parent_fragment: str = "",
        ):
            fragment = f"{parent_fragment}.{name}" if parent_fragment else name
            suri = SURIGenerator.for_symbol(rel_path, fragment)

            # Compute Hash
            sig_hash = None
            if entity_for_hash:
                # We reuse the strategy, but we need to adapt it because strategy returns a Fingerprint object
                # with multiple keys. We probably want 'current_code_structure_hash'.
                fp = self.hasher.compute(entity_for_hash)  # type: ignore
                sig_hash = fp.get("current_code_structure_hash")

            # Location is currently not provided by ModuleDef in a granular way easily
            # (Griffe objects have lineno, but ModuleDef might have lost it or it's deep).
            # For MVP, we use 0, 0 as placeholder or we need to extend ModuleDef to carry location.
            # Extending ModuleDef is the right way, but for now we proceed.
            # TODO: Enhance ModuleDef to carry source location info.

            symbols.append(
                SymbolRecord(
                    id=suri,
                    name=name,
                    kind=kind,
                    location_start=0,  # Placeholder
                    location_end=0,  # Placeholder
                    logical_path=fragment,  # This is relative logical path in file
                    signature_hash=sig_hash,
                )
            )
            return fragment

        # 1. Functions
        for func in module.functions:
            add(func.name, "function", func)

        # 2. Classes
        for cls in module.classes:
            cls_frag = add(cls.name, "class", cls)

            # Methods
            for method in cls.methods:
                add(method.name, "method", method, parent_fragment=cls_frag)

            # Attributes
            for attr in cls.attributes:
                add(attr.name, "variable", None, parent_fragment=cls_frag)

        # 3. Module-level Attributes
        for attr in module.attributes:
            add(attr.name, "variable", None)

        return symbols

    def _extract_references(
        self, rel_path: str, module: ModuleDef
    ) -> List[ReferenceRecord]:
        # Basic implementation: extract imports as references
        # This is very limited. Real ref extraction needs AST traversal.
        # But we deliver what we can for now.
        refs: List[ReferenceRecord] = []
        return refs
