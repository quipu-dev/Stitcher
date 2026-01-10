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

        # Pre-calculate logical FQN for the module
        logical_module_fqn = rel_path.replace("/", ".").replace(".py", "")
        if logical_module_fqn.endswith(".__init__"):
            logical_module_fqn = logical_module_fqn[: -len(".__init__")]

        # 3. Project to Symbols
        symbols = self._extract_symbols(rel_path, module_def, logical_module_fqn)

        # 4. Project to References
        references = self._extract_references(
            rel_path, module_def, content, file_path, logical_module_fqn
        )

        return symbols, references

    def _extract_symbols(
        self, rel_path: str, module: ModuleDef, logical_module_fqn: str
    ) -> List[SymbolRecord]:
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
                fp = self.hasher.compute(entity_for_hash)  # type: ignore
                sig_hash = fp.get("current_code_structure_hash")

            # Location Handling
            loc = getattr(entity_for_hash, "location", None)

            # Alias Handling
            alias_target_id: Optional[str] = None
            final_kind = kind
            alias_target_fqn = getattr(entity_for_hash, "alias_target", None)
            if alias_target_fqn:
                final_kind = "alias"
                alias_target_id = self._guess_suri(
                    alias_target_fqn, logical_module_fqn, rel_path
                )

            symbols.append(
                SymbolRecord(
                    id=suri,
                    name=name,
                    kind=final_kind,
                    lineno=loc.lineno if loc else 0,
                    col_offset=loc.col_offset if loc else 0,
                    end_lineno=loc.end_lineno if loc else 0,
                    end_col_offset=loc.end_col_offset if loc else 0,
                    logical_path=fragment,  # This is relative logical path in file
                    signature_hash=sig_hash,
                    alias_target_id=alias_target_id,
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
                add(attr.name, "variable", attr, parent_fragment=cls_frag)

        # 3. Module-level Attributes
        for attr in module.attributes:
            add(attr.name, "variable", attr)

        return symbols

    def _extract_references(
        self,
        rel_path: str,
        module: ModuleDef,
        content: str,
        file_path: Path,
        logical_module_fqn: str,
    ) -> List[ReferenceRecord]:
        refs: List[ReferenceRecord] = []

        # 1. Build local_symbols map (Name -> FQN)
        # This helps the visitor distinguish between local usages and globals/builtins.
        # It maps a name visible in the current scope to its fully-qualified name.
        local_symbols = {}

        # 1a. Register all imported aliases (e.g., 'helper' -> 'pkg.utils.helper')
        for attr in module.attributes:
            if attr.alias_target:
                local_symbols[attr.name] = attr.alias_target

        # 1b. Register all local definitions
        def register_local(name: str, parent_fqn: str = "") -> str:
            fqn = (
                f"{parent_fqn}.{name}" if parent_fqn else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            cls_fqn = register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
                    local_symbols[attr.name] = attr.alias_target
            # Methods are handled by the visitor's scope analysis (e.g., self.method)
            # so we don't need to register them as top-level local symbols.

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
                            lineno=loc.lineno,
                            col_offset=loc.col_offset,
                            end_lineno=loc.end_lineno,
                            end_col_offset=loc.end_col_offset,
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
