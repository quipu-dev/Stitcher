import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Any, Dict, Optional, Tuple

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib


@dataclass
class StitcherConfig:
    name: str = "default"
    scan_paths: List[str] = field(default_factory=list)
    plugins: Dict[str, str] = field(default_factory=dict)
    stub_path: Optional[str] = None
    stub_package: Optional[str] = None
    docstring_style: str = "raw"
    peripheral_paths: List[str] = field(default_factory=list)


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


def load_config_from_path(
    search_path: Path,
) -> Tuple[List[StitcherConfig], Optional[str]]:
    plugins = _find_plugins(search_path)
    project_name: Optional[str] = None
    stitcher_data: Dict[str, Any] = {}

    try:
        config_path = _find_pyproject_toml(search_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        project_name = data.get("project", {}).get("name")
        stitcher_data = data.get("tool", {}).get("stitcher", {})

    except FileNotFoundError:
        # If no root config file, return default config with discovered plugins
        return [StitcherConfig(plugins=plugins)], None

    configs: List[StitcherConfig] = []
    targets = stitcher_data.get("targets", {})

    if targets:
        # Multi-target mode
        for target_name, target_data in targets.items():
            configs.append(
                StitcherConfig(
                    name=target_name,
                    scan_paths=target_data.get("scan_paths", []),
                    plugins=plugins,
                    stub_path=target_data.get("stub_path"),
                    stub_package=target_data.get("stub_package"),
                    docstring_style=target_data.get("docstring_style", "raw"),
                    peripheral_paths=target_data.get("peripheral_paths", []),
                )
            )
    else:
        # Single-target (Legacy/Simple) mode
        configs.append(
            StitcherConfig(
                scan_paths=stitcher_data.get("scan_paths", []),
                plugins=plugins,
                stub_path=stitcher_data.get("stub_path"),
                stub_package=stitcher_data.get("stub_package"),
                docstring_style=stitcher_data.get("docstring_style", "raw"),
                peripheral_paths=stitcher_data.get("peripheral_paths", []),
            )
        )

    return configs, project_name
