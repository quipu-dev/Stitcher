import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Any, Dict

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib


@dataclass
class StitcherConfig:
    scan_paths: List[str] = field(default_factory=list)


def _find_pyproject_toml(search_path: Path) -> Path:
    """Traverse upwards to find pyproject.toml."""
    current_dir = search_path.resolve()
    while current_dir.parent != current_dir:
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.is_file():
            return pyproject_path
        current_dir = current_dir.parent
    raise FileNotFoundError("Could not find pyproject.toml in any parent directory.")


def load_config_from_path(search_path: Path) -> StitcherConfig:
    """Finds and loads stitcher config from pyproject.toml."""
    try:
        config_path = _find_pyproject_toml(search_path)
    except FileNotFoundError:
        # If no config file, return a default config.
        # This allows running stitcher on projects without explicit setup.
        return StitcherConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    stitcher_data: Dict[str, Any] = data.get("tool", {}).get("stitcher", {})
    
    # Create config with data from file, falling back to defaults.
    return StitcherConfig(
        scan_paths=stitcher_data.get("scan_paths", [])
    )