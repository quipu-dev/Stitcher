from pathlib import Path
from typing import Dict
import yaml
from stitcher.io.interfaces import DocumentAdapter

class YamlAdapter(DocumentAdapter):
    """Adapter for reading and writing .yaml documentation files."""

    def load(self, path: Path) -> Dict[str, str]: ...

    def save(self, path: Path, data: Dict[str, str]) -> None: ...