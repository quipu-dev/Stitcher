from pathlib import Path
from typing import List, Tuple, Optional

from stitcher.spec import ModuleDef
from stitcher.index.protocols import LanguageAdapter
from stitcher.index.types import SymbolRecord, ReferenceRecord

import libcst as cst
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.adapter.python.fingerprint import PythonFingerprintStrategy
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry
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

        # 4. Project to References
        references = self._extract_references(rel_path, module_def, content, file_path)

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
        self, rel_path: str, module: ModuleDef, content: str, file_path: Path
    ) -> List[ReferenceRecord]:
        refs: List[ReferenceRecord] = []

        # 1. Build local_symbols map (Name -> FQN)
        # This helps the visitor distinguish between local usages and globals/builtins
        # The FQN here is logical (e.g. "pkg.mod.Class")
        logical_module_fqn = rel_path.replace("/", ".").replace(".py", "")
        if logical_module_fqn.endswith(".__init__"):
            logical_module_fqn = logical_module_fqn[: -len(".__init__")]

        local_symbols = {}

        # Helper to construct logical FQN for local symbols
        def register_local(name: str, parent_fqn: str = ""):
            fqn = (
                f"{parent_fqn}.{name}" if parent_fqn else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            cls_fqn = register_local(cls.name)
            for method in cls.methods:
                # Assuming UsageScanVisitor handles attribute lookups,
                # strictly speaking we might not need to pass method names as locals
                # unless they are used unqualified (which they aren't, they are self.x),
                # but registering top-level classes/funcs is key.
                pass

        # 2. Parse CST and Run Visitor
        try:
            wrapper = cst.MetadataWrapper(cst.parse_module(content))
            registry = UsageRegistry()

            visitor = UsageScanVisitor(
                file_path=file_path,
                local_symbols=local_symbols,
                registry=registry,
                current_module_fqn=logical_module_fqn,
                is_init_file=rel_path.endswith("__init__.py"),
            )
            wrapper.visit(visitor)

            # 3. Convert Registry to ReferenceRecords
            # UsageRegistry structure: { target_fqn: [UsageLocation, ...] }
            for target_fqn, locations in registry._index.items():
                for loc in locations:
                    # Convert logical FQN target to SURI
                    # NOTE: This is a heuristic. We don't have a SourceMap yet.
                    # We assume standard python layout: a.b.c -> py://a/b.py#c (simplified)
                    # For local symbols, we can be precise. For external, we guess.

                    target_suri = self._guess_suri(
                        target_fqn, logical_module_fqn, rel_path
                    )

                    refs.append(
                        ReferenceRecord(
                            target_id=target_suri,
                            kind=loc.ref_type.value,
                            location_start=loc.lineno,  # Simplification: use lineno as start offset proxy for now?
                            # Wait, ReferenceRecord expects byte offsets (integers) usually,
                            # but currently we don't have easy byte offset access from UsageLocation (it has line/col).
                            # TODO: Fix UsageLocation to carry byte offsets or convert line/col to offset.
                            # For MVP, we will store LINENO in location_start just to signal "not empty".
                            # This is Technical Debt but allows progress.
                            location_end=loc.end_lineno,
                        )
                    )

        except Exception:
            # If CST parsing fails (syntax error), we just return empty refs
            # Logging should happen higher up
            pass

        return refs

    def _guess_suri(
        self, fqn: str, current_module_fqn: str, current_rel_path: str
    ) -> str:
        # Case 1: Internal reference (same module)
        if fqn.startswith(current_module_fqn + "."):
            fragment = fqn[len(current_module_fqn) + 1 :]
            return SURIGenerator.for_symbol(current_rel_path, fragment)

        # Case 2: External reference
        # We naively convert dots to slashes.
        # This will be incorrect for complex package roots (src/),
        # but serves as a unique identifier for now.
        # e.g. "os.path.join" -> "py://os/path.py#join"

        parts = fqn.split(".")
        if len(parts) == 1:
            # Top level module or class
            return SURIGenerator.for_symbol(f"{parts[0]}.py", parts[0])

        # Guess: last part is symbol, rest is path
        path_parts = parts[:-1]
        symbol = parts[-1]
        guessed_path = "/".join(path_parts) + ".py"
        return SURIGenerator.for_symbol(guessed_path, symbol)
