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
    plugins: Dict[str, str] = field(default_factory=dict)


def _find_pyproject_toml(search_path: Path) -> Path:
    current_dir = search_path.resolve()
    while current_dir.parent != current_dir:
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.is_file():
            return pyproject_path
        current_dir = current_dir.parent
    raise FileNotFoundError("Could not find pyproject.toml in any parent directory.")


def _find_plugins(workspace_root: Path) -> Dict[str, str]:
    plugins: Dict[str, str] = {}
    for toml_file in workspace_root.rglob("**/pyproject.toml"):
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)

            entry_points = data.get("project", {}).get("entry-points", {})
            stitcher_plugins = entry_points.get("stitcher.plugins", {})
            if stitcher_plugins:
                plugins.update(stitcher_plugins)
        except Exception:
            # Silently ignore parsing errors in other projects' toml files
            pass
    return plugins


def load_config_from_path(search_path: Path) -> StitcherConfig:
    plugins = _find_plugins(search_path)

    try:
        config_path = _find_pyproject_toml(search_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        stitcher_data: Dict[str, Any] = data.get("tool", {}).get("stitcher", {})
    except FileNotFoundError:
        # If no root config file, still return discovered plugins with default scan_paths
        return StitcherConfig(plugins=plugins)

    # Create config with data from file, falling back to defaults.
    return StitcherConfig(
        scan_paths=stitcher_data.get("scan_paths", []), plugins=plugins
    )
