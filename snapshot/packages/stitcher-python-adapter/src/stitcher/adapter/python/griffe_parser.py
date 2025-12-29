import griffe.loader
from griffe import Function as GriffeFunction
from griffe import Class as GriffeClass
from griffe import Attribute as GriffeAttribute

from stitcher.spec import (
    ModuleDef,
    FunctionDef,
    ClassDef,
    Argument,
    ArgumentKind,
    Attribute,
    LanguageParserProtocol,
)


class GriffePythonParser(LanguageParserProtocol):
    """A Python parser implementation powered by Griffe."""

    def parse(self, source_code: str, file_path: str = "") -> ModuleDef:
        """
        Parses Python source code using Griffe and maps the result to
        the Stitcher IR (ModuleDef).
        """
        # Griffe can work with in-memory code, but needs a module name.
        # We derive a plausible module name from the file path.
        module_name = (
            file_path.replace("/", ".").removesuffix(".py") if file_path else "dynamic_module"
        )

        griffe_module = griffe.loader.load_module(
            module_name,
            filepath=file_path or None,  # Pass None if not provided
            code=source_code,
        )

        # TODO: Implement the full mapping logic from griffe.dataclasses.Module
        # to stitcher.spec.ModuleDef.

        # Placeholder implementation for the skeleton:
        return ModuleDef(
            file_path=file_path,
            docstring=griffe_module.docstring.value if griffe_module.docstring else None,
            # functions=[self._map_function(f) for f in griffe_module.functions.values()],
            # classes=[self._map_class(c) for c in griffe_module.classes.values()],
            attributes=[
                self._map_attribute(a) for a in griffe_module.attributes.values()
            ],
        )

    def _map_function(self, griffe_func: GriffeFunction) -> FunctionDef:
        # TODO: Map Griffe function to FunctionDef
        pass

    def _map_class(self, griffe_class: GriffeClass) -> ClassDef:
        # TODO: Map Griffe class to ClassDef
        pass

    def _map_attribute(self, griffe_attr: GriffeAttribute) -> Attribute:
        """Maps a Griffe Attribute to a Stitcher IR Attribute."""
        return Attribute(
            name=griffe_attr.name,
            annotation=str(griffe_attr.annotation)
            if griffe_attr.annotation
            else None,
            value=griffe_attr.value if griffe_attr.value else None,
            docstring=griffe_attr.docstring.value if griffe_attr.docstring else None,
        )