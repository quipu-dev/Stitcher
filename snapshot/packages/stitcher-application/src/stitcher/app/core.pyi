from pathlib import Path
from typing import Dict, List
from collections import defaultdict
from stitcher.scanner import (
    parse_source_code,
    parse_plugin_entry,
    InspectionError,
    strip_docstrings,
    inject_docstrings,
)
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from stitcher.needle import L
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager, SignatureManager

class StitcherApp:
    def __init__(self, root_path: Path): ...

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        """Parses a list of source files into ModuleDef IRs."""
        ...

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        """Parses plugins and builds a virtual ModuleDef tree."""
        ...

    def _generate_stubs(self, modules: List[ModuleDef]) -> List[Path]:
        """Generates .pyi files from a list of ModuleDefs."""
        ...

    def run_from_config(self) -> List[Path]:
        """Loads config, discovers files and plugins, and generates all stubs."""
        ...

    def run_init(self) -> List[Path]:
        """Scans source files and extracts docstrings into external .stitcher.yaml files."""
        ...

    def run_check(self) -> bool:
        """
        Checks consistency between source code and documentation files.
Returns True if passed, False if issues found.
        """
        ...

    def run_strip(self) -> List[Path]:
        """Strips docstrings from all source files."""
        ...

    def run_eject(self) -> List[Path]:
        """Injects docstrings from YAML files back into source code."""
        ...

    def _get_files_from_config(self, config) -> List[Path]:
        """Helper to discover all source files based on config."""
        ...