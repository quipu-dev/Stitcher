import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Any, Dict
import tomli as tomllib
import tomllib

def _find_pyproject_toml(search_path: Path) -> Path:
    """Traverse upwards to find pyproject.toml."""
    ...

def _find_plugins(workspace_root: Path) -> Dict[str, str]:
    """Scans the entire workspace for stitcher plugins in pyproject.toml files."""
    ...

def load_config_from_path(search_path: Path) -> StitcherConfig:
    """Finds and loads stitcher config from pyproject.toml, and discovers plugins."""
    ...

class StitcherConfig:
    scan_paths: List[str]
    plugins: Dict[str, str]